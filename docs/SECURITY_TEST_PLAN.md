# SWARAJ v2 Security Test Plan

## Overview
This document defines the security tests required to validate SWARAJ v2's security guarantees. Each test includes the requirement ID, method, expected pass result, expected fail-closed result, and whether it can run without GPU/model/Docker.

---

## 1. Model Integrity Tests

### TEST-SEC-001: Model SHA256 Mismatch Rejection
- **Requirement IDs**: REQ-082, REQ-083, REQ-156, REQ-157, REQ-158
- **Method**: 
  1. Create a model manifest with an incorrect SHA256 checksum
  2. Attempt to load the model using the registry loader
  3. Verify the loader rejects the model
- **Expected Pass Result**: Loader raises exception or returns error indicating checksum mismatch; model is not loaded
- **Expected Fail-Closed Result**: Application refuses to proceed with unverified model; security event logged
- **Can Run Without GPU/Model/Docker**: Yes (requires only a test file to act as fake model artifact)

### TEST-SEC-002: Missing Model Artifact Fail-Closed Behavior
- **Requirement IDs**: REQ-156, REQ-157, REQ-158
- **Method**:
  1. Create a valid manifest pointing to a non-existent model path
  2. Attempt to load the model
  3. Verify the loader fails appropriately
- **Expected Pass Result**: Loader raises FileNotFoundError or equivalent; no silent fallback
- **Expected Fail-Closed Result**: Application cannot load unverified model; appropriate error returned
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-003: Fabricated or Pending Checksum Rejection
- **Requirement IDs**: REQ-007, REQ-082, REQ-085
- **Method**:
  1. Create a manifest with placeholder checksum (e.g., "pending", "TODO", all zeros)
  2. Attempt to validate the manifest
  3. Verify rejection of invalid checksum format
- **Expected Pass Result**: Manifest validation fails; placeholder checksums rejected
- **Expected Fail-Closed Result**: Model cannot be registered until real checksum calculated
- **Can Run Without GPU/Model/Docker**: Yes

---

## 2. Filesystem Security Tests

### TEST-SEC-004: Filesystem Traversal Rejection (../)
- **Requirement IDs**: REQ-165, REQ-166, REQ-167, REQ-168, REQ-169
- **Method**:
  1. Attempt to access path containing "../" (e.g., "../../etc/passwd")
  2. Verify fs_jail.reject_path() or equivalent rejects the path
- **Expected Pass Result**: Path rejected with security exception
- **Expected Fail-Closed Result**: Access denied; no file operation performed
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-005: Filesystem Traversal Rejection (..\)
- **Requirement IDs**: REQ-165, REQ-166, REQ-167, REQ-168, REQ-169
- **Method**:
  1. Attempt to access path containing "..\" (Windows-style traversal)
  2. Verify rejection
- **Expected Pass Result**: Path rejected with security exception
- **Expected Fail-Closed Result**: Access denied
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-006: Absolute Path Rejection
- **Requirement IDs**: REQ-165, REQ-166, REQ-167
- **Method**:
  1. Attempt to access absolute path outside configured workspace (e.g., "/etc/passwd" or "C:\Windows\system32")
  2. Verify rejection
- **Expected Pass Result**: Absolute paths rejected unless within allowed workspace
- **Expected Fail-Closed Result**: Access denied
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-007: Symlink Escape Rejection
- **Requirement IDs**: REQ-165, REQ-166, REQ-167, REQ-168
- **Method**:
  1. Create a symlink inside workspace pointing to a file outside workspace
  2. Attempt to access the file through the symlink
  3. Verify the escape is detected and rejected
- **Expected Pass Result**: Symlink escape detected; access denied
- **Expected Fail-Closed Result**: No access to files outside workspace via symlinks
- **Can Run Without GPU/Model/Docker**: Yes (requires filesystem setup)

---

## 3. RBAC Tests

### TEST-SEC-008: RBAC Deny-by-Default Behavior
- **Requirement IDs**: REQ-063, REQ-070, REQ-205
- **Method**:
  1. Create a user with no explicit permissions
  2. Attempt any action requiring authorization
  3. Verify the action is denied by default
- **Expected Pass Result**: Action denied; no implicit permissions granted
- **Expected Fail-Closed Result**: Unauthorized action blocked
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-009: Approval Queue Flow for Prohibited Actions
- **Requirement IDs**: REQ-068, REQ-072, REQ-205
- **Method**:
  1. Create a user (Inspector) without write permission
  2. Attempt a write action
  3. Verify action is denied and routed to approval queue
  4. Verify Approver can review and approve/deny
  5. Verify action executes only after approval
- **Expected Pass Result**: Unauthorized write → denied → approval queue → human approval required → execution after approval
- **Expected Fail-Closed Result**: No unauthorized execution without approval
- **Can Run Without GPU/Model/Docker**: Yes

---

## 4. Egress Monitor Tests

### TEST-SEC-010: Egress Monitor Detection of Forbidden Non-Loopback Connections
- **Requirement IDs**: REQ-031, REQ-032, REQ-033, REQ-034, REQ-035, REQ-038
- **Method**:
  1. Start egress monitor
  2. Launch controlled test workload that attempts external connection (e.g., to 8.8.8.8:53 or example.com:80)
  3. Verify connection is detected as non-loopback
  4. Verify security event generated
- **Expected Pass Result**: Non-loopback connection detected; event recorded with timestamp, source, destination
- **Expected Fail-Closed Result**: Connection attempt logged; kill-switch available
- **Can Run Without GPU/Model/Docker**: Yes (requires network capability)

### TEST-SEC-011: Kill-Switch Behavior
- **Requirement IDs**: REQ-038, REQ-039, REQ-040, REQ-041
- **Method**:
  1. Configure kill-switch threshold
  2. Trigger forbidden connection detection
  3. Verify workload termination
  4. Verify run marked as security-failed
  5. Verify certification prevented
- **Expected Pass Result**: Workload terminated; run marked security-failed; certificate generation fails
- **Expected Fail-Closed Result**: No certification for runs with security failures
- **Can Run Without GPU/Model/Docker**: Partially (requires ability to simulate network connections)

### TEST-SEC-012: Loopback vs Non-Loopback Distinction
- **Requirement IDs**: REQ-034
- **Method**:
  1. Establish loopback connection (127.0.0.1)
  2. Establish local network connection (192.168.x.x, 10.x.x.x)
  3. Establish external connection attempt
  4. Verify correct classification of each
- **Expected Pass Result**: Loopback classified as allowed; external classified as forbidden
- **Expected Fail-Closed Result**: Conservative classification if uncertain
- **Can Run Without GPU/Model/Docker**: Yes

---

## 5. Cryptographic Certificate Tests

### TEST-SEC-013: Certificate Tampering Rejection
- **Requirement IDs**: REQ-048, REQ-220, REQ-225
- **Method**:
  1. Generate valid certificate using certificate.py
  2. Tamper with certificate payload (modify egress_events, run_id, or timestamps)
  3. Run verify_certificate.py on tampered certificate
  4. Verify verification fails
- **Expected Pass Result**: Verification fails; exit code non-zero; tampering detected
- **Expected Fail-Closed Result**: Tampered certificate rejected; no false positive validation
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-014: Hash Chain Tampering Rejection
- **Requirement IDs**: REQ-042, REQ-043, REQ-048
- **Method**:
  1. Generate valid certificate
  2. Modify hash_chain_head value
  3. Run verify_certificate.py
  4. Verify reconstruction of hash chain does not match modified head
- **Expected Pass Result**: Hash chain verification fails
- **Expected Fail-Closed Result**: Tampered certificate rejected
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-015: Invalid Signature Rejection
- **Requirement IDs**: REQ-044, REQ-048, REQ-049, REQ-050
- **Method**:
  1. Generate valid certificate
  2. Replace signature with invalid value
  3. Run verify_certificate.py
  4. Verify Ed25519 signature verification fails
- **Expected Pass Result**: Signature verification fails; exit code non-zero
- **Expected Fail-Closed Result**: Invalid signature detected; certificate rejected
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-016: Private Key Non-Exposure
- **Requirement IDs**: REQ-192, REQ-218, REQ-219, REQ-220
- **Method**:
  1. Inspect all API responses for private key material
  2. Inspect logs for private key material
  3. Attempt to retrieve private key via API
  4. Verify private key never appears in responses or logs
- **Expected Pass Result**: Private key never exposed; only public key returned with certificate
- **Expected Fail-Closed Result**: API refuses to return private key; logs sanitized
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-017: Certificate Structure Verification
- **Requirement IDs**: REQ-047, REQ-048
- **Method**:
  1. Generate valid certificate
  2. Remove required field (e.g., run_id, signature, hash_chain_head)
  3. Run verify_certificate.py
  4. Verify structural validation fails
- **Expected Pass Result**: Missing required field detected; verification fails
- **Expected Fail-Closed Result**: Malformed certificate rejected
- **Can Run Without GPU/Model/Docker**: Yes

---

## 6. Docker/Network Isolation Tests

### TEST-SEC-018: Docker Internal Network Behavior
- **Requirement IDs**: REQ-206, REQ-207, REQ-208, REQ-210
- **Method**:
  1. Start docker-compose.yml
  2. Inspect network configuration
  3. Verify api and web services are on internal network
  4. Attempt external connection from container
  5. Verify no accidental Internet connectivity
- **Expected Pass Result**: Services isolated on internal network; no external egress by default
- **Expected Fail-Closed Result**: Network isolation enforced
- **Can Run Without GPU/Model/Docker**: No (requires Docker)

### TEST-SEC-019: Sandbox Exec Network None
- **Requirement IDs**: REQ-170, REQ-171, REQ-172, REQ-220
- **Method**:
  1. Execute sandboxed workload via sandbox_exec.py
  2. Verify docker run uses --network none
  3. Attempt external connection from within sandbox
  4. Verify connection fails
- **Expected Pass Result**: Sandbox has no network access; external connections fail
- **Expected Fail-Closed Result**: Untrusted workloads isolated from network
- **Can Run Without GPU/Model/Docker**: No (requires Docker)

### TEST-SEC-020: Subprocess Fallback Limitations
- **Requirement IDs**: REQ-171, REQ-172, REQ-173, REQ-174
- **Method**:
  1. Disable Docker availability
  2. Execute workload via subprocess fallback
  3. Verify fallback does not have Internet access (firewall rules, restricted environment)
  4. Verify user-controlled shell strings not executed through unrestricted shell
- **Expected Pass Result**: Fallback documented and restricted; no silent Internet access
- **Expected Fail-Closed Result**: Fallback more restrictive than permissive; limitations documented
- **Can Run Without GPU/Model/Docker**: Yes (requires Docker to be unavailable)

---

## 7. Offline/Air-Gap Tests

### TEST-SEC-021: Offline Behavior
- **Requirement IDs**: REQ-001, REQ-009, REQ-220
- **Method**:
  1. Disconnect network (or block external access via firewall)
  2. Run core workflow (model loading, routing, inference if model available)
  3. Verify system operates without Internet connectivity
  4. Verify no cloud API calls attempted
- **Expected Pass Result**: System functions without Internet; no external dependencies
- **Expected Fail-Closed Result**: No silent cloud fallback; errors reported locally
- **Can Run Without GPU/Model/Docker**: Partially (requires model for full inference test)

### TEST-SEC-022: No Cloud Fallback Behavior
- **Requirement IDs**: REQ-001, REQ-009, REQ-010
- **Method**:
  1. Monitor network traffic during operation
  2. Verify no outbound connections to cloud APIs (OpenAI, Anthropic, etc.)
  3. Verify all inference is local
- **Expected Pass Result**: No cloud API connections; all processing local
- **Expected Fail-Closed Result**: If local processing fails, report failure rather than cloud fallback
- **Can Run Without GPU/Model/Docker**: Yes (can monitor for attempted connections)

---

## 8. Audit Log Tests

### TEST-SEC-023: Audit Log Append-Only Behavior
- **Requirement IDs**: REQ-175, REQ-176, REQ-177, REQ-220
- **Method**:
  1. Write audit entries via application
  2. Attempt to UPDATE or DELETE entries through application layer
  3. Verify modifications are rejected
- **Expected Pass Result**: UPDATE/DELETE operations rejected; only INSERT allowed
- **Expected Fail-Closed Result**: Audit log integrity preserved at application level
- **Can Run Without GPU/Model/Docker**: Yes

### TEST-SEC-024: Sensitive Data Non-Logging
- **Requirement IDs**: REQ-180, REQ-218, REQ-220
- **Method**:
  1. Perform operations involving signing keys, secrets, credentials
  2. Inspect audit logs
  3. Verify sensitive data not logged
- **Expected Pass Result**: Private keys, secrets, credentials absent from logs
- **Expected Fail-Closed Result**: Logs sanitized; sensitive data protected
- **Can Run Without GPU/Model/Docker**: Yes

---

## 9. Summary Matrix

| Test ID | Can Run Without GPU | Can Run Without Model | Can Run Without Docker |
|---------|---------------------|-----------------------|------------------------|
| TEST-SEC-001 | Yes | Yes | Yes |
| TEST-SEC-002 | Yes | Yes | Yes |
| TEST-SEC-003 | Yes | Yes | Yes |
| TEST-SEC-004 | Yes | Yes | Yes |
| TEST-SEC-005 | Yes | Yes | Yes |
| TEST-SEC-006 | Yes | Yes | Yes |
| TEST-SEC-007 | Yes | Yes | Yes |
| TEST-SEC-008 | Yes | Yes | Yes |
| TEST-SEC-009 | Yes | Yes | Yes |
| TEST-SEC-010 | Yes | Yes | Yes |
| TEST-SEC-011 | Yes | Yes | Partially |
| TEST-SEC-012 | Yes | Yes | Yes |
| TEST-SEC-013 | Yes | Yes | Yes |
| TEST-SEC-014 | Yes | Yes | Yes |
| TEST-SEC-015 | Yes | Yes | Yes |
| TEST-SEC-016 | Yes | Yes | Yes |
| TEST-SEC-017 | Yes | Yes | Yes |
| TEST-SEC-018 | Yes | Yes | No |
| TEST-SEC-019 | Yes | Yes | No |
| TEST-SEC-020 | Yes | Yes | Yes |
| TEST-SEC-021 | Yes | Partially | Yes |
| TEST-SEC-022 | Yes | Yes | Yes |
| TEST-SEC-023 | Yes | Yes | Yes |
| TEST-SEC-024 | Yes | Yes | Yes |

---

## Execution Order

1. **Phase 1 Security Tests** (after Phase 1 completion):
   - TEST-SEC-001, TEST-SEC-002, TEST-SEC-003 (model integrity)

2. **Phase 2 Security Tests** (after Phase 2 completion):
   - TEST-SEC-004 through TEST-SEC-007 (filesystem)
   - TEST-SEC-008, TEST-SEC-009 (RBAC)
   - TEST-SEC-010, TEST-SEC-011, TEST-SEC-012 (egress)
   - TEST-SEC-013 through TEST-SEC-017 (certificates)
   - TEST-SEC-023, TEST-SEC-024 (audit log)

3. **Phase 3+ Security Tests** (after Phase 3 completion):
   - TEST-SEC-018, TEST-SEC-019 (Docker isolation)
   - TEST-SEC-020 (sandbox fallback)
   - TEST-SEC-021, TEST-SEC-022 (offline behavior)

All tests must pass before pilot-ready declaration (REQ-225).
