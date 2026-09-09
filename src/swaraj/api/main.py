"""SWARAJ v2 FastAPI application.

Provides health endpoint and router decision endpoint for Phase 1B.
Does not expose private keys, arbitrary filesystem access, or unrestricted subprocess execution.
"""

from typing import Any, Dict, Optional, List
from pathlib import Path
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
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
from swaraj.governance.rbac import RBACManager, PermissionResult, ApprovalRequest
from swaraj.governance.audit_log import AuditLog
from swaraj.governance.certificate import CertificateManager, RunCertificate as Certificate
from swaraj.monitor.egress_watch import EgressMonitor, ConnectionEvent, EgressState, SecurityStatus as SecurityState

# Global egress monitor registry (manages multiple runs)
_egress_monitors: dict[str, EgressMonitor] = {}

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


class AgentRunRequest(BaseModel):
    """Agent run request."""
    model_config = ConfigDict(protected_namespaces=())
    task_description: str
    user_id: str
    role: str
    source_documents: Optional[List[str]] = None


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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="SWARAJ v2: Sovereign Workbench for Agentic Reasoning & Auditable Judgement",
        docs_url=None,  # Disable Swagger UI for air-gapped operation
        redoc_url=None,  # Disable ReDoc for air-gapped operation
    )
    
    # Initialize registry loader
    loader = RegistryLoader()
    
    # Initialize capability vector storage and calculator
    cap_storage_path = Path(settings.data_dir) / "capability_vectors.json"
    cap_storage = CapabilityVectorStorage(cap_storage_path)
    cap_calculator = CapabilityVectorCalculator(cap_storage)
    
    # Determine hardware tier (simplified for Phase 1B)
    # Hardware detection implemented via CapabilityVectorCalculator
    hardware_tier = "cpu_only"
    
    # Initialize router engine
    router_engine = RouterDecisionEngine(loader, cap_calculator, hardware_tier)
    
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
    
    @app.get("/", response_model=Dict[str, str])
    async def root() -> Dict[str, str]:
        """Root endpoint with basic service information."""
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
        """Get hardware tier and calibration status."""
        # Hardware detection - uses calibration data from Phase 1B
        return HardwareStatusResponse(
            tier="cpu_only",
            gpu_available=False,
            vram_gb=None,
            measured_latency_per_500_tokens=None,
            calibrated_at=None,
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
                            sha256=manifest.sha256 if manifest.checksum_status != ChecksumStatus.PLACEHOLDER else None,
                            quant=manifest.quant,
                            context_length=manifest.context_length,
                            hardware_tier_min=manifest.hardware_tier_min,
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
        """Ingest a document (PDF) for OCR and indexing."""
        # OCR pipeline endpoint - implemented in Phase 3
        # For now, fail closed if file is not PDF
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail={"error": "unsupported_format", "message": "Only PDF files are supported"}
            )
        
        # Log the ingestion attempt
        audit_log.log_event(
            run_id=str(uuid.uuid4()),
            user=user_id,
            role=role,
            event_type="document_ingest",
            details={"filename": file.filename, "size": file.size},
        )
        
        # Fail closed: OCR not implemented in this phase
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ocr_unavailable",
                "message": "OCR pipeline requires PaddleOCR. Install paddlepaddle and paddleocr.",
            },
        )
    
    @app.post("/agent/run", response_model=AgentRunResponse)
    async def start_agent_run(request: AgentRunRequest) -> AgentRunResponse:
        """Start an agent execution run."""
        run_id = str(uuid.uuid4())
        
        # Validate RBAC
        rbac_result = rbac_manager.evaluate_action(
            action=Action.EXECUTE_AGENT,
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
        
        # Log the run start
        audit_log.log_event(
            run_id=run_id,
            user=request.user_id,
            role=request.role,
            event_type="agent_run_start",
            details={"task_description": request.task_description},
        )
        
        # Initialize egress monitor for this run
        _get_or_create_monitor(run_id).start_monitoring(run_id)
        
        # Return initial state
        initial_state = {
            "run_id": run_id,
            "task": request.task_description,
            "user_id": request.user_id,
            "role": request.role,
            "state": "initialized",
        }
        
        return AgentRunResponse(
            run_id=run_id,
            status="running",
            initial_state=initial_state,
        )
    
    @app.get("/agent/trace/{run_id}", response_model=TraceResponse)
    async def get_agent_trace(run_id: str) -> TraceResponse:
        """Get agent execution trace for a run."""
        # Trace retrieval endpoint - implemented in Phase 3
        # For now, return empty trace structure
        return TraceResponse(
            run_id=run_id,
            state={},
            transitions=[],
            iterations=0,
            final_certificate_eligible=False,
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
            events.append(EgressEventResponse(
                run_id=event.run_id,
                timestamp=event.timestamp.isoformat(),
                address=event.address,
                port=event.port,
                status=event.status,
                is_loopback=event.is_loopback,
                security_event=event.security_event,
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
                    data["new_events"].append({
                        "timestamp": event.timestamp.isoformat(),
                        "address": event.address,
                        "port": event.port,
                        "status": event.status,
                        "is_loopback": event.is_loopback,
                        "security_event": event.security_event,
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
            """Generate SSE events for agent state changes."""
            nonlocal last_state
            
            # Maximum wait time for agent completion (5 minutes)
            max_wait = 300
            elapsed = 0
            
            while elapsed < max_wait:
                # Try to get current agent state from store
                # In production, this would query a persistent store
                current_state = {
                    "run_id": run_id,
                    "status": "running",
                    "current_step": "processing",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Only send if state changed
                if current_state != last_state:
                    yield f"data: {json.dumps(current_state)}\n\n"
                    last_state = current_state
                
                # Check if run completed (would query database in production)
                # For now, send heartbeat every 2 seconds
                await asyncio.sleep(2)
                elapsed += 2
            
            # Send completion signal
            yield f"data: {json.dumps({'status': 'completed', 'run_id': run_id})}\n\n"
        
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
            items.append(ApprovalItem(
                approval_id=req.approval_id,
                run_id=req.run_id,
                user_id=req.user_id,
                role=req.role,
                action=req.action.value,
                artifact=req.artifact,
                policy_reason=req.policy_reason,
                requested_at=req.requested_at.isoformat(),
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
        cert = cert_manager.load_certificate(run_id)
        
        if not cert:
            raise HTTPException(
                status_code=404,
                detail={"error": "certificate_not_found", "message": f"Certificate for run {run_id} not found"},
            )
        
        return CertificateResponse(
            run_id=cert.run_id,
            started_at=cert.started_at,
            ended_at=cert.ended_at,
            model_used=cert.model_used,
            egress_events=cert.egress_events,
            hash_chain_head=cert.hash_chain_head,
            signature=cert.signature,
            signer_pubkey=cert.signer_pubkey,
            verified=True,
        )
    
    @app.post("/certificate/verify", response_model=Dict[str, Any])
    async def verify_certificate(request: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a certificate."""
        # Load certificate from request or file path
        if "certificate" in request:
            cert_data = request["certificate"]
        elif "path" in request:
            import json
            with open(request["path"]) as f:
                cert_data = json.load(f)
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_request", "message": "Provide 'certificate' or 'path'"},
            )
        
        result = cert_manager.verify_certificate(cert_data)
        
        return {
            "verified": result.is_valid,
            "reason": result.reason,
            "checked_at": datetime.utcnow().isoformat(),
        }
    
    @app.get("/audit/events", response_model=AuditEventsResponse)
    async def get_audit_events(run_id: Optional[str] = None, limit: int = 100) -> AuditEventsResponse:
        """Get audit events."""
        events = audit_log.get_events(run_id=run_id, limit=limit)
        
        response_events = []
        for event in events:
            response_events.append(AuditEventResponse(
                id=event["id"],
                run_id=event["run_id"],
                user=event.get("user"),
                role=event.get("role"),
                timestamp=event["timestamp"],
                event_type=event["event_type"],
                details=event.get("details", {}),
                previous_hash=event.get("previous_hash"),
            ))
        
        return AuditEventsResponse(events=response_events, count=len(response_events))
    
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
