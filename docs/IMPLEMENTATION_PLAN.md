# SWARAJ v2 Implementation Plan

## Phase Execution Order (REQ-226)

1. Phase 1 — Model Runtime + Registry + Router
2. Phase 2 — Governance + Security + Tools
3. Phase 3 — Agent + Multimodal + API
4. Phase 4 — Frontend
5. Phase 5 — Pilot Hardening

**Critical Constraint (REQ-232)**: Frontend must not be started until backend Phase 1 acceptance criteria are satisfied.

---

## Phase 1 — Model Runtime + Registry + Router

### Objective
Establish the foundational model runtime, registry with checksum verification, and explainable routing mechanism.

### Files to Create

#### Phase 1A — Registry Bootstrap
1. `pyproject.toml` - Project dependencies and configuration
2. `src/swaraj/config.py` - Configuration management
3. `src/swaraj/__init__.py` - Package initialization
4. `src/swaraj/registry/__init__.py` - Registry package
5. `src/swaraj/registry/manifest_schema.py` - Pydantic ModelManifest schema
6. `src/swaraj/registry/loader.py` - Model loader with checksum verification
7. `src/swaraj/registry/manifests/qwen3-4b.yaml` - Qwen3-4B model manifest (SHA256 calculated from actual artifact)
8. `models/.gitkeep` - Ensure models directory exists (artifact not committed)

#### Phase 1B — Auto-Benchmark + Router
9. `src/swaraj/auto_bench/__init__.py` - Auto-bench package
10. `src/swaraj/auto_bench/eval_suite.py` - Deterministic evaluation suite
11. `src/swaraj/auto_bench/capability_vector.py` - Capability vector computation
12. `src/swaraj/router/__init__.py` - Router package
13. `src/swaraj/router/embed.py` - FastEmbed task embedding
14. `src/swaraj/router/classifier.py` - Task classifier
15. `src/swaraj/router/decide.py` - Routing decision logic
16. `src/swaraj/api/__init__.py` - API package
17. `src/swaraj/api/main.py` - FastAPI application with /router/decide endpoint

#### Supporting Files
18. `policies/rbac_policy.json` - RBAC policy (initial structure)
19. `tests/test_registry.py` - Registry checksum verification tests
20. `tests/test_router.py` - Router determinism tests

### Dependencies
- Python 3.11+
- pydantic
- pyyaml
- llama-cpp-python
- fastapi
- uvicorn
- fastembed
- scikit-learn
- pytest
- pytest-asyncio

### Required Tests
1. **Registry Tests**:
   - Model manifest loads and validates via Pydantic
   - SHA256 mismatch causes rejection (fail-closed)
   - Missing model artifact causes fail-closed behavior
   - Loader refuses to load unverified models

2. **Router Tests**:
   - Same task + same registry/calibration state → same decision (determinism)
   - Router returns required fields: selected_model, confidence, reasoning, capability_scores, hardware_tier
   - No hardcoded/fake confidence values

### Acceptance Criteria
- [ ] Model registry loads YAML manifests with Pydantic validation
- [ ] SHA256 checksum is calculated from actual model artifact
- [ ] Checksum mismatch causes immediate rejection (no silent continue)
- [ ] Missing model artifact causes fail-closed behavior
- [ ] POST /router/decide endpoint returns real explainable routing decisions
- [ ] Router decisions are deterministic for identical inputs
- [ ] Hardware tier detection/calibration implemented
- [ ] Capability vector is computed from actual evaluation, not hardcoded

### Exit Criteria
- All Phase 1 files created
- All Phase 1 tests pass (pytest -q)
- POST /router/decide returns valid response with actual model and hardware state
- No TODO placeholders in production paths
- No fake values in any output

### Evidence Required
- pytest output showing passing tests
- curl/httpx response from POST /router/decide with real values
- IMPLEMENTATION_STATUS.md updated with TESTED status for Phase 1 requirements

### Known Risks
- Model artifact may not be available during development
- GPU detection may fail on certain hardware configurations
- llama-cpp-python compilation issues on some systems

### Fail-Closed Behavior
- If model artifact is missing: registry loader raises exception, application cannot load unverified model
- If SHA256 mismatches: loader rejects model, logs security event
- If GPU detection fails: default to CPU-only tier (Tier 3)
- If calibration inference fails: use conservative CPU configuration

---

## Phase 2 — Governance + Security + Tools

### Objective
Implement RBAC, audit logging, egress monitoring, certificate generation, filesystem jail, and sandbox execution.

### Files to Create
1. `src/swaraj/governance/__init__.py`
2. `src/swaraj/governance/rbac.py` - RBAC enforcement at planning layer
3. `src/swaraj/governance/audit_log.py` - SQLite append-only audit log
4. `src/swaraj/governance/certificate.py` - Ed25519 certificate generation
5. `src/swaraj/monitor/__init__.py`
6. `src/swaraj/monitor/egress_watch.py` - Network state polling, kill-switch
7. `src/swaraj/tools/__init__.py`
8. `src/swaraj/tools/fs_jail.py` - Filesystem path validation
9. `src/swaraj/tools/sandbox_exec.py` - Docker/subprocess sandbox
10. `src/swaraj/tools/xlsx_writer.py` - Excel writer with self-check
11. `src/swaraj/tools/docx_writer.py` - Word writer with self-check
12. `src/swaraj/tools/calc_trace.py` - Calculator with trace
13. `src/swaraj/tools/doc_search.py` - Document search tool
14. `scripts/verify_certificate.py` - Independent certificate verification
15. `tests/test_egress_monitor.py` - Egress detection tests
16. `tests/test_self_check.py` - Document self-check tests
17. `tests/test_certificate.py` - Certificate verification/tampering tests
18. `policies/users.json` - Pilot users (Inspector, Approver, Admin)

### Dependencies
- cryptography (Ed25519)
- psutil
- sqlite3 (stdlib)
- python-docx
- openpyxl

### Required Tests
1. **Egress Monitor Tests**:
   - Controlled external connection attempt detected
   - Security event generated
   - Kill-switch triggered
   - Run marked as security-failed
   - Certification prevented

2. **Filesystem Jail Tests**:
   - ../ traversal rejected
   - ..\ traversal rejected
   - Absolute paths rejected
   - Symlink escapes rejected

3. **Self-Check Tests**:
   - Malformed .docx detected
   - Structured validation diff generated
   - Regeneration path activated

4. **Certificate Tests**:
   - Valid certificate verifies successfully
   - Tampered hash chain → verification failure
   - Tampered payload → verification failure
   - Invalid signature → verification failure

5. **RBAC Tests**:
   - Deny by default behavior
   - Unauthorized write → denied → approval queue
   - Approved action executes successfully

### Acceptance Criteria
- [ ] Egress monitor polls network state every ~2 seconds
- [ ] Non-loopback connections trigger kill-switch
- [ ] Certificate uses real Ed25519 signatures
- [ ] verify_certificate.py independently verifies certificates
- [ ] Filesystem jail rejects all traversal attempts
- [ ] RBAC operates at planning layer (prune before execute)
- [ ] Audit log is append-only at application level
- [ ] Self-check produces structured validation diffs

### Exit Criteria
- All Phase 2 files created
- All Phase 2 tests pass
- Certificate verification succeeds on valid certificate
- Certificate verification fails on tampered certificate
- Egress kill-switch test passes
- Filesystem traversal tests pass
- RBAC unauthorized write reaches approval queue

### Evidence Required
- pytest output for all Phase 2 tests
- verify_certificate.py exit code 0 on valid cert, non-zero on tampered
- IMPLEMENTATION_STATUS.md updated

### Known Risks
- Docker may not be available in all environments
- psutil behavior may vary across OS
- Ed25519 key generation requires secure randomness

### Fail-Closed Behavior
- If Docker unavailable: use restricted subprocess fallback with documented limitations
- If egress monitor detects anomaly: terminate workload, prevent certification
- If RBAC check fails: deny action, route to approval queue if applicable
- If certificate generation fails: run cannot be certified

---

## Phase 3 — Agent + Multimodal + API

### Objective
Implement the full agent graph, OCR pipeline, and complete API surface.

### Files to Create
1. `src/swaraj/multimodal/__init__.py`
2. `src/swaraj/multimodal/ocr_pipeline.py` - PDF → OCR pipeline
3. `src/swaraj/agent/__init__.py`
4. `src/swaraj/agent/graph.py` - LangGraph agent implementation
5. `src/swaraj/agent/schemas.py` - Agent state schemas
6. `src/swaraj/api/main.py` - Complete API with all endpoints

### Dependencies
- langgraph
- paddleocr
- pdf2image
- pillow
- pypdf

### Required Tests
- Agent graph executes plan → prune → act → observe → self_check cycle
- Maximum 4 act/self-check iterations enforced
- OCR pipeline processes PDF to structured text
- All API endpoints return valid responses

### Acceptance Criteria
- [ ] Agent graph implements required state machine
- [ ] Self-check iteration limit enforced
- [ ] OCR pipeline works on CPU
- [ ] All API endpoints functional
- [ ] End-to-end workflow runs CPU-only

### Exit Criteria
- Full workflow: document ingestion → OCR → agent reasoning → structured output → self-check → certificate
- All integration tests pass
- CPU-only execution verified

### Evidence Required
- End-to-end workflow execution log
- Generated artifacts (.docx, .xlsx)
- Certificate for successful run
- IMPLEMENTATION_STATUS.md updated

### Known Risks
- PaddleOCR CPU performance
- Memory constraints on low-VRAM systems
- LangGraph state management complexity

### Fail-Closed Behavior
- If OCR fails: return structured error, do not proceed with invalid input
- If agent exceeds iteration limit: terminate with validation failure
- If tool execution fails: capture error in trace, allow agent to recover or fail gracefully

---

## Phase 4 — Frontend

### Prerequisite
**DO NOT START** until Phase 1, 2, and 3 acceptance criteria are fully satisfied and evidenced.

### Objective
Build industrial console UI reflecting actual backend state.

### Files to Create
1. `ui-web/package.json`
2. `ui-web/vite.config.ts`
3. `ui-web/tailwind.config.ts`
4. `ui-web/tsconfig.json`
5. `ui-web/src/lib/api.ts`
6. `ui-web/src/hooks/useAgentStream.ts`
7. `ui-web/src/hooks/useConnectionStatus.ts`
8. `ui-web/src/store/useAppStore.ts`
9. `ui-web/src/store/useTraceStore.ts`
10. `ui-web/src/components/shell/Sidebar.tsx`
11. `ui-web/src/components/shell/TopBar.tsx`
12. `ui-web/src/components/shell/StatusBar.tsx`
13. `ui-web/src/pages/Home.tsx`
14. `ui-web/src/pages/Trace.tsx`
15. `ui-web/src/pages/Egress.tsx`
16. `ui-web/src/pages/Registry.tsx`
17. `ui-web/src/pages/Approvals.tsx`

### Dependencies
- React 19
- TypeScript strict
- Vite 6
- Tailwind CSS 3.4
- shadcn/ui
- Framer Motion 11
- @xyflow/react 12
- Recharts 2.15
- Zustand 5
- @tanstack/react-query 5
- cmdk
- sonner
- lucide-react
- mammoth
- xlsx

### Acceptance Criteria
- [ ] Home shows real backend state (task input, selected model, routing explanation, hardware tier, execution status, artifacts, certificate status)
- [ ] Trace shows plan, RBAC pruning, executed tools, observations, self-check iterations, certificate state
- [ ] Egress shows live egress status, event count, connection events, heartbeats, security status, run ID (no fake zeros)
- [ ] Registry shows installed models, versions, quantization, SHA256, capability vector, hardware requirements, benchmark results
- [ ] Approvals shows pending requests, user, role, requested action, artifact, policy reason, approve/deny controls
- [ ] UI reflects actual backend state (no hardcoded values)
- [ ] Design system: SOVEREIGN MISSION CONTROL colors, Inter/JetBrains Mono fonts self-hosted

### Exit Criteria
- All screens implemented
- All UI values sourced from backend API
- No hardcoded/fake values
- Design system compliance verified

### Evidence Required
- Screenshots of each page with real data
- Network inspection showing API calls
- IMPLEMENTATION_STATUS.md updated

### Known Risks
- Font self-hosting complexity
- SSE stream handling in React
- State synchronization between components

### Fail-Closed Behavior
- If backend unavailable: show error state, do not display stale/fake data
- If API returns error: display error message, maintain security state indicators

---

## Phase 5 — Pilot Hardening

### Objective
Run all Definition-of-Done items, fix failures, repeat until all pass.

### Activities
1. Execute all Definition-of-Done checklist items (REQ-225)
2. Fix any failures discovered
3. Re-run tests after fixes
4. Update README with measured benchmark results
5. Verify security checklist items (REQ-220)
6. Perform offline verification test
7. Document pilot limitations

### Definition of Done Verification
- [ ] End-to-end workflow runs CPU-only with configuration only
- [ ] GPU execution works where supported
- [ ] Model integrity is verified before loading
- [ ] Router returns real explainable routing decisions
- [ ] Hardware tier is detected/calibrated
- [ ] Four core pytest suites pass
- [ ] Filesystem traversal tests pass
- [ ] Egress kill-switch test passes
- [ ] Self-check rejects malformed documents
- [ ] Certificate verification succeeds
- [ ] Certificate tampering test fails correctly
- [ ] Approval note can be verified on another offline machine
- [ ] RBAC unauthorized write reaches Approvals queue
- [ ] Signing private key never leaves local storage
- [ ] Docker network has no normal external egress
- [ ] Structured rotating logs work
- [ ] README contains measured hardware results
- [ ] No TODOs/placeholders/mocks remain in production paths

### Evidence Required
- Complete pytest output
- Certificate verification on separate offline machine
- Security checklist with validated items
- README with measured (not target) benchmark results
- IMPLEMENTATION_STATUS.md showing all requirements MEASURED or TESTED

### Exit Criteria
- All Definition-of-Done items satisfied
- All security checklist items validated
- Pilot-ready declaration justified by evidence

---

## Cross-Phase Constraints

1. **No Fake Values**: Never hardcode confidence scores, hashes, benchmark results, or egress states (REQ-007, REQ-029, REQ-030, REQ-163, REQ-164, REQ-198).

2. **Fail-Closed Default**: When environment limitations exist, implement strongest real fallback and document limitation (REQ-234, REQ-235).

3. **Evidence Before Completion**: A feature is complete only when it works and has evidence demonstrating that it works (REQ-236, REQ-237).

4. **No Frontend Before Backend**: Phase 4 cannot begin until Phases 1-3 acceptance criteria are satisfied (REQ-232).

5. **Real Cryptography**: Use real Ed25519, real SHA256 calculation, real Pydantic validation (REQ-011, REQ-014, REQ-015, REQ-049, REQ-050).

6. **No Cloud Fallback**: System must operate without Internet connectivity (REQ-001, REQ-009).

7. **Checksum Integrity**: Never invent SHA256; calculate from actual artifact (REQ-082, REQ-083, REQ-084, REQ-085, REQ-086).
