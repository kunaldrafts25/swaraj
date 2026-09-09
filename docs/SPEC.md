# SWARAJ v2 Specification

## 1. Product Mission

Build SWARAJ — Sovereign Workbench for Agentic Reasoning & Auditable Judgement.

SWARAJ is a self-hosted, air-gapped, multi-model agentic AI workbench for confidential industrial knowledge work.

Its primary demonstrated workflow is:

Unstructured refinery documents → OCR/document retrieval → agentic reasoning → structured Word/Excel output → self-validation → cryptographically signed zero-egress certificate → independently verifiable audit artifact.

The system must run entirely on local hardware, including:

- GPU systems with ≥6 GB VRAM
- systems with approximately 4 GB VRAM
- CPU-only laptops

The primary language model is:

- Qwen3-4B-Instruct, GGUF Q4_K_M

The system must never require cloud APIs, remote inference, telemetry, hosted vector databases, SaaS authentication, or Internet connectivity during normal operation.

**REQ-001**: System must operate without cloud APIs, remote inference, telemetry, hosted vector databases, SaaS authentication, or Internet connectivity during normal operation.

**REQ-002**: System must support GPU systems with ≥6 GB VRAM, systems with ~4 GB VRAM, and CPU-only laptops.

**REQ-003**: Primary model must be Qwen3-4B-Instruct, GGUF Q4_K_M.

## 2. Explicit Non-Goals

Document these clearly in README.md.

SWARAJ is:

- not a general-purpose chatbot;
- not a cloud service;
- not a replacement for a formal cybersecurity/security audit;
- not a regulatory certification authority;
- not claiming that cryptographic attestation alone proves the entire host was uncompromised.

The demonstrated use case is deliberately narrow:

Convert confidential refinery documents such as scanned inspection reports, P&IDs, near-miss logs, and related records into structured office outputs such as approval notes and Excel trackers, while maintaining an auditable execution trace and cryptographic evidence of observed network behavior.

Do not make broader claims than the implementation supports.

**REQ-004**: README.md must explicitly document non-goals.

**REQ-005**: System must not claim cryptographic attestation proves entire host was uncompromised.

## 3. Absolute Implementation Rules

**REQ-006**: No mocks in production paths.

**REQ-007**: No fake values (hashes, benchmark scores, routing confidence, egress state, certificate state).

**REQ-008**: No TODO placeholders in production paths.

**REQ-009**: No cloud fallback.

**REQ-010**: No hidden network access.

**REQ-011**: No invented cryptography (must use real Ed25519).

**REQ-012**: No UI before backend Phase 1 works.

**REQ-013**: No claim of completion without evidence.

**REQ-014**: Use real SHA256 calculation.

**REQ-015**: Use real Pydantic validation.

**REQ-016**: Use real pytest tests.

**REQ-017**: Use real fail-closed behavior.

## 4. Core Differentiating Mechanisms

### 4.1 Capability-Vector Auto-Benchmarking

**REQ-018**: When a model is registered, SWARAJ must evaluate it against a deterministic micro-evaluation suite covering:
- code generation/correctness
- summarization
- OCR-to-structured-field extraction

**REQ-019**: Produce a numeric capability vector with keys: code, summary, ocr_extract.

**REQ-020**: Capability scores must be computed from actual evaluation, not hardcoded.

### 4.2 Explainable Routing

**REQ-021**: At routing time, embed the incoming task using the local FastEmbed model.

**REQ-022**: Determine task characteristics.

**REQ-023**: Compare task requirements against registered model capabilities.

**REQ-024**: Incorporate hardware tier and latency constraints.

**REQ-025**: Select the best eligible model.

**REQ-026**: Return a deterministic, human-readable explanation.

**REQ-027**: Router decision must be deterministic for identical inputs and identical registry/calibration state.

**REQ-028**: POST /router/decide endpoint must return selected_model, confidence, reasoning, capability_scores, hardware_tier.

**REQ-029**: No fake confidence values.

**REQ-030**: No hardcoded routing output.

### 4.3 Zero-Egress Cryptographic Attestation

**REQ-031**: Implement a real runtime egress monitor.

**REQ-032**: During an agent run, poll network state approximately every 2 seconds.

**REQ-033**: Use psutil or equivalent local mechanism.

**REQ-034**: Distinguish loopback/local connections from non-loopback connections.

**REQ-035**: Record every observed event.

**REQ-036**: Emit events to frontend through SSE.

**REQ-037**: Provide continuous heartbeat/all-clear events.

**REQ-038**: If a forbidden non-loopback established connection is detected, trigger the configured kill-switch.

**REQ-039**: Terminate the isolated workload where technically possible.

**REQ-040**: Mark the run as security-failed.

**REQ-041**: Prevent successful certification on security failure.

**REQ-042**: On successful completion, construct a tamper-evident hash chain from recorded connection events.

**REQ-043**: Compute the final chain head.

**REQ-044**: Sign the certificate with an Ed25519 private key.

**REQ-045**: Store the public key with the certificate.

**REQ-046**: Produce a portable JSON certificate.

**REQ-047**: Certificate format must include: run_id, started_at, ended_at, model_used, egress_events, hash_chain_head, signature, signer_pubkey.

**REQ-048**: Create scripts/verify_certificate.py that loads certificate, reconstructs hash chain, verifies signature, verifies structure, reports success/failure, exits non-zero on tampering.

**REQ-049**: Do not implement cryptography using homemade signature scheme or ordinary SHA256 as substitute for signing.

**REQ-050**: Use cryptography.hazmat.primitives.asymmetric.ed25519.

### 4.4 Reflexive Document Self-Check

**REQ-051**: After generating .docx or .xlsx, re-open the generated file.

**REQ-052**: Parse it.

**REQ-053**: Validate against its declared output schema.

**REQ-054**: Validate required sections.

**REQ-055**: Validate numeric consistency.

**REQ-056**: Validate source citations.

**REQ-057**: Produce a structured validation diff.

**REQ-058**: If invalid, return the failure to the agent.

**REQ-059**: Allow the agent to regenerate.

**REQ-060**: Maximum four act/self-check iterations.

**REQ-061**: Only permit certification after validation succeeds.

**REQ-062**: Never reduce self-check to `return True`.

### 4.5 RBAC-Pruned Agent Planning

**REQ-063**: RBAC must operate at the planning layer.

**REQ-064**: Before tool execution, construct the agent plan.

**REQ-065**: Inspect every planned step.

**REQ-066**: Evaluate each step against the JSON RBAC policy.

**REQ-067**: Prune prohibited steps.

**REQ-068**: Route approval-required steps to the human Approvals queue.

**REQ-069**: Only execute authorized steps.

**REQ-070**: RBAC must be deny by default.

**REQ-071**: Roles: Inspector, Approver, Admin.

**REQ-072**: Demonstrate unauthorized write attempt → denied → approval queue → human approval required.

**REQ-073**: Do not merely check permissions after an action has already been planned/executed.

## 5. Model Runtime Requirements

**REQ-074**: Primary model: Qwen3-4B-Instruct, GGUF, Q4_K_M.

**REQ-075**: Runtime: llama.cpp, llama-cpp-python 0.3.x.

**REQ-076**: Use Ollama only as development/packaging convenience where useful.

**REQ-077**: Production application inference must use direct llama-cpp-python control.

**REQ-078**: Do not require an Ollama server to be running in production.

**REQ-079**: Expected model artifact: models/qwen3-4b-instruct-q4_k_m.gguf.

**REQ-080**: The artifact must NOT be committed to Git.

**REQ-081**: The setup process must obtain the model from a documented source and verify its checksum.

**REQ-082**: Never invent a SHA256 checksum.

**REQ-083**: The exact SHA256 must be calculated from the exact artifact actually downloaded.

**REQ-084**: If upstream provider publishes official checksum, compare against it.

**REQ-085**: If no trustworthy upstream checksum exists: calculate artifact SHA256, record calculated value, clearly label provenance, never represent locally calculated checksum as upstream publisher checksum.

**REQ-086**: The registry manifest must reference the verified artifact hash.

## 6. Hardware Tier Requirements

**REQ-087**: Implement automatic hardware detection/calibration.

**REQ-088**: Tier 1: ≥6 GB usable VRAM. Configuration: Qwen3-4B Q4_K_M, full GPU offload, 8K context. Expected target: ~2–4 seconds / 500 generated tokens.

**REQ-089**: Tier 2: Approximately 4 GB VRAM/integrated GPU. Configuration: partial GPU offload, approximately n_gpu_layers=20. Expected target: ~6–10 seconds / 500 generated tokens.

**REQ-090**: Tier 3: CPU-only. Configuration: n_gpu_layers=0, n_threads=8, Qwen3-4B Q4_K_M. Expected target: ~15–25 seconds / 500 generated tokens.

**REQ-091**: These numbers are targets, not fake runtime claims.

**REQ-092**: At startup: detect hardware, perform short calibration inference, measure actual latency, classify hardware tier, persist calibration results, expose actual measurements through API, use measured results in routing.

**REQ-093**: README must distinguish expected/target performance from measured performance.

**REQ-094**: Do not display target latency as if it were measured latency.

## 7. Vision/OCR Requirements

**REQ-095**: Primary OCR: PaddleOCR 2.9 CPU.

**REQ-096**: Pipeline: PDF → pdf2image → Pillow → PaddleOCR → structured text.

**REQ-097**: Optional layout/image reasoning: Qwen2-VL-2B Q4.

**REQ-098**: Load optional model only when required.

**REQ-099**: Never keep two large models resident simultaneously on low-VRAM machine unless hardware measurements explicitly demonstrate it is safe.

## 8. Technology Stack

### 8.1 Backend

**REQ-100**: Python 3.11.

**REQ-101**: FastAPI 0.115.

**REQ-102**: Uvicorn 0.32.

**REQ-103**: LangGraph 0.2.

**REQ-104**: ChromaDB 0.5.

**REQ-105**: FastEmbed 0.4.

**REQ-106**: scikit-learn 1.5.

**REQ-107**: llama-cpp-python 0.3.x.

**REQ-108**: PaddleOCR 2.9.

**REQ-109**: PyPDF 5.

**REQ-110**: pdf2image 1.17.

**REQ-111**: Pillow 10.

**REQ-112**: python-docx 1.1.

**REQ-113**: python-pptx 1.0.

**REQ-114**: openpyxl 3.1.

**REQ-115**: cryptography 43.

**REQ-116**: psutil 6.

**REQ-117**: httpx.

**REQ-118**: PyYAML.

**REQ-119**: pytest.

**REQ-120**: pytest-asyncio.

**REQ-121**: Pin versions where practical for reproducibility.

**REQ-122**: Do not blindly trust version combinations. Resolve dependency conflicts and choose compatible patch versions when necessary, documenting deviations in README.

### 8.2 Frontend

**REQ-123**: React 19.

**REQ-124**: TypeScript strict.

**REQ-125**: Vite 6.

**REQ-126**: Tailwind CSS 3.4.

**REQ-127**: shadcn/ui.

**REQ-128**: Framer Motion 11.

**REQ-129**: @xyflow/react 12.

**REQ-130**: Recharts 2.15.

**REQ-131**: Zustand 5.

**REQ-132**: @tanstack/react-query 5.

**REQ-133**: cmdk.

**REQ-134**: sonner.

**REQ-135**: lucide-react.

**REQ-136**: mammoth.

**REQ-137**: xlsx.

**REQ-138**: Self-host Inter and JetBrains Mono fonts. No external font CDN.

## 9. Design System

**REQ-139**: Name: SOVEREIGN MISSION CONTROL.

**REQ-140**: Colors: #0B0F14, #11161D, #161D26, #1E2630, #E6EDF3, #8B949E, #10B981, #F59E0B, #EF4444, #22D3EE.

**REQ-141**: No glassmorphism.

**REQ-142**: No gradients.

**REQ-143**: Hairline borders.

**REQ-144**: Dense but readable information layout.

**REQ-145**: Inter for UI.

**REQ-146**: JetBrains Mono for hashes, logs, IDs, measurements and technical values.

**REQ-147**: Restrained animation.

**REQ-148**: Clear security state indicators.

**REQ-149**: Accessibility-conscious contrast.

**REQ-150**: Responsive layout.

**REQ-151**: UI should feel like an industrial security/operations console, not a consumer chatbot.

## 10. Exact Repository Structure

**REQ-152**: Create exact repository structure as specified:

```
swaraj/
├── pyproject.toml
├── docker-compose.yml
├── README.md
├── models/
│   └── qwen3-4b-instruct-q4_k_m.gguf
├── policies/
│   └── rbac_policy.json
├── scripts/
│   ├── setup.sh
│   └── verify_certificate.py
├── src/swaraj/
│   ├── __init__.py
│   ├── config.py
│   ├── registry/
│   │   ├── __init__.py
│   │   ├── manifest_schema.py
│   │   ├── loader.py
│   │   └── manifests/
│   │       └── qwen3-4b.yaml
│   ├── auto_bench/
│   │   ├── __init__.py
│   │   ├── eval_suite.py
│   │   └── capability_vector.py
│   ├── router/
│   │   ├── __init__.py
│   │   ├── embed.py
│   │   ├── classifier.py
│   │   └── decide.py
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── rbac.py
│   │   ├── audit_log.py
│   │   └── certificate.py
│   ├── monitor/
│   │   ├── __init__.py
│   │   └── egress_watch.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── fs_jail.py
│   │   ├── sandbox_exec.py
│   │   ├── xlsx_writer.py
│   │   ├── docx_writer.py
│   │   ├── calc_trace.py
│   │   └── doc_search.py
│   ├── multimodal/
│   │   ├── __init__.py
│   │   └── ocr_pipeline.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py
│   │   └── schemas.py
│   └── api/
│       ├── __init__.py
│       └── main.py
├── tests/
│   ├── test_router.py
│   ├── test_egress_monitor.py
│   ├── test_self_check.py
│   └── test_certificate.py
└── ui-web/
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── tsconfig.json
    └── src/
        ├── lib/api.ts
        ├── hooks/
        │   ├── useAgentStream.ts
        │   └── useConnectionStatus.ts
        ├── store/
        │   ├── useAppStore.ts
        │   └── useTraceStore.ts
        ├── components/
        │   └── shell/
        │       ├── Sidebar.tsx
        │       ├── TopBar.tsx
        │       └── StatusBar.tsx
        └── pages/
            ├── Home.tsx
            ├── Trace.tsx
            ├── Egress.tsx
            ├── Registry.tsx
            └── Approvals.tsx
```

**REQ-153**: May add supporting files when required by correct implementation, but do not arbitrarily restructure the architecture.

## 11. Registry Contract

**REQ-154**: Implement ModelManifest with at least: name, version, gguf_path, sha256, quant, context_length, hardware_tier_min, capability_vector, signed_at, signature.

**REQ-155**: Use Pydantic validation.

**REQ-156**: The loader must: load YAML, validate schema, resolve model path safely, calculate SHA256, compare with manifest, reject mismatch, validate signature where applicable, return trusted model record.

**REQ-157**: Never silently continue on checksum mismatch.

**REQ-158**: Never load a model whose integrity verification failed.

## 12. Router Contract

**REQ-159**: Expose POST /router/decide.

**REQ-160**: Input must describe the task sufficiently to determine routing requirements.

**REQ-161**: Return: selected_model, confidence, reasoning, capability_scores, hardware_tier.

**REQ-162**: Decision must be deterministic for identical inputs and identical registry/calibration state.

**REQ-163**: No fake confidence values.

**REQ-164**: No hardcoded routing output.

## 13. Filesystem Jail Requirements

**REQ-165**: Implement strict path validation.

**REQ-166**: Reject: ../, ..\, absolute paths, symlink escapes, paths outside configured workspace.

**REQ-167**: Resolve canonical paths before authorization.

**REQ-168**: Write explicit tests for traversal attempts.

**REQ-169**: The filesystem jail must operate before file access.

## 14. Sandbox Execution Requirements

**REQ-170**: All untrusted executable/tool workloads must use: docker run --network none where Docker is available.

**REQ-171**: Provide a carefully restricted subprocess fallback only where Docker is unavailable.

**REQ-172**: Never permit the fallback to silently gain Internet access.

**REQ-173**: Never execute user-controlled shell strings through an unrestricted shell.

**REQ-174**: Document the security limitations of the fallback.

## 15. Audit Log Requirements

**REQ-175**: Use SQLite.

**REQ-176**: Audit entries must be append-only from the application's perspective and protected against UPDATE/DELETE through the application's database access layer.

**REQ-177**: Record: run ID, user, role, timestamp, agent step, router decision, tool invocation, authorization result, output artifact, self-check result, egress events, certificate state.

**REQ-178**: Use structured records.

**REQ-179**: Hash-chain security-sensitive audit entries.

**REQ-180**: Do not log: private signing keys, secrets, credentials, sensitive document contents unless explicitly required.

## 16. Observability Requirements

**REQ-181**: Use structured JSON logging.

**REQ-182**: No production print() logging.

**REQ-183**: Log: startup, hardware calibration, model loading, model integrity verification, router decisions, every agent step, RBAC decisions, tool executions, self-check failures, egress events, certificate generation, certificate verification failures.

**REQ-184**: Use rotating local log files.

**REQ-185**: Logs must remain useful without requiring the development team.

## 17. Agent Graph Requirements

**REQ-186**: Implement LangGraph: plan → prune → act → observe → self_check → (fail → act) or (pass → cert).

**REQ-187**: Maximum 4 act/self-check iterations.

**REQ-188**: Every state transition must be represented in the trace.

**REQ-189**: Agent state must contain enough information to reproduce/audit the run.

## 18. API Requirements

**REQ-190**: Expose appropriate REST/SSE endpoints for: health, hardware status, model registry, router decision, document ingestion, agent execution, agent trace, egress stream, approval queue, certificate retrieval, certificate verification, audit events.

**REQ-191**: Use Pydantic request/response models.

**REQ-192**: Do not expose the signing private key.

**REQ-193**: Do not expose arbitrary filesystem access.

**REQ-194**: Do not expose unrestricted subprocess execution.

## 19. Frontend Requirements

**REQ-195**: Implement screens: Home, Trace, Egress, Registry, Approvals.

**REQ-196**: Home must show: task input, selected model, routing explanation, hardware tier, execution status, generated artifacts, certificate status.

**REQ-197**: Trace must show: plan, RBAC pruning, executed tools, observations, self-check iterations, final certificate state.

**REQ-198**: Egress must show: live egress status, event count, connection events, heartbeats, security status, run ID. Do not display fake zero.

**REQ-199**: UI must reflect actual backend state.

**REQ-200**: Registry must show: installed models, versions, quantization, SHA256, capability vector, hardware requirements, benchmark results.

**REQ-201**: Approvals must show: pending requests, requesting user, role, requested action, affected artifact, policy reason, approve/deny controls.

## 20. Users and RBAC Requirements

**REQ-202**: Create pilot-oriented users.json with: Inspector, Approver, Admin.

**REQ-203**: Flat-file authentication is acceptable for the pilot.

**REQ-204**: Do not claim production-grade identity management.

**REQ-205**: The authorization model must still be real and demonstrable.

## 21. Docker Requirements

**REQ-206**: Create docker-compose.yml with api and web services.

**REQ-207**: The application network must be internal by default.

**REQ-208**: Do not provide accidental Internet connectivity.

**REQ-209**: Avoid dependency downloads at runtime.

**REQ-210**: The intended pilot workflow should be: ./scripts/setup.sh then docker compose up --build.

**REQ-211**: After model placement/download, there should be no undocumented manual configuration.

## 22. Testing Requirements

**REQ-212**: Implement tests that actually exercise the mechanisms.

**REQ-213**: Minimum required tests: Router (same task + same registry/calibration state → same decision), Egress (connection detected → security event generated → kill switch triggered → run cannot be certified), Filesystem (../secret, ..\secret, absolute path, symlink escape are rejected), Self-check (malformed .docx → self-check fails → structured diff generated → regeneration path activated), Certificate (valid certificate → success, tampered hash chain → failure, tampered payload → failure, invalid signature → failure).

**REQ-214**: Run pytest -q and ensure the suite passes.

## 23. Setup Script Requirements

**REQ-215**: Implement scripts/setup.sh.

**REQ-216**: It must: check required system dependencies, create required directories, create Python environment/install dependencies as appropriate, obtain the GGUF if configured, verify the artifact checksum, initialize SQLite, generate Ed25519 keypair if absent, set secure key permissions, initialize configuration, perform a basic health check.

**REQ-217**: Never overwrite an existing signing key without explicit operator confirmation.

**REQ-218**: Never print the private key.

**REQ-219**: Never put it in an API response.

## 24. Security Checklist

**REQ-220**: README must contain this checklist and update it only when genuinely satisfied:

- [ ] Sandbox exec never runs with --network other than none
- [ ] Filesystem jail rejects ../ traversal
- [ ] Filesystem jail rejects symlink escapes
- [ ] RBAC denies by default
- [ ] Audit log is append-only at application level
- [ ] Signing key never leaves host filesystem
- [ ] Signing key is never logged
- [ ] Signing key is never returned by an API
- [ ] Model SHA256 is verified before loading
- [ ] Certificate fails verification after tampering
- [ ] CPU-only execution works
- [ ] No cloud/API dependency exists in normal operation

**REQ-221**: Do not check boxes merely because the code exists. Validate them.

## 25. README Requirements

**REQ-222**: README must contain: product overview, architecture diagram in Mermaid, security model, threat assumptions, hardware ladder, installation, model acquisition, model checksum verification, CPU-only instructions, GPU instructions, measured benchmark methodology, measured benchmark results, API overview, certificate verification instructions, RBAC explanation, air-gap/network architecture, troubleshooting, test instructions, pilot limitations, Definition of Done, explicit non-goals.

**REQ-223**: Clearly distinguish: implemented, tested, measured, assumed, target.

**REQ-224**: Never present assumptions as measurements.

## 26. Definition of Done

**REQ-225**: Do not call the project pilot-ready until every item is genuinely satisfied:

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

## 27. Phase Execution Order

**REQ-226**: Must follow this order:

Phase 1 — Model Runtime + Registry + Router
Phase 2 — Governance + Security + Tools
Phase 3 — Agent + Multimodal + API
Phase 4 — Frontend
Phase 5 — Pilot Hardening

**REQ-227**: Begin immediately with Phase 1.

**REQ-228**: Do not jump to React.

**REQ-229**: Do not generate a conceptual explanation instead of implementation.

**REQ-230**: Do not stop after creating a scaffold.

**REQ-231**: Produce the complete, runnable Phase 1 implementation, then execute the relevant validation/tests and fix failures before moving forward.

**REQ-232**: Frontend must not be started until backend Phase 1 acceptance criteria are satisfied.

## 28. Failure Handling Rules

**REQ-233**: When an implementation cannot satisfy a requirement because of missing hardware, unavailable model artifact, incompatible package, operating-system limitation, Docker limitation, unsupported accelerator: do not fake success.

**REQ-234**: Instead: identify the exact failure, preserve the architecture, implement the strongest real fallback, document the limitation, add a test where possible, continue with independent work.

**REQ-235**: Never silently downgrade a security guarantee.

## 29. Output and Evidence Rules

**REQ-236**: A feature is not complete because its source file exists.

**REQ-237**: A feature is complete only when it works and has evidence demonstrating that it works.

**REQ-238**: Before declaring any phase complete, perform: static inspection, dependency validation, unit tests, integration tests, security tests, runtime smoke test, offline test, failure-path test, verify no placeholder implementations, verify no fake values, verify documentation matches reality.

**REQ-239**: The ultimate objective is: A judge can clone the repository, place/download the verified model, run the setup procedure, start Docker Compose, execute a real refinery-document workflow, inspect every agent decision, observe the egress monitor, see RBAC enforcement, receive a real Word/Excel artifact, and independently verify the cryptographic certificate offline.

**REQ-240**: Build toward that standard throughout the project.
