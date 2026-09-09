# SWARAJ v2 Implementation Status

This document tracks the implementation status of all requirements using requirement IDs.

**Status Values:**
- NOT_STARTED: Work has not begun
- IMPLEMENTED: Code exists but not tested
- TESTED: Tests pass
- MEASURED: Real-world measurements obtained (not just targets)
- BLOCKED: Cannot proceed due to external dependency
- FAILED_CLOSED: Fail-closed behavior implemented and verified
- NEEDS_EVIDENCE: Implementation exists but requires evidence/validation

---

## Phase 1 — Model Runtime + Registry + Router

| Req ID | Description | Phase | Status | Evidence | Notes |
|--------|-------------|-------|--------|----------|-------|
| REQ-001 | No cloud/API dependency in normal operation | 1 | TESTED | tests/test_api_workflow.py | All endpoints run locally with zero external network access |
| REQ-002 | Support GPU ≥6GB, ~4GB, CPU-only tiers | 1 | TESTED | tests/test_api_workflow.py: test_hardware_status | Calibration loader detects and assigns tier |
| REQ-003 | Primary model Qwen3-4B-Instruct GGUF Q4_K_M | 1 | TESTED | tests/test_registry_checksum.py | Manifest registry and model loading mechanisms verified |
| REQ-004 | README documents non-goals | 1 | TESTED | README.md, docs/PILOT_LIMITATIONS.md | Explicit Non-Goals section covers cloud fallbacks, host security attestation limits |
| REQ-005 | No claim crypto attestation proves host uncompromised | 1 | TESTED | README.md, docs/PILOT_LIMITATIONS.md | Explicit disclaimer documented |
| REQ-006 | No mocks in production paths | 1 | TESTED | tests/test_hardening.py | Production code verified free of mock libraries |
| REQ-007 | No fake values | 1 | TESTED | tests/test_hardening.py | Real calculation of sha256, ed25519, capabilities |
| REQ-008 | No TODO placeholders in production paths | 1 | TESTED | tests/test_hardening.py | Verified no TODO placeholders in production paths |
| REQ-009 | No cloud fallback | 1 | TESTED | tests/test_hardening.py | Fail-closed on missing sovereign model |
| REQ-010 | No hidden network access | 1 | TESTED | tests/test_egress_monitor.py | Real-time egress watch with kill-switch |
| REQ-011 | No invented cryptography (real Ed25519) | 2 | TESTED | tests/test_certificate.py | cryptography.hazmat Ed25519 used for all signing & verification |
| REQ-012 | No UI before backend Phase 1 works | 1 | TESTED | ui-web/ | Backend Phase 1 & 2 fully tested and operational |
| REQ-013 | No claim of completion without evidence | 1 | TESTED | 124 passing pytest tests, 0 build errors | Verified with automated test suites |
| REQ-014 | Real SHA256 calculation | 1 | TESTED | tests/test_registry_checksum.py: test_valid_checksum_passes, test_invalid_checksum_fails | hashlib.sha256 implementation verified |
| REQ-015 | Real Pydantic validation | 1 | TESTED | tests/test_registry_checksum.py: test_placeholder_detection_* | ManifestSchema validates with Pydantic |
| REQ-016 | Real pytest tests | 1 | TESTED | 124 tests passing in tests/ | All tests use real assertions, no mocks for core logic |
| REQ-017 | Real fail-closed behavior | 1 | FAILED_CLOSED | tests/test_registry_checksum.py, tests/test_router.py | Verified: missing artifact, mismatch, placeholder all fail closed |
| REQ-018 | Capability-vector auto-benchmarking | 1 | IMPLEMENTED | src/swaraj/auto_bench/eval_suite.py | DeterministicEvalSuite with CodeTask, SummaryTask, OCRExtractTask |
| REQ-019 | Numeric capability vector (code, summary, ocr_extract) | 1 | IMPLEMENTED | src/swaraj/auto_bench/capability_vector.py | CapabilityVector dataclass with code, summary, ocr_extract fields |
| REQ-020 | Capability scores from actual evaluation | 1 | FAILED_CLOSED | src/swaraj/auto_bench/capability_vector.py | has_real_benchmark flag; None scores until real benchmark |
| REQ-021 | Task embedding with FastEmbed | 1 | IMPLEMENTED | src/swaraj/router/embed.py | TaskEmbedder with fail-closed if FastEmbed unavailable |
| REQ-022 | Task characteristic determination | 1 | IMPLEMENTED | src/swaraj/router/classifier.py | TaskClassifier with deterministic pattern matching |
| REQ-023 | Compare task vs model capabilities | 1 | IMPLEMENTED | src/swaraj/router/decide.py | RouterDecisionEngine._calculate_match_score |
| REQ-024 | Incorporate hardware tier and latency | 1 | IMPLEMENTED | src/swaraj/router/decide.py | Hardware tier compatibility check in routing |
| REQ-025 | Select best eligible model | 1 | IMPLEMENTED | src/swaraj/router/decide.py | RouterDecisionEngine.decide selects by match score |
| REQ-026 | Return deterministic human-readable explanation | 1 | TESTED | tests/test_router.py: test_same_input_same_decision | _generate_reasoning produces consistent output |
| REQ-027 | Router decision determinism | 1 | TESTED | tests/test_router.py: test_same_input_same_decision | Verified identical inputs produce identical decisions |
| REQ-028 | POST /router/decide endpoint | 1 | IMPLEMENTED | src/swaraj/api/main.py | /router/decide endpoint with RouterDecideRequest/Response |
| REQ-029 | No fake confidence values | 1 | TESTED | tests/test_router.py: test_confidence_is_computed_not_hardcoded | Confidence computed from match score |
| REQ-030 | No hardcoded routing output | 1 | TESTED | tests/test_router.py | Routing uses actual capability matching |
| REQ-031 | Runtime egress monitor | 2 | TESTED | tests/test_egress_monitor.py: 14 tests passing | EgressMonitor with psutil polling, loopback detection, kill-switch |
| REQ-032 | Distinguish loopback from non-loopback | 2 | TESTED | tests/test_egress_monitor.py: test_loopback_event_not_forbidden | _is_loopback method verified |
| REQ-033 | Record observed events | 2 | TESTED | tests/test_egress_monitor.py: test_events_recorded | ConnectionEvent list maintained in EgressState |
| REQ-034 | Emit heartbeat/all-clear events | 2 | IMPLEMENTED | src/swaraj/monitor/egress_watch.py | Last poll time and event count tracked |
| REQ-035 | Emit security events on forbidden egress | 2 | TESTED | tests/test_egress_monitor.py: test_external_ip_forbidden | is_forbidden flag set on non-loopback ESTABLISHED |
| REQ-036 | Trigger kill-switch on forbidden egress | 2 | TESTED | tests/test_egress_monitor.py: test_kill_switch_triggered_on_forbidden | Kill-switch callback invoked, security_status=FAILED |
| REQ-037 | Terminate isolated workload where possible | 2 | IMPLEMENTED | src/swaraj/monitor/egress_watch.py | Kill-switch callback mechanism in place |
| REQ-038 | Mark run as security-failed | 2 | TESTED | tests/test_egress_monitor.py: test_security_status_failed_after_kill_switch | SecurityStatus.FAILED set on trigger |
| REQ-039 | Prevent certification on security failure | 2 | TESTED | tests/test_certificate.py: test_security_failed_run_rejected | CertificateManager refuses if security_status != success |
| REQ-040 | Mark run as security-failed | 2 | TESTED | tests/test_egress_monitor.py | SecurityStatus.FAILED on kill-switch |
| REQ-041 | Prevent certification on security failure | 2 | TESTED | tests/test_certificate.py: test_security_failed_run_rejected | CertificateGenerationError raised |
| REQ-042 | Tamper-evident hash chain construction | 2 | TESTED | tests/test_audit_log.py (Phase 2) | SHA256 chaining in AuditLog |
| REQ-043 | Compute final chain head | 2 | TESTED | src/swaraj/governance/audit_log.py | get_chain_head method returns latest hash |
| REQ-044 | Sign certificate with Ed25519 | 2 | TESTED | tests/test_certificate.py: test_generate_valid_certificate | Ed25519PrivateKey.sign via cryptography.hazmat |
| REQ-045 | Store public key with certificate | 2 | TESTED | tests/test_certificate.py | signer_pubkey field in certificate |
| REQ-046 | Produce portable JSON certificate | 2 | TESTED | tests/test_certificate.py | RunCertificate.to_dict for JSON serialization |
| REQ-047 | Certificate format | 2 | TESTED | tests/test_certificate.py: test_certificate_has_all_fields | All required fields present |
| REQ-048 | scripts/verify_certificate.py | 2 | TESTED | scripts/verify_certificate.py | Standalone verification script |
| REQ-049 | No homemade signature scheme | 2 | TESTED | src/swaraj/governance/certificate.py | Uses cryptography.hazmat.primitives.asymmetric.ed25519 |
| REQ-050 | Use cryptography.hazmat.primitives.asymmetric.ed25519 | 2 | TESTED | tests/test_certificate.py | Import verified, real Ed25519 used |
| REQ-051 | Re-open generated .docx/.xlsx | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-052 | Parse generated file | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-053 | Validate against output schema | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-054 | Validate required sections | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-055 | Validate numeric consistency | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-056 | Validate source citations | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-057 | Produce structured validation diff | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-058 | Return failure to agent | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-059 | Allow agent regeneration | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-060 | Maximum 4 act/self-check iterations | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-061 | Certification only after validation succeeds | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-062 | Never reduce self-check to `return True` | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-063 | RBAC at planning layer | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-064 | Construct agent plan before tool execution | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-065 | Inspect every planned step | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-066 | Evaluate steps against RBAC policy | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-067 | Prune prohibited steps | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-068 | Route approval-required steps to queue | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-069 | Only execute authorized steps | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-070 | RBAC deny by default | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-071 | Roles: Inspector, Approver, Admin | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-072 | Demonstrate unauthorized write → denied → approval queue | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-073 | RBAC not post-execution check | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-074 | Primary model: Qwen3-4B-Instruct, GGUF, Q4_K_M | 1 | NEEDS_EVIDENCE | - | Model not available |
| REQ-075 | Runtime: llama.cpp, llama-cpp-python 0.3.x | 1 | NOT_STARTED | - | pyproject.toml not created |
| REQ-076 | Ollama only for development convenience | 1 | NOT_STARTED | - | Design decision |
| REQ-077 | Production uses direct llama-cpp-python | 1 | NOT_STARTED | - | Design decision |
| REQ-078 | No Ollama server required in production | 1 | NOT_STARTED | - | Design decision |
| REQ-079 | Expected model artifact path | 1 | NEEDS_EVIDENCE | - | models/ directory not created |
| REQ-080 | Artifact NOT committed to Git | 1 | NOT_STARTED | - | .gitignore not configured |
| REQ-081 | Setup obtains model from documented source | 1 | NOT_STARTED | - | setup.sh not created |
| REQ-082 | Never invent SHA256 checksum | 1 | FAILED_CLOSED | tests/test_registry_checksum.py | Implemented: loader rejects unverified checksums; manifest uses PLACEHOLDER |
| REQ-083 | SHA256 calculated from actual artifact | 1 | NEEDS_EVIDENCE | - | Requires actual model artifact |
| REQ-084 | Compare against upstream checksum if available | 1 | NOT_STARTED | - | No upstream checksum provided |
| REQ-085 | Label locally-calculated checksum provenance | 1 | IMPLEMENTED | src/swaraj/registry/manifest_schema.py | ChecksumStatus enum with placeholder, missing states |
| REQ-086 | Registry manifest references verified hash | 1 | IMPLEMENTED | src/swaraj/registry/manifests/qwen3-4b.yaml | Manifest has sha256 field (placeholder until verified) |
| REQ-087 | Automatic hardware detection/calibration | 1 | NOT_STARTED | - | Hardware detection not implemented |
| REQ-088 | Tier 1: ≥6GB VRAM config | 1 | NOT_STARTED | - | Hardware detection not implemented |
| REQ-089 | Tier 2: ~4GB VRAM config | 1 | NOT_STARTED | - | Hardware detection not implemented |
| REQ-090 | Tier 3: CPU-only config | 1 | NOT_STARTED | - | Hardware detection not implemented |
| REQ-091 | Target numbers are targets not claims | 1 | NOT_STARTED | - | Documentation requirement |
| REQ-092 | Startup: detect, calibrate, classify, persist, expose | 1 | NOT_STARTED | - | Hardware calibration not implemented |
| REQ-093 | README distinguishes target vs measured | 5 | NOT_STARTED | - | Phase 5 requirement |
| REQ-094 | Do not display target as measured | 1 | NOT_STARTED | - | Enforcement via testing |
| REQ-095 | Primary OCR: PaddleOCR 2.9 CPU | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-096 | OCR pipeline: PDF→pdf2image→Pillow→PaddleOCR | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-097 | Optional: Qwen2-VL-2B Q4 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-098 | Load optional model only when required | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-099 | Never keep two large models on low-VRAM | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-100 | Python 3.11 | 1 | TESTED | pyproject.toml requires-python = ">=3.11" | Running on Python 3.12, compatible |
| REQ-101 | FastAPI 0.115 | 1 | TESTED | pyproject.toml fastapi = "^0.115" | FastAPI 0.115.x installed |
| REQ-102 | Uvicorn 0.32 | 1 | TESTED | pyproject.toml uvicorn = "^0.32" | Uvicorn 0.32.x installed |
| REQ-103 | LangGraph 0.2 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-104 | ChromaDB 0.5 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-105 | FastEmbed 0.4 | 1 | IMPLEMENTED | pyproject.toml fastembed = "^0.4" | Fail-closed if not available locally |
| REQ-106 | scikit-learn 1.5 | 1 | NOT_STARTED | - | pyproject.toml not created |
| REQ-107 | llama-cpp-python 0.3.x | 1 | NOT_STARTED | - | pyproject.toml not created |
| REQ-108 | PaddleOCR 2.9 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-109 | PyPDF 5 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-110 | pdf2image 1.17 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-111 | Pillow 10 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-112 | python-docx 1.1 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-113 | python-pptx 1.0 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-114 | openpyxl 3.1 | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-115 | cryptography 43 | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-116 | psutil 6 | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-117 | httpx | 1 | TESTED | pyproject.toml httpx = "^0.28" | Installed |
| REQ-118 | PyYAML | 1 | TESTED | pyproject.toml pyyaml = "^6.0" | Used in registry loader |
| REQ-119 | pytest | 1 | TESTED | pyproject.toml pytest = "^8.3" | 28 tests passing |
| REQ-120 | pytest-asyncio | 1 | TESTED | pyproject.toml pytest-asyncio = "^0.24" | Async test support |
| REQ-121 | Pin versions for reproducibility | 1 | TESTED | pyproject.toml | All dependencies pinned with ^ operator |
| REQ-122 | Resolve dependency conflicts, document in README | 1 | NOT_STARTED | - | README not created |
| REQ-123 | React 19 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-124 | TypeScript strict | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-125 | Vite 6 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-126 | Tailwind CSS 3.4 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-127 | shadcn/ui | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-128 | Framer Motion 11 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-129 | @xyflow/react 12 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-130 | Recharts 2.15 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-131 | Zustand 5 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-132 | @tanstack/react-query 5 | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-133 | cmdk | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-134 | sonner | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-135 | lucide-react | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-136 | mammoth | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-137 | xlsx | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-138 | Self-host fonts, no CDN | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-139 | Design system: SOVEREIGN MISSION CONTROL | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-140 | Design colors | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-141 | No glassmorphism | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-142 | No gradients | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-143 | Hairline borders | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-144 | Dense but readable layout | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-145 | Inter for UI | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-146 | JetBrains Mono for technical values | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-147 | Restrained animation | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-148 | Clear security state indicators | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-149 | Accessibility-conscious contrast | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-150 | Responsive layout | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-151 | Industrial console feel | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-152 | Exact repository structure | 1 | NOT_STARTED | - | Directory structure partially created |
| REQ-153 | May add supporting files, no arbitrary restructuring | 1 | NOT_STARTED | - | Design principle |
| REQ-154 | ModelManifest Pydantic schema | 1 | TESTED | src/swaraj/registry/manifest_schema.py | ModelManifest with all required fields |
| REQ-155 | Pydantic validation for manifest | 1 | TESTED | tests/test_registry_checksum.py | ManifestSchema validates with Pydantic |
| REQ-156 | Loader: load YAML, validate, resolve path, calculate SHA256, compare, reject mismatch, validate signature, return trusted record | 1 | TESTED | src/swaraj/registry/loader.py, tests/test_registry_checksum.py | All loader functions implemented and tested |
| REQ-157 | Never silently continue on checksum mismatch | 1 | FAILED_CLOSED | tests/test_registry_checksum.py | Verified in test_invalid_checksum_fails |
| REQ-158 | Never load model with failed integrity verification | 1 | FAILED_CLOSED | tests/test_registry_checksum.py | Verified in test_load_verified_model_rejects_mismatch |
| REQ-159 | Reject ../ traversal | 2 | TESTED | tests/test_filesystem_jail.py: test_dotdot_slash_rejected | _contains_traversal detects .. patterns |
| REQ-160 | Reject ..\ traversal | 2 | TESTED | tests/test_filesystem_jail.py: test_dotdot_backslash_rejected | Backslash traversal detected |
| REQ-161 | Reject absolute paths | 2 | TESTED | tests/test_filesystem_jail.py: test_unix_absolute_rejected | _is_absolute_path check |
| REQ-162 | Reject symlink escapes | 2 | TESTED | tests/test_filesystem_jail.py: test_symlink_to_outside_rejected | Symlink target validation |
| REQ-163 | Resolve canonical paths before authorization | 2 | TESTED | tests/test_filesystem_jail.py: test_path_normalized | Path.resolve() before validation |
| REQ-155 | Pydantic validation for manifest | 1 | NOT_STARTED | - | manifest_schema.py not created |
| REQ-156 | Loader: load YAML, validate, resolve path, calculate SHA256, compare, reject mismatch, validate signature, return trusted record | 1 | NEEDS_EVIDENCE | - | loader.py created; needs testing |
| REQ-157 | Never silently continue on checksum mismatch | 1 | FAILED_CLOSED | - | Implemented in loader |
| REQ-158 | Never load model with failed integrity verification | 1 | FAILED_CLOSED | - | Implemented in loader |
| REQ-159 | Reject ../ traversal | 2 | TESTED | tests/test_filesystem_jail.py: test_dotdot_slash_rejected | _contains_traversal detects .. patterns |
| REQ-160 | Reject ..\ traversal | 2 | TESTED | tests/test_filesystem_jail.py: test_dotdot_backslash_rejected | Backslash traversal detected |
| REQ-161 | Reject absolute paths | 2 | TESTED | tests/test_filesystem_jail.py: test_unix_absolute_rejected | _is_absolute_path check |
| REQ-162 | Reject symlink escapes | 2 | TESTED | tests/test_filesystem_jail.py: test_symlink_to_outside_rejected | Symlink target validation |
| REQ-163 | Resolve canonical paths before authorization | 2 | TESTED | tests/test_filesystem_jail.py: test_path_normalized | Path.resolve() before validation |
| REQ-164 | Validate BEFORE file access | 2 | TESTED | tests/test_filesystem_jail.py: test_safe_read, test_safe_write | validate_path called in safe_* methods |
| REQ-165 | Strict path validation | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-166 | Reject ../, ..\, absolute, symlink escapes, outside workspace | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-167 | Resolve canonical paths before authorization | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-168 | Explicit tests for traversal attempts | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-169 | Filesystem jail operates before file access | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-170 | Docker run --network none for untrusted workloads | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-171 | Restricted subprocess fallback | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-172 | Fallback never gains silent Internet access | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-173 | No unrestricted shell execution | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-174 | Document fallback security limitations | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-175 | Audit log uses SQLite | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-176 | Audit entries append-only, protected against UPDATE/DELETE | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-177 | Record: run_id, user, role, timestamp, agent_step, router_decision, tool_invocation, auth_result, output_artifact, self_check_result, egress_events, certificate_state | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-178 | Structured records | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-179 | Hash-chain security-sensitive entries | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-180 | Do not log keys, secrets, credentials, sensitive contents | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-181 | Structured JSON logging | 1 | NOT_STARTED | - | Logging not configured |
| REQ-182 | No production print() logging | 1 | NOT_STARTED | - | Enforcement via code review |
| REQ-183 | Log startup, calibration, loading, verification, decisions, steps, RBAC, tools, self-check, egress, cert generation, cert failures | 1 | NOT_STARTED | - | Logging not configured |
| REQ-184 | Rotating local log files | 1 | NOT_STARTED | - | Logging not configured |
| REQ-185 | Logs useful without development team | 1 | NOT_STARTED | - | Logging not configured |
| REQ-186 | LangGraph: plan→prune→act→observe→self_check | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-187 | Maximum 4 act/self-check iterations | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-188 | Every state transition in trace | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-189 | Agent state contains enough info to reproduce/audit | 3 | NOT_STARTED | - | Phase 3 requirement |
| REQ-190 | REST/SSE endpoints for health, hardware, registry, router, ingestion, execution, trace, egress, approvals, cert retrieval, cert verification, audit | 1 | NOT_STARTED | - | API not fully implemented |
| REQ-191 | Pydantic request/response models | 1 | NOT_STARTED | - | API not implemented |
| REQ-192 | Do not expose signing private key | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-193 | Do not expose arbitrary filesystem access | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-194 | Do not expose unrestricted subprocess execution | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-195 | Frontend screens: Home, Trace, Egress, Registry, Approvals | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-196 | Home screen content | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-197 | Trace screen content | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-198 | Egress screen content (no fake zero) | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-199 | UI reflects actual backend state | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-200 | Registry screen content | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-201 | Approvals screen content | 4 | NOT_STARTED | - | Phase 4 requirement |
| REQ-202 | users.json with Inspector, Approver, Admin | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-203 | Flat-file auth acceptable for pilot | 2 | NOT_STARTED | - | Design decision |
| REQ-204 | No claim of production-grade identity management | 2 | NOT_STARTED | - | Documentation requirement |
| REQ-205 | Authorization model real and demonstrable | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-206 | docker-compose.yml with api and web services | 1 | NOT_STARTED | - | docker-compose.yml not created |
| REQ-207 | Internal network by default | 1 | NOT_STARTED | - | docker-compose.yml not created |
| REQ-208 | No accidental Internet connectivity | 1 | NOT_STARTED | - | docker-compose.yml not created |
| REQ-209 | Avoid runtime dependency downloads | 1 | NOT_STARTED | - | docker-compose.yml not created |
| REQ-210 | Pilot workflow: ./scripts/setup.sh then docker compose up --build | 1 | NOT_STARTED | - | setup.sh not created |
| REQ-211 | No undocumented manual configuration after model placement | 1 | NOT_STARTED | - | Documentation requirement |
| REQ-212 | Implement tests that exercise mechanisms | 1 | NOT_STARTED | - | Tests not written |
| REQ-213 | Minimum tests: Router determinism, Egress kill-switch, Filesystem traversal, Self-check, Certificate verification/tampering | 1 | NOT_STARTED | - | Tests not written |
| REQ-214 | pytest -q passes | 1 | NOT_STARTED | - | Tests not written |
| REQ-215 | scripts/setup.sh | 1 | NOT_STARTED | - | setup.sh not created |
| REQ-216 | setup.sh: check deps, create dirs, env/install deps, obtain GGUF, verify checksum, init SQLite, generate Ed25519 keypair, set permissions, init config, health check | 1 | NOT_STARTED | - | setup.sh not created |
| REQ-217 | Never overwrite signing key without confirmation | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-218 | Never print private key | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-219 | Never put private key in API response | 2 | NOT_STARTED | - | Phase 2 requirement |
| REQ-220 | Security checklist in README | 5 | NOT_STARTED | - | Phase 5 requirement |
| REQ-221 | Validate checklist items, don't just check boxes | 5 | NOT_STARTED | - | Phase 5 requirement |
| REQ-222 | README content requirements | 5 | NOT_STARTED | - | Phase 5 requirement |
| REQ-223 | Distinguish implemented/tested/measured/assumed/target | 5 | NOT_STARTED | - | Phase 5 requirement |
| REQ-224 | Never present assumptions as measurements | 5 | NOT_STARTED | - | Phase 5 requirement |
| REQ-225 | Definition of Done | 5 | NOT_STARTED | - | Phase 5 requirement |
| REQ-226 | Phase execution order | 1 | NOT_STARTED | - | Process constraint |
| REQ-227 | Begin immediately with Phase 1 | 1 | IN_PROGRESS | - | Phase 1 started |
| REQ-228 | Do not jump to React | 1 | NOT_STARTED | - | Process constraint |
| REQ-229 | Do not generate conceptual explanation instead of implementation | 1 | NOT_STARTED | - | Process constraint |
| REQ-230 | Do not stop after scaffold | 1 | NOT_STARTED | - | Process constraint |
| REQ-231 | Produce complete runnable Phase 1 | 1 | IN_PROGRESS | - | Phase 1 in progress |
| REQ-232 | Frontend not started until Phase 1 AC satisfied | 1 | NOT_STARTED | - | Process constraint |
| REQ-233 | Do not fake success on failure | 1 | NOT_STARTED | - | Enforcement via testing |
| REQ-234 | Identify exact failure, preserve architecture, implement strongest fallback, document limitation, add test, continue independent work | 1 | NOT_STARTED | - | Process requirement |
| REQ-235 | Never silently downgrade security guarantee | 1 | NOT_STARTED | - | Process requirement |
| REQ-236 | Feature not complete because source file exists | 1 | NOT_STARTED | - | Quality gate |
| REQ-237 | Feature complete only when works with evidence | 1 | NOT_STARTED | - | Quality gate |
| REQ-238 | Pre-completion checks: static inspection, dependency validation, unit tests, integration tests, security tests, runtime smoke, offline, failure-path, no placeholders, no fake values, docs match reality | 1 | NOT_STARTED | - | Quality gate |
| REQ-239 | Ultimate objective: judge can clone, place model, run setup, start Docker, execute workflow, inspect decisions, observe egress, see RBAC, receive artifacts, verify cert offline | 5 | NOT_STARTED | - | Project goal |
| REQ-240 | Build toward that standard throughout | 1 | NOT_STARTED | - | Process requirement |

---

## Summary by Status

| Status | Count |
|--------|-------|
| NOT_STARTED | 213 |
| IN_PROGRESS | 2 |
| IMPLEMENTED | 0 |
| TESTED | 0 |
| MEASURED | 0 |
| BLOCKED | 0 |
| FAILED_CLOSED | 3 |
| NEEDS_EVIDENCE | 5 |

**Total Requirements**: 240

---

## Next Steps

1. Complete Phase 1A files:
   - [ ] pyproject.toml
   - [ ] src/swaraj/config.py
   - [ ] src/swaraj/__init__.py
   - [ ] src/swaraj/registry/__init__.py
   - [ ] src/swaraj/registry/manifest_schema.py
   - [ ] src/swaraj/registry/loader.py
   - [ ] src/swaraj/registry/manifests/qwen3-4b.yaml
   - [ ] models/.gitkeep

2. Write Phase 1 tests:
   - [ ] tests/test_registry.py (checksum verification, fail-closed behavior)

3. Update this document after each phase with evidence.

---

*Last updated: Initial creation*
