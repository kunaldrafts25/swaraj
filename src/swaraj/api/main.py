"""SWARAJ v2 FastAPI application.

Provides health endpoint and router decision endpoint for Phase 1B.
Does not expose private keys, arbitrary filesystem access, or unrestricted subprocess execution.
"""

from typing import Any, Dict, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

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
    # TODO: Implement proper hardware detection in Phase 1C
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
    
    @app.get("/")
    async def root() -> Dict[str, str]:
        """Root endpoint with basic service information."""
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "health": "/health",
            "router": "/router/decide",
        }
    
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
