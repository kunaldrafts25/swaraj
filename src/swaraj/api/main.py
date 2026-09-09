"""SWARAJ v2 FastAPI application.

Provides all API endpoints for the SWARAJ sovereign workbench.
Does not expose private keys, arbitrary filesystem access, or unrestricted subprocess execution.
"""

import sys
import os
from typing import Any, Dict, Optional, List
from pathlib import Path
from datetime import datetime
import asyncio
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
import json

from swaraj.config import get_settings, settings
from swaraj.registry.loader import RegistryLoader
from swaraj.registry.manifest_schema import ChecksumStatus
from swaraj.auto_bench.capability_vector import CapabilityVectorStorage, CapabilityVectorCalculator
from swaraj.router.decide import (
    RouterDecisionEngine,
    RoutingDecision,
    RouterUnavailableError,
    ModelNotBenchmarkedError,
    NoEligibleModelError,
)
from swaraj.governance.rbac import RBACManager, PermissionResult, ApprovalRequest, Action
from swaraj.governance.audit_log import AuditLog, AuditEntryType
from swaraj.governance.certificate import CertificateManager, RunCertificate as Certificate
from swaraj.monitor.egress_watch import EgressMonitor, ConnectionEvent, EgressState, SecurityStatus as SecurityState

# Global egress monitor registry (manages multiple runs)
_egress_monitors: dict[str, EgressMonitor] = {}

# In-memory run store: run_id -> AgentState dict snapshot
_run_store: dict[str, dict] = {}

def _get_or_create_monitor(run_id: str) -> EgressMonitor:
    """Get or create an egress monitor for a run."""
    if run_id not in _egress_monitors:
        _egress_monitors[run_id] = EgressMonitor(run_id=run_id)
    return _egress_monitors[run_id]
from swaraj.agent.schemas import AgentState, RunState, TaskInput, SelfCheckResult
from swaraj.tools.docx_writer import DocXWriter
from swaraj.tools.xlsx_writer import XLSXWriter


class HealthResponse(BaseModel):
    """Health check response model.
    
    REQ-020: API Requirements
    REQ-017: Observability Requirements
    """
    
    model_config = ConfigDict(protected_namespaces=())
    
    app_name: str
    version: str
    status: str
    registry_ready: bool
    model_artifact_present: bool
    checksum_verification_state: str
    fail_closed: bool
    details: Dict[str, Any]


class RouterDecideRequest(BaseModel):
    """Request model for router decision endpoint."""
    
    model_config = ConfigDict(protected_namespaces=())
    
    task_description: str
    task_type: Optional[str] = None
    latency_budget_ms: Optional[int] = None


class RouterDecideResponse(BaseModel):
    """Response model for router decision endpoint."""
    
    model_config = ConfigDict(protected_namespaces=())
    
    selected_model: Optional[str]
    confidence: float
    reasoning: str
    capability_scores: Dict[str, Optional[float]]
    hardware_tier: str
    task_characteristics: Dict[str, Any]
    is_fail_closed: bool
    error_detail: Optional[str] = None


# Phase 2 & 3 Response Models
class HardwareStatusResponse(BaseModel):
    """Hardware status response."""
    model_config = ConfigDict(protected_namespaces=())
    tier: str
    gpu_available: bool
    vram_gb: Optional[float]
    measured_latency_per_500_tokens: Optional[float]
    calibrated_at: Optional[str]


class RegistryModel(BaseModel):
    """Model registry entry."""
    model_config = ConfigDict(protected_namespaces=())
    name: str
    version: str
    gguf_path: str
    sha256: Optional[str]
    quant: str
    context_length: int
    hardware_tier_min: str
    capability_vector: Optional[Dict[str, Optional[float]]]
    verified: bool
    checksum_status: str


class RegistryResponse(BaseModel):
    """Registry response."""
    model_config = ConfigDict(protected_namespaces=())
    models: List[RegistryModel]
    total: int
    verified_count: int


class IngestRequest(BaseModel):
    """Document ingestion request."""
    model_config = ConfigDict(protected_namespaces=())
    user_id: str
    role: str


class IngestResponse(BaseModel):
    """Document ingestion response."""
    model_config = ConfigDict(protected_namespaces=())
    document_id: str
    pages_processed: int
    ocr_results: List[Dict[str, Any]]
    indexed: bool
    extracted_preview: Optional[str] = None   # first 300 chars of extracted text
    filename: Optional[str] = None


class AgentRunRequest(BaseModel):
    """Agent run request."""
    model_config = ConfigDict(protected_namespaces=())
    task_description: str
    user_id: str
    role: str
    source_documents: Optional[List[str]] = None
    task_type: Optional[str] = None


class AgentRunResponse(BaseModel):
    """Agent run response."""
    model_config = ConfigDict(protected_namespaces=())
    run_id: str
    status: str
    initial_state: Dict[str, Any]


class TraceResponse(BaseModel):
    """Agent trace response."""
    model_config = ConfigDict(protected_namespaces=())
    run_id: str
    state: Dict[str, Any]
    transitions: List[Dict[str, Any]]
    iterations: int
    final_certificate_eligible: bool
    # Chat-facing fields: the actual AI response content
    artifact_content: Optional[str] = None    # rendered markdown / code in chat
    artifact_filename: Optional[str] = None   # e.g. "summary_abc.md"
    task_description: Optional[str] = None    # echoed back for history display


class EgressEventResponse(BaseModel):
    """Egress event response."""
    model_config = ConfigDict(protected_namespaces=())
    run_id: str
    timestamp: str
    address: str
    port: int
    status: str
    is_loopback: bool
    security_event: bool


class EgressStatusResponse(BaseModel):
    """Egress status response."""
    model_config = ConfigDict(protected_namespaces=())
    run_id: str
    security_state: str
    event_count: int
    latest_heartbeat: Optional[str]
    kill_switch_triggered: bool
    events: List[EgressEventResponse]


class ApprovalItem(BaseModel):
    """Approval queue item."""
    model_config = ConfigDict(protected_namespaces=())
    approval_id: str
    run_id: str
    user_id: str
    role: str
    action: str
    artifact: str
    policy_reason: str
    requested_at: str


class ApprovalsResponse(BaseModel):
    """Approvals list response."""
    model_config = ConfigDict(protected_namespaces=())
    pending: List[ApprovalItem]
    count: int


class ApprovalDecisionRequest(BaseModel):
    """Approval decision request."""
    model_config = ConfigDict(protected_namespaces=())
    approved: bool
    reviewer_id: str
    comments: Optional[str] = None


class CertificateResponse(BaseModel):
    """Certificate response."""
    model_config = ConfigDict(protected_namespaces=())
    run_id: str
    started_at: str
    ended_at: str
    model_used: str
    egress_events: List[Dict[str, Any]]
    hash_chain_head: str
    signature: str
    signer_pubkey: str
    verified: bool


class AuditEventResponse(BaseModel):
    """Audit event response."""
    model_config = ConfigDict(protected_namespaces=())
    id: int
    run_id: str
    user: Optional[str]
    role: Optional[str]
    timestamp: str
    event_type: str
    details: Dict[str, Any]
    previous_hash: Optional[str]


class AuditEventsResponse(BaseModel):
    """Audit events list response."""
    model_config = ConfigDict(protected_namespaces=())
    events: List[AuditEventResponse]
    count: int


def _load_hardware_tier() -> tuple[str, Optional[float], Optional[str]]:
    """
    Detect hardware tier using HardwareDetector (pynvml → nvidia-smi → CPU baseline).
    Results are cached in data/hw_calibration.json for 1 hour.
    """
    try:
        from swaraj.runtime.hardware import detect_hardware
        import time
        cache_path = Path(settings.data_dir) / "hw_calibration.json"
        hw = detect_hardware(cache_path=cache_path)
        calibrated_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(hw.detected_at)
        )
        return hw.tier, None, calibrated_at
    except Exception:
        pass
    return "cpu_only", None, None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="SWARAJ v2: Sovereign Workbench for Agentic Reasoning & Auditable Judgement",
        docs_url=None,  # Disable Swagger UI for air-gapped operation
        redoc_url=None,  # Disable ReDoc for air-gapped operation
    )

    from starlette.middleware.base import BaseHTTPMiddleware

    class ApiPrefixMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path.startswith("/api/"):
                request.scope["path"] = request.url.path[4:]
            return await call_next(request)

    app.add_middleware(ApiPrefixMiddleware)

    # Resolved directories
    certs_dir = Path(settings.data_dir) / "certificates"
    workspace_root = Path(settings.data_dir) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    certs_dir.mkdir(parents=True, exist_ok=True)

    # UI distribution path (supports PyInstaller frozen mode and source mode)
    possible_ui_dirs = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        possible_ui_dirs.append(Path(sys._MEIPASS) / "ui-web" / "dist")
    possible_ui_dirs.extend([
        Path(sys.executable).resolve().parent / "_internal" / "ui-web" / "dist",
        Path(sys.executable).resolve().parent / "ui-web" / "dist",
        Path(settings.project_root) / "ui-web" / "dist",
        Path(__file__).resolve().parent.parent.parent.parent / "ui-web" / "dist",
    ])

    ui_dist_dir = possible_ui_dirs[0]
    for p in possible_ui_dirs:
        if p.exists() and (p / "index.html").exists():
            ui_dist_dir = p
            break

    if ui_dist_dir.exists() and (ui_dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(ui_dist_dir / "assets")), name="assets")

    # Initialize registry loader
    loader = RegistryLoader()

    # Initialize capability vector storage and calculator
    cap_storage_path = Path(settings.data_dir) / "capability_vectors.json"
    cap_storage = CapabilityVectorStorage(cap_storage_path)
    cap_calculator = CapabilityVectorCalculator(cap_storage)

    # Initialize RBAC manager
    rbac_manager = RBACManager(
        policy_path=settings.policy_dir / "rbac_policy.json",
        users_path=settings.users_file,
    )

    # Initialize certificate manager
    cert_manager = CertificateManager(keys_dir=settings.keys_dir)

    # Initialize audit log
    audit_log = AuditLog(db_path=settings.audit_db_path)

    # Determine hardware tier using live hardware detector
    hardware_tier, _measured_latency, _calibrated_at = _load_hardware_tier()

    # Initialize router engine with live hardware tier
    router_engine = RouterDecisionEngine(loader, cap_calculator, hardware_tier)

    _llm_runner_singleton: Optional[Any] = None

    def _get_llm_runner() -> Optional[Any]:
        nonlocal _llm_runner_singleton
        if _llm_runner_singleton is not None:
            return _llm_runner_singleton

        import logging as _logging
        _log = _logging.getLogger("swaraj.api")

        from swaraj.runtime.llm_runner import LLMRunner

        # Build ordered list of candidate directories to search for GGUF models.
        # Priority: SWARAJ_MODELS_DIR env → next to the exe (packaged) → project models/
        search_dirs: list[Path] = []
        env_models = os.environ.get("SWARAJ_MODELS_DIR", "")
        if env_models:
            search_dirs.append(Path(env_models))
        if getattr(sys, "frozen", False):
            # Packaged exe: model should live beside the executable
            exe_dir = Path(sys.executable).resolve().parent
            search_dirs.append(exe_dir / "models")
            search_dirs.append(exe_dir)          # flat placement beside exe
        search_dirs.append(Path(settings.models_dir))

        def _find_gguf(directory: Path) -> list[Path]:
            """Return valid .gguf files (exact extension, >10 MB, not partial downloads)."""
            if not directory.exists():
                return []
            return sorted(
                [
                    p for p in directory.iterdir()
                    if p.suffix == ".gguf"           # exact suffix — excludes .gguf.tmp etc.
                    and p.is_file()
                    and p.stat().st_size > 10 * 1024 * 1024
                ],
                key=lambda p: p.stat().st_size,
                reverse=True,
            )

        model_path: Optional[Path] = None
        for d in search_dirs:
            candidates = _find_gguf(d)
            if candidates:
                model_path = candidates[0]
                _log.info("LLMRunner: found model %s (%.1f GB) in %s",
                          model_path.name, model_path.stat().st_size / 1e9, d)
                break

        if model_path is None:
            searched = ", ".join(str(d) for d in search_dirs)
            _log.warning(
                "LLMRunner: no valid .gguf model found in [%s]. "
                "Place a GGUF model file (>10 MB) in the models/ directory to enable AI responses.",
                searched,
            )
            return None

        try:
            _llm_runner_singleton = LLMRunner(model_path, n_gpu_layers=None)
            return _llm_runner_singleton
        except Exception as llm_err:
            _log.warning("LLMRunner failed to load %s: %s", model_path, llm_err)
        return None
    
    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint.
        
        Reports:
        - Application name and version
        - Overall status (healthy/degraded/unavailable)
        - Registry readiness
        - Model artifact presence
        - Checksum verification state
        - Fail-closed state
        
        Does NOT expose:
        - Private signing keys
        - Arbitrary filesystem paths
        - Sensitive configuration
        """
        registry_status = loader.get_registry_status()
        
        # Determine overall status
        if registry_status["ready"]:
            status = "healthy"
            fail_closed = False
        elif registry_status["total_manifests"] > 0:
            # Has manifests but no verified models → fail-closed
            status = "degraded"
            fail_closed = True
        else:
            # No manifests at all
            status = "unavailable"
            fail_closed = True
        
        # Determine checksum verification state
        checksum_states = []
        artifact_present = False
        
        for model in registry_status.get("models", []):
            model_status = model.get("checksum_status", "unknown")
            checksum_states.append(f"{model.get('name', 'unknown')}: {model_status}")
            
            if model.get("verified", False):
                artifact_present = True
            elif model_status in ["missing", "placeholder", "mismatch"]:
                pass  # Artifact may exist but not verified
            else:
                # Check if any model has verified=true
                if model.get("verified"):
                    artifact_present = True
        
        # More accurate artifact presence check
        artifact_present = registry_status["verified_models"] > 0
        
        # Build checksum state summary
        if not checksum_states:
            checksum_state = "no_manifests"
        elif registry_status["verified_models"] > 0:
            checksum_state = "verified"
        elif any("placeholder" in s for s in checksum_states):
            checksum_state = "pending_verification"
        elif any("mismatch" in s for s in checksum_states):
            checksum_state = "mismatch"
        elif any("missing" in s for s in checksum_states):
            checksum_state = "artifact_missing"
        else:
            checksum_state = "unknown"
        
        return HealthResponse(
            app_name=settings.app_name,
            version=settings.app_version,
            status=status,
            registry_ready=registry_status["ready"],
            model_artifact_present=artifact_present,
            checksum_verification_state=checksum_state,
            fail_closed=fail_closed,
            details={
                "total_manifests": registry_status["total_manifests"],
                "verified_models": registry_status["verified_models"],
                "models": registry_status.get("models", []),
            },
        )
    
    @app.post("/router/decide", response_model=RouterDecideResponse)
    async def router_decide(request: RouterDecideRequest) -> RouterDecideResponse:
        """Make a routing decision for the given task.
        
        This endpoint implements explainable, deterministic model routing based on:
        - Task characteristics
        - Model capability vectors from real benchmarks
        - Hardware tier constraints
        
        Fail-Closed Behavior:
        - Returns 503 if no verified models available
        - Returns 503 if models not benchmarked
        - Returns 400 if no model satisfies constraints
        - Never returns fake confidence scores
        
        REQ-004: Explainable routing
        REQ-160: Router contract
        REQ-161: Deterministic routing
        """
        try:
            decision = router_engine.decide(
                task_description=request.task_description,
                task_type=request.task_type,
                latency_budget_ms=request.latency_budget_ms,
            )
            
            return RouterDecideResponse(
                selected_model=decision.selected_model,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
                capability_scores=decision.capability_scores,
                hardware_tier=decision.hardware_tier,
                task_characteristics=decision.task_characteristics,
                is_fail_closed=False,
                error_detail=None,
            )
            
        except RouterUnavailableError as e:
            # Fail-closed: no verified models
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "router_unavailable",
                    "message": str(e),
                },
            )
            
        except ModelNotBenchmarkedError as e:
            # Fail-closed: models not benchmarked
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "model_not_benchmarked",
                    "message": str(e),
                },
            )
            
        except NoEligibleModelError as e:
            # No model satisfies constraints
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "no_eligible_model",
                    "message": str(e),
                },
            )
    
    @app.get("/")
    async def root(request: Request) -> Any:
        """Root endpoint: serves frontend UI for browsers, or API metadata for JSON clients."""
        accept = request.headers.get("accept", "")
        # If frontend index.html exists, serve it for browser requests
        if ui_dist_dir.exists() and (ui_dist_dir / "index.html").exists():
            if "application/json" not in accept or "text/html" in accept or "*/*" in accept:
                return FileResponse(str(ui_dist_dir / "index.html"))

        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "health": "/health",
            "router": "/router/decide",
        }
    
    # Phase 2 & 3 Endpoints
    
    @app.get("/hardware/status", response_model=HardwareStatusResponse)
    async def hardware_status() -> HardwareStatusResponse:
        """Get live hardware tier from HardwareDetector (GPU via pynvml/nvidia-smi or CPU baseline)."""
        try:
            from swaraj.runtime.hardware import detect_hardware
            cache_path = Path(settings.data_dir) / "hw_calibration.json"
            hw = detect_hardware(cache_path=cache_path)
            vram_gb = round(hw.vram_total_mb / 1024, 1) if hw.vram_total_mb else None
            import time
            calibrated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(hw.detected_at))
            gpu_available = hw.vram_total_mb > 0
            return HardwareStatusResponse(
                tier=hw.tier,
                gpu_available=gpu_available,
                vram_gb=vram_gb,
                measured_latency_per_500_tokens=None,
                calibrated_at=calibrated_at,
            )
        except Exception:
            tier, latency, calibrated_at = _load_hardware_tier()
            gpu_available = tier not in ("cpu_only", "cpu_avx2")
            return HardwareStatusResponse(
                tier=tier,
                gpu_available=gpu_available,
                vram_gb=None,
                measured_latency_per_500_tokens=latency,
                calibrated_at=calibrated_at,
            )
    
    @app.get("/registry", response_model=RegistryResponse)
    async def get_registry() -> RegistryResponse:
        """Get model registry with verification status."""
        registry_status = loader.get_registry_status()
        models = []
        
        for model in registry_status.get("models", []):
            model_name = model.get("name")
            if not model_name:
                continue
            manifest_path = settings.registry_dir / f"{model_name}.yaml"
            if manifest_path.exists():
                try:
                    manifest = loader.load_manifest(manifest_path)
                    if manifest:
                        models.append(RegistryModel(
                            name=manifest.name,
                            version=manifest.version,
                            gguf_path=manifest.gguf_path,
                            sha256=manifest.sha256 if not manifest.is_checksum_placeholder() else None,
                            quant=manifest.quant,
                            context_length=manifest.context_length,
                            hardware_tier_min=manifest.hardware_tier_min.value if hasattr(manifest.hardware_tier_min, "value") else str(manifest.hardware_tier_min),
                            capability_vector=manifest.capability_vector.model_dump() if manifest.capability_vector else None,
                            verified=model.get("verified", False),
                            checksum_status=model.get("checksum_status", "unknown"),
                        ))
                except Exception as e:
                    # Log error but continue with other models
                    pass
        
        return RegistryResponse(
            models=models,
            total=len(models),
            verified_count=registry_status["verified_models"],
        )
    
    @app.post("/ingest/document", response_model=IngestResponse)
    async def ingest_document(
        file: UploadFile = File(...),
        user_id: str = Form(...),
        role: str = Form(...),
    ) -> IngestResponse:
        """Ingest a document (PDF, DOCX, TXT, CSV, MD, JSON) for extraction and indexing."""
        if not file.filename:
            raise HTTPException(status_code=400, detail={"error": "invalid_file", "message": "Filename is required"})

        filename_lower = file.filename.lower()
        supported_exts = (".pdf", ".docx", ".txt", ".md", ".json", ".csv", ".py", ".log", ".yaml", ".yml")
        if not any(filename_lower.endswith(ext) for ext in supported_exts):
            raise HTTPException(
                status_code=400,
                detail={"error": "unsupported_format", "message": f"Supported formats: {', '.join(supported_exts)}"},
            )

        doc_id = str(uuid.uuid4())
        upload_dir = workspace_root / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_bytes = await file.read()
        file_ext = Path(file.filename).suffix.lower()
        saved_file_path = upload_dir / f"{doc_id}{file_ext}"
        saved_file_path.write_bytes(file_bytes)

        audit_log.append(
            entry_type=AuditEntryType.AGENT_STEP,
            event_data={"action": "document_ingest", "filename": file.filename, "doc_id": doc_id},
            run_id=doc_id,
            user_id=user_id,
            role=role,
        )

        pages_processed = 1
        ocr_results: List[Dict[str, Any]] = []
        full_text = ""

        # PDF processing: try pypdf first for fast clean extraction
        if file_ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(saved_file_path))
                pages_processed = len(reader.pages)
                page_texts = []
                for idx, page in enumerate(reader.pages):
                    txt = page.extract_text() or ""
                    page_texts.append(txt)
                    ocr_results.append({
                        "page": idx + 1,
                        "text": txt[:500],
                        "confidence": 1.0 if txt.strip() else 0.0,
                    })
                full_text = "\n\n".join(page_texts)
            except Exception:
                pass

            # Fallback to OCR if pypdf got minimal or no text (scanned PDF)
            if not full_text.strip():
                try:
                    from swaraj.multimodal.ocr_pipeline import OCREngine
                    engine = OCREngine()
                    if engine.available:
                        result = engine.process_pdf(str(saved_file_path))
                        pages_processed = result.pages
                        ocr_results = [
                            {"page": b.page, "text": b.text, "confidence": b.confidence}
                            for b in result.blocks
                        ]
                        full_text = result.full_text
                except Exception:
                    pass

        # DOCX processing
        elif file_ext == ".docx":
            try:
                import docx
                doc = docx.Document(str(saved_file_path))
                paras = [p.text for p in doc.paragraphs if p.text.strip()]
                full_text = "\n\n".join(paras)
                pages_processed = max(1, len(paras) // 5)
                ocr_results = [{"page": 1, "text": full_text[:500], "confidence": 1.0}]
            except Exception:
                pass

        # Plain text, CSV, JSON, Markdown, Code
        else:
            try:
                full_text = file_bytes.decode("utf-8", errors="replace")
                pages_processed = max(1, len(full_text.splitlines()) // 50)
                ocr_results = [{"page": 1, "text": full_text[:500], "confidence": 1.0}]
            except Exception:
                pass

        # Save normalized extracted text for agent consumption
        extracted_txt_path = upload_dir / f"{doc_id}.txt"
        extracted_txt_path.write_text(full_text, encoding="utf-8")

        # Index into ChromaDB if available
        indexed = False
        try:
            from swaraj.tools.doc_search import DocumentSearchTool
            searcher = DocumentSearchTool(workspace_root=str(workspace_root))
            searcher.index_document(
                doc_id=doc_id,
                text=full_text,
                metadata={"filename": file.filename, "pages": pages_processed},
            )
            indexed = True
        except Exception:
            indexed = False

        return IngestResponse(
            document_id=doc_id,
            pages_processed=pages_processed,
            ocr_results=ocr_results,
            indexed=indexed,
            extracted_preview=full_text[:300].strip() if full_text else None,
            filename=file.filename,
        )
    
    def _execute_agent_run(
        run_id: str,
        request: AgentRunRequest,
    ) -> None:
        """Background task: execute the full agent graph and persist results."""
        from swaraj.agent.graph import AgentGraph
        from swaraj.agent.schemas import TaskInput, TaskType
        from swaraj.tools.fs_jail import FilesystemJail

        # Mark as running
        _run_store[run_id]["status"] = "running"
        _run_store[run_id]["current_state"] = "planning"

        try:
            jail = FilesystemJail(workspace_root=str(workspace_root))

            llm_runner = _get_llm_runner()

            graph = AgentGraph(
                rbac_manager=rbac_manager,
                filesystem_jail=jail,
                workspace_root=str(workspace_root),
                llm_runner=llm_runner,
            )

            # Resolve task type
            task_type = None
            raw_task_type = getattr(request, "task_type", None)
            if raw_task_type:
                try:
                    task_type = TaskType(raw_task_type)
                except ValueError:
                    pass
            if task_type is None:
                from swaraj.router.classifier import TaskClassifier
                characteristics = TaskClassifier().classify(request.task_description)
                if characteristics.code_required:
                    task_type = TaskType.CODE_GENERATION
                elif characteristics.summarization_required:
                    task_type = TaskType.SUMMARIZATION
                elif characteristics.structured_output_required:
                    task_type = TaskType.DATA_ANALYSIS
                else:
                    task_type = TaskType.DOCUMENT_GENERATION

            task_input = TaskInput(
                task_description=request.task_description,
                task_type=task_type,
                user_id=request.user_id,
                role=request.role,
                source_documents=request.source_documents or [],
                run_id=run_id,
            )

            state = graph.create_run(task_input)
            state = graph.plan(state)
            _run_store[run_id]["current_state"] = "pruning"
            state = graph.prune(state)

            # Act loop (max 4 iterations)
            for step_idx in range(len(state.plan.steps) if state.plan else 0):
                _run_store[run_id]["current_state"] = "acting"
                state = graph.act(state, step_idx)
                state = graph.observe(state)

            # Self-check loop
            _run_store[run_id]["current_state"] = "self_check"
            state = graph.self_check(state)
            while graph.should_regenerate(state):
                state = graph.self_check(state)

            # Determine final state
            can_cert, cert_reason = graph.can_certify(state)
            state.certificate_eligible = can_cert

            if state.current_state not in ("failed", "security_failed"):
                state.current_state = __import__("swaraj.agent.schemas", fromlist=["RunState"]).RunState.COMPLETED

            # Issue certificate if eligible
            if can_cert:
                try:
                    monitor_state = _get_or_create_monitor(run_id).state
                    egress_events = [
                        {
                            "timestamp": e.timestamp.isoformat(),
                            "address": e.address,
                            "is_forbidden": e.is_forbidden,
                        }
                        for e in monitor_state.events
                    ]
                    cert = cert_manager.sign_certificate(
                        run_id=run_id,
                        started_at=_run_store[run_id].get("started_at", datetime.utcnow().isoformat()),
                        ended_at=datetime.utcnow().isoformat(),
                        model_used=_run_store[run_id].get("model_used", "unknown"),
                        egress_events=egress_events,
                        hash_chain_head=audit_log._get_last_hash() or "genesis",
                        security_status="success",
                    )
                    cert_manager.save_certificate(cert, certs_dir)
                    _run_store[run_id]["certificate_issued"] = True
                    audit_log.append(
                        entry_type=AuditEntryType.CERTIFICATE_STATE,
                        event_data={"run_id": run_id, "action": "issued"},
                        run_id=run_id,
                        user_id=request.user_id,
                        role=request.role,
                        is_security_sensitive=True,
                    )
                except Exception as cert_err:
                    _run_store[run_id]["certificate_error"] = str(cert_err)

            # Persist final state snapshot
            _run_store[run_id].update({
                "status": state.current_state.value,
                "current_state": state.current_state.value,
                "plan": state.plan.model_dump() if state.plan else None,
                "rbac_results": [r.model_dump() for r in state.rbac_results],
                "invocations": [i.model_dump() for i in state.invocations],
                "observations": [o.model_dump() for o in state.observations],
                "self_check_results": [s.model_dump() for s in state.self_check_results],
                "iteration_count": state.iteration_count,
                "generated_artifacts": state.generated_artifacts,
                "approval_queue": state.approval_queue,
                "trace": state.trace,
                "certificate_eligible": state.certificate_eligible,
                "failure_reason": state.failure_reason,
                "security_failed": state.security_failed,
                "completed_at": datetime.utcnow().isoformat(),
            })

            audit_log.append(
                entry_type=AuditEntryType.RUN_END,
                event_data={"run_id": run_id, "final_state": state.current_state.value},
                run_id=run_id,
                user_id=request.user_id,
                role=request.role,
                is_security_sensitive=True,
            )

        except Exception as exc:
            _run_store[run_id].update({
                "status": "failed",
                "current_state": "failed",
                "failure_reason": str(exc),
                "completed_at": datetime.utcnow().isoformat(),
            })

    @app.post("/agent/run", response_model=AgentRunResponse)
    async def start_agent_run(
        request: AgentRunRequest,
        background_tasks: BackgroundTasks,
    ) -> AgentRunResponse:
        """Start an agent execution run."""
        run_id = str(uuid.uuid4())

        # Validate RBAC — use EXECUTE_TOOL as the closest available action
        rbac_result = rbac_manager.evaluate_action(
            action=Action.EXECUTE_TOOL,
            user_id=request.user_id,
            role=request.role,
            artifact=f"run:{run_id}",
        )

        if not rbac_result.authorized:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "rbac_denied",
                    "message": rbac_result.reason,
                    "approval_required": rbac_result.approval_required,
                },
            )

        # Determine selected model from router
        try:
            decision = router_engine.decide(
                task_description=request.task_description,
                task_type=request.task_type,
            )
            model_used = decision.selected_model or "unknown"
        except Exception:
            model_used = "unknown"

        # Seed the run store
        _run_store[run_id] = {
            "run_id": run_id,
            "task": request.task_description,
            "user_id": request.user_id,
            "role": request.role,
            "model_used": model_used,
            "status": "initialized",
            "current_state": "pending",
            "started_at": datetime.utcnow().isoformat(),
            "plan": None,
            "rbac_results": [],
            "invocations": [],
            "observations": [],
            "self_check_results": [],
            "iteration_count": 0,
            "generated_artifacts": [],
            "approval_queue": [],
            "trace": [],
            "certificate_eligible": False,
            "certificate_issued": False,
            "failure_reason": None,
            "security_failed": False,
            "completed_at": None,
        }

        # Log the run start
        audit_log.append(
            entry_type=AuditEntryType.RUN_START,
            event_data={"task_description": request.task_description, "model": model_used},
            run_id=run_id,
            user_id=request.user_id,
            role=request.role,
            is_security_sensitive=True,
        )

        # Initialize egress monitor for this run
        _get_or_create_monitor(run_id).start_monitoring(run_id)

        # Launch agent graph in background
        background_tasks.add_task(_execute_agent_run, run_id, request)

        return AgentRunResponse(
            run_id=run_id,
            status="running",
            initial_state=_run_store[run_id],
        )
    
    @app.get("/agent/trace/{run_id}", response_model=TraceResponse)
    async def get_agent_trace(run_id: str) -> TraceResponse:
        """Get agent execution trace for a run."""
        run = _run_store.get(run_id)
        if not run:
            raise HTTPException(
                status_code=404,
                detail={"error": "run_not_found", "message": f"Run {run_id} not found"},
            )

        # Resolve artifact content for inline chat display
        artifact_content = None
        artifact_filename = None
        artifacts = run.get("generated_artifacts", [])
        if artifacts:
            last_artifact = artifacts[-1]
            artifact_filename = Path(last_artifact).name
            candidate_paths = [
                Path(last_artifact),
                workspace_root / last_artifact,
                workspace_root / "artifacts" / artifact_filename,
                workspace_root / artifact_filename,
            ]
            for p in candidate_paths:
                if p.exists() and p.is_file():
                    try:
                        artifact_content = p.read_text(encoding="utf-8", errors="replace")
                        break
                    except Exception:
                        pass

        return TraceResponse(
            run_id=run_id,
            state={
                "status": run.get("status", "unknown"),
                "current_state": run.get("current_state", "unknown"),
                "model_used": run.get("model_used", "unknown"),
                "started_at": run.get("started_at"),
                "completed_at": run.get("completed_at"),
                "generated_artifacts": run.get("generated_artifacts", []),
                "security_failed": run.get("security_failed", False),
                "failure_reason": run.get("failure_reason"),
            },
            transitions=run.get("trace", []),
            iterations=run.get("iteration_count", 0),
            final_certificate_eligible=run.get("certificate_eligible", False),
            artifact_content=artifact_content,
            artifact_filename=artifact_filename,
            task_description=run.get("task"),
        )
    
    @app.get("/egress/status", response_model=EgressStatusResponse)
    async def get_egress_status(run_id: Optional[str] = None) -> EgressStatusResponse:
        """Get egress monitoring status."""
        # Get the most recent run if not specified
        if not run_id:
            # Active run tracking - implemented via egress monitor
            run_id = "unknown"
        
        state = _get_or_create_monitor(run_id).state
        
        events = []
        for event in state.events:
            ts = event.timestamp if isinstance(event.timestamp, str) else event.timestamp.isoformat()
            addr = event.remote_address or event.local_address or "127.0.0.1"
            port = event.remote_port or event.local_port or 0
            events.append(EgressEventResponse(
                run_id=run_id,
                timestamp=ts,
                address=addr,
                port=port,
                status=event.status,
                is_loopback=event.is_loopback,
                security_event=event.is_forbidden,
            ))
        
        return EgressStatusResponse(
            run_id=run_id,
            security_state=state.security_status.value,
            event_count=len(state.events),
            latest_heartbeat=state.last_poll_time,
            kill_switch_triggered=state.kill_switch_triggered,
            events=events,
        )
    
    @app.get("/egress/stream")
    async def egress_stream(run_id: str):
        """SSE endpoint for real-time egress monitoring.
        
        REQ-020: API Requirements - SSE for egress events
        REQ-057: Egress monitor emits heartbeats and security events
        """
        import asyncio
        
        async def event_generator():
            """Generate SSE events every 2 seconds."""
            last_event_count = 0
            while True:
                state = _get_or_create_monitor(run_id).state
                
                # Send full state as JSON
                data = {
                    "run_id": run_id,
                    "security_state": state.security_status.value,
                    "event_count": len(state.events),
                    "latest_heartbeat": state.last_poll_time,
                    "kill_switch_triggered": state.kill_switch_triggered,
                    "new_events": []
                }
                
                # Only send new events since last check
                for event in state.events[last_event_count:]:
                    ts = event.timestamp if isinstance(event.timestamp, str) else event.timestamp.isoformat()
                    addr = getattr(event, "remote_address", None) or getattr(event, "local_address", None) or getattr(event, "address", "127.0.0.1")
                    port = getattr(event, "remote_port", None) or getattr(event, "local_port", None) or getattr(event, "port", 0)
                    stat = getattr(event, "status", "clean")
                    loopback = getattr(event, "is_loopback", True)
                    sec_event = getattr(event, "is_forbidden", False) or getattr(event, "security_event", False)
                    data["new_events"].append({
                        "timestamp": ts,
                        "address": addr,
                        "port": port,
                        "status": stat,
                        "is_loopback": loopback,
                        "security_event": sec_event,
                    })
                
                last_event_count = len(state.events)
                
                yield f"data: {json.dumps(data)}\n\n"
                
                # Check if kill switch triggered - stop stream
                if state.kill_switch_triggered:
                    yield f"data: {json.dumps({'error': 'kill_switch_triggered'})}\n\n"
                    break
                
                await asyncio.sleep(2)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    @app.get("/agent/stream/{run_id}")
    async def agent_stream(run_id: str):
        """SSE endpoint for real-time agent trace updates.
        
        REQ-020: API Requirements - SSE for agent trace updates
        REQ-051: Agent graph represents every state transition in trace
        """
        import asyncio
        
        # Track last known state
        last_state: Optional[Dict[str, Any]] = None
        
        async def event_generator():
            """Generate SSE events for agent state changes from in-memory run store."""
            nonlocal last_state

            max_wait = 300  # 5 minutes
            elapsed = 0

            while elapsed < max_wait:
                run = _run_store.get(run_id)
                if run:
                    current_state = {
                        "run_id": run_id,
                        "status": run.get("status", "unknown"),
                        "current_state": run.get("current_state", "unknown"),
                        "iteration_count": run.get("iteration_count", 0),
                        "generated_artifacts": run.get("generated_artifacts", []),
                        "certificate_eligible": run.get("certificate_eligible", False),
                        "security_failed": run.get("security_failed", False),
                        "timestamp": datetime.utcnow().isoformat(),
                    }

                    if current_state != last_state:
                        yield f"data: {json.dumps(current_state)}\n\n"
                        last_state = current_state

                    # Stop streaming once terminal state reached
                    terminal = {"completed", "failed", "security_failed"}
                    if run.get("status") in terminal:
                        yield f"data: {json.dumps({'status': run.get('status'), 'run_id': run_id, 'done': True})}\n\n"
                        break
                else:
                    yield f"data: {json.dumps({'run_id': run_id, 'status': 'not_found'})}\n\n"

                await asyncio.sleep(2)
                elapsed += 2

            yield f"data: {json.dumps({'status': 'timeout', 'run_id': run_id})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    @app.get("/approvals", response_model=ApprovalsResponse)
    async def get_approvals() -> ApprovalsResponse:
        """Get pending approval requests."""
        pending = rbac_manager.get_approval_queue()
        
        items = []
        for req in pending:
            req_action = req.action.value if hasattr(req.action, "value") else str(req.action)
            req_time = req.requested_at.isoformat() if hasattr(req.requested_at, "isoformat") else str(req.requested_at)
            req_artifact = getattr(req, "artifact", None) or getattr(req, "resource", "")
            req_run_id = getattr(req, "run_id", None) or "run-pending"
            req_reason = getattr(req, "policy_reason", None) or getattr(req, "decision_reason", None) or f"Action '{req_action}' requires approval for role '{req.role}'"
            items.append(ApprovalItem(
                approval_id=req.approval_id,
                run_id=req_run_id,
                user_id=req.user_id,
                role=req.role,
                action=req_action,
                artifact=req_artifact,
                policy_reason=req_reason,
                requested_at=req_time,
            ))
        
        return ApprovalsResponse(pending=items, count=len(items))
    
    @app.post("/approvals/{approval_id}", response_model=Dict[str, Any])
    async def decide_approval(approval_id: str, request: ApprovalDecisionRequest) -> Dict[str, Any]:
        """Approve or deny an approval request."""
        result = rbac_manager.process_approval(
            approval_id=approval_id,
            approved=request.approved,
            reviewer_id=request.reviewer_id,
            comments=request.comments,
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail={"error": "approval_not_found", "message": f"Approval {approval_id} not found"},
            )
        
        return {
            "approval_id": approval_id,
            "approved": request.approved,
            "processed_at": datetime.utcnow().isoformat(),
            "reviewer_id": request.reviewer_id,
        }
    
    @app.get("/certificate/{run_id}", response_model=CertificateResponse)
    async def get_certificate(run_id: str) -> CertificateResponse:
        """Get certificate for a completed run."""
        cert = cert_manager.load_certificate(run_id, certs_dir)

        if not cert:
            raise HTTPException(
                status_code=404,
                detail={"error": "certificate_not_found", "message": f"Certificate for run {run_id} not found"},
            )

        verify_result = cert_manager.verify_certificate(cert)
        return CertificateResponse(
            run_id=cert.run_id,
            started_at=cert.started_at,
            ended_at=cert.ended_at,
            model_used=cert.model_used,
            egress_events=cert.egress_events,
            hash_chain_head=cert.hash_chain_head,
            signature=cert.signature,
            signer_pubkey=cert.signer_pubkey,
            verified=verify_result.valid,
        )
    
    @app.post("/certificate/verify", response_model=Dict[str, Any])
    async def verify_certificate_endpoint(request: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a certificate supplied as JSON dict or file path."""
        if "certificate" in request:
            cert_data = request["certificate"]
        elif "certificate_path" in request or "path" in request:
            cert_path = Path(request.get("certificate_path") or request.get("path"))
            if not cert_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail={"error": "file_not_found", "message": f"Certificate file not found: {cert_path}"},
                )
            cert_data = json.loads(cert_path.read_text(encoding="utf-8"))
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_request", "message": "Provide 'certificate' dict or 'certificate_path' string"},
            )

        result = cert_manager.verify_certificate_dict(cert_data)
        return {
            "verified": result.valid,
            "reason": result.reason,
            "checked_at": datetime.utcnow().isoformat(),
        }
    
    @app.get("/audit/events", response_model=AuditEventsResponse)
    async def get_audit_events(run_id: Optional[str] = None, limit: int = 100) -> AuditEventsResponse:
        """Get audit events."""
        # AuditLog exposes get_entries(); map kwargs accordingly
        entries = audit_log.get_entries(run_id=run_id, limit=limit)

        response_events = []
        for entry in entries:
            response_events.append(AuditEventResponse(
                id=entry["id"],
                run_id=entry.get("run_id", ""),
                user=entry.get("user_id"),
                role=entry.get("role"),
                timestamp=entry["timestamp"],
                event_type=entry["entry_type"],
                details=entry.get("event_data", {}),
                previous_hash=entry.get("previous_hash"),
            ))

        return AuditEventsResponse(events=response_events, count=len(response_events))
    
    @app.get("/artifact/{filename:path}")
    async def get_artifact_file(filename: str) -> FileResponse:
        """Download or view an artifact generated in workspace."""
        clean_name = Path(filename).name
        ws_resolved = str(workspace_root.resolve())
        candidate_paths = [
            (workspace_root / filename).resolve(),
            (workspace_root / "output" / clean_name).resolve(),
            (workspace_root / "artifacts" / clean_name).resolve(),
            (workspace_root / clean_name).resolve(),
        ]
        # Also search workspace_root recursively for the filename
        found_matches = list(workspace_root.rglob(clean_name))
        for m in found_matches:
            candidate_paths.append(m.resolve())

        for target in candidate_paths:
            if target.exists() and target.is_file() and str(target).startswith(ws_resolved):
                return FileResponse(str(target), filename=target.name)
        raise HTTPException(status_code=404, detail=f"Artifact '{filename}' not found")

    @app.get("/runs")
    async def list_runs(limit: int = 50) -> Dict[str, Any]:
        """List past runs for history/chat recall."""
        sorted_runs = sorted(
            _run_store.values(),
            key=lambda r: r.get("started_at") or "",
            reverse=True,
        )
        return {
            "runs": [
                {
                    "run_id": r.get("run_id"),
                    "task": r.get("task"),
                    "status": r.get("status"),
                    "started_at": r.get("started_at"),
                    "completed_at": r.get("completed_at"),
                    "model_used": r.get("model_used"),
                    "artifacts": r.get("generated_artifacts", []),
                }
                for r in sorted_runs[:limit]
            ],
            "total": len(_run_store),
        }

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request) -> Any:
        """SPA fallback: serve static files or index.html for client-side HTML routes."""
        if ui_dist_dir.exists():
            # Check for direct static file (e.g. favicon.ico, logo.png, robots.txt)
            target_file = ui_dist_dir / full_path
            if target_file.exists() and target_file.is_file():
                return FileResponse(str(target_file))
            # Fallback to index.html for SPA client-side routes
            if (ui_dist_dir / "index.html").exists():
                return FileResponse(str(ui_dist_dir / "index.html"))
        raise HTTPException(status_code=404, detail=f"Not Found: {full_path}")

    return app



app = create_app()


def main() -> None:
    """Entry point for running the server directly."""
    import uvicorn
    
    settings.validate_paths()
    
    uvicorn.run(
        "swaraj.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
    )


if __name__ == "__main__":
    main()
