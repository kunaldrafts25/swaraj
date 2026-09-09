# SWARAJ v2 Open Questions

This document tracks ambiguous, missing, contradictory, or environment-dependent aspects of the specification. Each question includes affected requirement IDs, safest fail-closed default, whether implementation can continue using that default, and what evidence would resolve it.

---

## OQ-001: Model Artifact SHA256 Value

**Question**: What is the exact SHA256 checksum of the Qwen3-4B-Instruct GGUF Q4_K_M artifact?

**Affected Requirement IDs**: REQ-079, REQ-081, REQ-082, REQ-083, REQ-084, REQ-085, REQ-086, REQ-154, REQ-156

**Context**: The specification mandates never inventing a SHA256 checksum. The exact SHA256 must be calculated from the exact artifact actually downloaded. However, the model artifact is not provided in the development environment, and the upstream source URL is not specified.

**Safest Fail-Closed Default**: 
- Implement registry loader with checksum verification mechanism
- Leave sha256 field in manifest as empty string or placeholder with clear "CALCULATE_FROM_ARTIFACT" marker
- Setup script calculates SHA256 when model is obtained
- Loader refuses to load model until verified checksum is available

**Can Implementation Continue Using Default**: Yes. Phase 1 implementation can proceed with:
- Full checksum verification logic implemented
- Manifest schema requiring sha256 field
- Loader rejecting models with unverified/missing checksums
- Setup script designed to calculate and insert checksum

**Evidence Needed to Resolve**: 
- Actual model artifact placed in models/qwen3-4b-instruct-q4_k_m.gguf
- SHA256 calculated via `sha256sum models/qwen3-4b-instruct-q4_k_m.gguf`
- If upstream publishes official checksum, comparison result

---

## OQ-002: Model Acquisition Source URL

**Question**: What is the documented source URL for obtaining the Qwen3-4B-Instruct GGUF Q4_K_M model?

**Affected Requirement IDs**: REQ-081, REQ-222

**Context**: The specification states "The setup process must obtain the model from a documented source" but does not specify the source URL. Potential sources include Hugging Face, ModelScope, or other repositories.

**Safest Fail-Closed Default**:
- Document multiple potential sources in README
- Setup script accepts configurable source URL via environment variable or argument
- Default to most trustworthy source (official Qwen repository if available)
- If no source configured, setup script instructs operator to manually place model

**Can Implementation Continue Using Default**: Yes. Setup script can be implemented with:
- Configurable MODEL_SOURCE_URL environment variable
- Fallback to manual placement instructions
- Clear documentation of acquisition options

**Evidence Needed to Resolve**:
- Confirmed official distribution channel for Qwen3-4B-Instruct GGUF
- Verified stable URL that will remain available for pilot duration

---

## OQ-003: GPU Detection on Specific Hardware Configurations

**Question**: How should hardware detection behave on systems with unusual GPU configurations (e.g., multiple GPUs, integrated + discrete, non-NVIDIA GPUs)?

**Affected Requirement IDs**: REQ-087, REQ-088, REQ-089, REQ-090, REQ-092

**Context**: The specification defines three tiers but does not detail detection logic for edge cases.

**Safest Fail-Closed Default**:
- If GPU detection is ambiguous or fails: default to Tier 3 (CPU-only)
- Use conservative configuration (n_gpu_layers=0)
- Log warning about detection uncertainty
- Allow manual override via configuration

**Can Implementation Continue Using Default**: Yes. Conservative default ensures system functions, albeit with slower performance.

**Evidence Needed to Resolve**:
- Test results from various hardware configurations
- llama-cpp-python GPU detection capabilities documentation
- Decision on which GPU libraries to support (CUDA, Metal, Vulkan, etc.)

---

## OQ-004: FastEmbed Model for Task Embedding

**Question**: Which specific FastEmbed model should be used for task embedding, and how is it obtained without Internet connectivity?

**Affected Requirement IDs**: REQ-021, REQ-105, REQ-122

**Context**: FastEmbed requires downloading embedding models. In air-gapped operation, these must be pre-positioned.

**Safest Fail-Closed Default**:
- Select smallest viable FastEmbed model (e.g., BAAI/bge-small-en-v1.5)
- Include model download in setup script with caching
- Document manual download procedure for air-gapped deployment
- If embedding model unavailable: use keyword-based fallback classifier with reduced capability

**Can Implementation Continue Using Default**: Yes. Can implement:
- Embedding abstraction with fallback
- Setup script handles model acquisition
- Graceful degradation if embedding unavailable

**Evidence Needed to Resolve**:
- FastEmbed model size vs. quality tradeoff analysis
- Confirmed list of embedding models supported by fastembed 0.4
- Air-gap deployment procedure for embedding models

---

## OQ-005: Ed25519 Key Pair Storage Location and Permissions

**Question**: What is the exact filesystem path for storing the Ed25519 signing keypair, and what are the precise file permissions?

**Affected Requirement IDs**: REQ-216, REQ-217, REQ-218, REQ-219, REQ-220

**Context**: The specification requires secure key storage but does not specify exact path or permission mode.

**Safest Fail-Closed Default**:
- Path: `keys/signing_private.pem` and `keys/signing_public.pem` (relative to project root)
- Private key permissions: 0600 (owner read/write only)
- Public key permissions: 0644 (owner read/write, others read)
- Directory permissions: 0700 (owner only)
- Never overwrite existing keys without explicit confirmation

**Can Implementation Continue Using Default**: Yes. These are standard secure defaults.

**Evidence Needed to Resolve**:
- Security review approval of key storage approach
- Confirmation that path works within Docker volume mounts

---

## OQ-006: RBAC Policy JSON Schema

**Question**: What is the exact JSON schema for the RBAC policy document?

**Affected Requirement IDs**: REQ-066, REQ-070, REQ-071, REQ-202, REQ-205

**Context**: The specification mentions JSON RBAC policy but does not provide exact schema.

**Safest Fail-Closed Default**:
```json
{
  "roles": {
    "Inspector": {
      "permissions": ["read", "list", "create_approval_request"]
    },
    "Approver": {
      "permissions": ["read", "list", "approve", "deny", "review_queue"]
    },
    "Admin": {
      "permissions": ["*"]
    }
  },
  "actions": {
    "file_write": {"required_permission": "write", "approval_required_if_missing": true},
    "file_read": {"required_permission": "read"},
    "model_inference": {"required_permission": "execute"}
  },
  "default_policy": "deny"
}
```
- Deny by default
- Explicit permission grants required
- Approval queue for actions requiring human review

**Can Implementation Continue Using Default**: Yes. Schema can be refined during implementation.

**Evidence Needed to Resolve**:
- Pilot user workflow requirements
- Specific actions that require approval vs. outright denial

---

## OQ-007: Audit Log Hash-Chain Construction Details

**Question**: What is the exact algorithm for constructing the audit log hash chain?

**Affected Requirement IDs**: REQ-179, REQ-176

**Context**: The specification requires hash-chaining security-sensitive audit entries but does not detail the construction algorithm.

**Safest Fail-Closed Default**:
- For each security-sensitive entry:
  - `entry_hash = SHA256(serialized_entry)`
  - `chain_head = SHA256(previous_chain_head + entry_hash)`
  - First entry: `chain_head = SHA256(entry_hash)`
- Store chain_head with each entry
- Certificate final chain_head computed from all egress events

**Can Implementation Continue Using Default**: Yes. This is a standard hash chain construction.

**Evidence Needed to Resolve**:
- Cryptographic review of hash chain construction
- Decision on which entries are "security-sensitive" vs. regular audit entries

---

## OQ-008: Egress Monitor Polling Interval Precision

**Question**: Is "approximately every 2 seconds" (REQ-032) acceptable, or is more precise timing required?

**Affected Requirement IDs**: REQ-032, REQ-035, REQ-038

**Context**: The specification says "approximately every 2 seconds" but does not define tolerance.

**Safest Fail-Closed Default**:
- Poll interval: 2 seconds ± 0.5 seconds
- Use asyncio.sleep(2.0) for simplicity
- If faster detection needed: make configurable via environment variable
- Conservative: shorter interval means faster detection but more overhead

**Can Implementation Continue Using Default**: Yes. 2-second polling is reasonable for pilot.

**Evidence Needed to Resolve**:
- Performance testing showing polling overhead
- Security requirements for maximum detection latency

---

## OQ-009: Self-Check Iteration Limit Enforcement

**Question**: What happens when the maximum 4 act/self-check iterations are exceeded?

**Affected Requirement IDs**: REQ-060, REQ-186, REQ-187

**Context**: The specification states maximum 4 iterations but does not detail failure behavior.

**Safest Fail-Closed Default**:
- On iteration 5: terminate agent run
- Mark run as validation_failed
- Return structured error with all previous validation diffs
- Do not generate certificate
- Log all attempts and failures for audit

**Can Implementation Continue Using Default**: Yes. Clear failure mode.

**Evidence Needed to Resolve**:
- Agent behavior testing showing typical iteration counts
- Whether regeneration should be attempted with different approach vs. hard fail

---

## OQ-010: Docker Compose Service Configuration Details

**Question**: What are the exact Docker image, port mappings, and volume configurations for api and web services?

**Affected Requirement IDs**: REQ-206, REQ-207, REQ-208, REQ-209, REQ-210

**Context**: The specification requires docker-compose.yml but does not provide service details.

**Safest Fail-Closed Default**:
```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"  # Only necessary port
    volumes:
      - ./models:/app/models:ro
      - ./policies:/app/policies:ro
      - ./data:/app/data
      - ./keys:/app/keys
    networks:
      - swaraj_internal
    environment:
      - SWARAJ_ENV=pilot
    
  web:
    build: ./ui-web
    ports:
      - "3000:3000"
    depends_on:
      - api
    networks:
      - swaraj_internal

networks:
  swaraj_internal:
    internal: false  # Allows host access but no external egress by default
```

**Can Implementation Continue Using Default**: Yes. Configuration can be adjusted based on testing.

**Evidence Needed to Resolve**:
- Docker build testing
- Network isolation verification
- Volume mount permissions testing

---

## OQ-011: Capability Vector Evaluation Suite Content

**Question**: What are the exact evaluation prompts/tasks for code, summary, and ocr_extract capability dimensions?

**Affected Requirement IDs**: REQ-018, REQ-019, REQ-020, REQ-154

**Context**: The specification requires deterministic micro-evaluation suite but does not provide exact evaluation tasks.

**Safest Fail-Closed Default**:
- **code**: Simple Python function completion (e.g., "Write a function that computes factorial")
- **summary**: Single-paragraph summarization task (e.g., "Summarize this 200-word text")
- **ocr_extract**: Structured field extraction from sample OCR text (e.g., "Extract date, ID number, and status from this text")
- Scoring: Exact match or semantic similarity against reference answers
- All evaluation data embedded in code (no external dependencies)

**Can Implementation Continue Using Default**: Yes. Initial evaluation suite can be simple and refined later.

**Evidence Needed to Resolve**:
- Evaluation task validation showing correlation with real-world performance
- Inter-model discrimination testing (do scores differentiate capable vs. incapable models?)

---

## OQ-012: Calibration Inference Prompt and Metrics

**Question**: What prompt and metrics are used for hardware calibration inference?

**Affected Requirement IDs**: REQ-092, REQ-154, REQ-222

**Context**: The specification requires calibration inference at startup but does not specify the prompt or measurement methodology.

**Safest Fail-Closed Default**:
- Prompt: Fixed 100-token context with request for 200-token response
- Metrics: tokens_per_second, time_to_first_token, total_latency
- Run calibration once at startup (or when configuration changes)
- Persist results to calibration.json
- Use measured tokens_per_second for routing decisions

**Can Implementation Continue Using Default**: Yes. Simple calibration provides useful baseline.

**Evidence Needed to Resolve**:
- Calibration repeatability testing
- Correlation between calibration results and real workload performance

---

## Summary

All open questions have safe fail-closed defaults that allow implementation to proceed. None of these questions block Phase 1 implementation. The most critical resolution needed before full system completion is OQ-001 (actual model SHA256), which must be resolved by calculating the checksum from the actual artifact when it becomes available.

Implementation strategy:
1. Implement all mechanisms with fail-closed defaults
2. Document assumptions and defaults clearly
3. Design configuration points for easy adjustment when questions are resolved
4. Mark requirements as NEEDS_EVIDENCE in IMPLEMENTATION_STATUS.md until resolved
