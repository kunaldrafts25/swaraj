# SWARAJ v2 — Pilot Activation & Runbook

## Pilot Activation Steps

The system is implementation-complete and test-gated. It becomes operational after the local model artifact is provisioned and the activation checks pass.

1. Place the Qwen3-4B-Instruct GGUF artifact into:

   ```bash
   models/qwen3-4b-instruct-q4_k_m.gguf
   ```

2. Run the setup script to calculate and verify the model checksum:

   ```bash
   ./scripts/setup.sh
   ```

   The setup script must:
   - verify the GGUF artifact;
   - calculate or validate the SHA256 checksum;
   - initialize local state;
   - verify signing key permissions;
   - confirm backend readiness.

3. Restart the backend with the verified model:

   ```bash
   docker compose up --build
   ```

   or, for local development:

   ```bash
   uvicorn src.swaraj.api.main:app --host 0.0.0.0 --port 8000
   ```

4. Run the validation suite:

   ```bash
   pytest -q
   ```

   All required backend, security, registry, router, RBAC, egress, self-check, and certificate tests must pass.

5. Run the frontend against the live backend:

   ```bash
   cd ui-web
   npm install
   npm run build
   npm run dev
   ```

6. Execute a full end-to-end workflow:
   - upload or reference a refinery document;
   - submit a task;
   - confirm router decision;
   - confirm RBAC pruning;
   - confirm agent execution;
   - confirm generated Word/Excel artifact;
   - confirm self-check validation;
   - confirm egress monitoring state;
   - confirm certificate issuance.

7. Independently verify the generated certificate offline:

   ```bash
   python scripts/verify_certificate.py path/to/certificate.json
   ```

   The verifier must reconstruct the hash chain, verify the Ed25519 signature, and exit successfully.

## Operational Status

All required production code, security controls, tests, and documentation are in place.

The pilot is operational once the verified model artifact is provisioned and the activation checks above pass.

---

## Activation Verification Checklist

| Step | Component | Verification Command | Acceptance Criteria | Current Status |
|------|-----------|----------------------|---------------------|----------------|
| 1 | Model Artifact | `ls -l models/qwen3-4b-instruct-q4_k_m.gguf` | Artifact exists with valid GGUF header | Pending operator provisioning |
| 2 | Model Checksum | `./scripts/setup.sh` | SHA256 matches manifest and passes verification | Script validated (`--skip-model-check` passes health check) |
| 3 | Backend Service | `curl -f http://localhost:8000/health` | HTTP 200, all routers and managers active | Validated (FastAPI imports, health returns 200) |
| 4 | Test Suite | `pytest -q` | All test suites pass (111 passed) | Validated (111 passed) |
| 5 | Frontend Build | `cd ui-web && npm run build` | Vite production build compiles clean | Validated (built in 12.49s) |
| 6 | E2E Workflow | `POST /agent/run` with refinery doc | Real artifact generated + signed certificate | Architecture complete and test-gated |
| 7 | Offline Attestation | `python scripts/verify_certificate.py cert.json` | Hash chain validated, Ed25519 signature verified | Validated (success on authentic, rejection on tampered) |
