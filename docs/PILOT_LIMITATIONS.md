# SWARAJ v2 — Pilot Limitations

This document records known limitations, trade-offs, and operational boundaries for the pilot phase.

| ID | Area | Limitation | Severity | Rationale / Mitigation |
|----|------|------------|----------|------------------------|
| LIM-001 | Hardware | GPU performance unmeasured in CI | Low | System designed with fail-closed CPU-only execution (Tier 3) fully validated. Hardware benchmarking script (`scripts/measure_hardware.py`) provides local calibration. |
| LIM-002 | Identity | Flat-file user storage (`users.json`) | Low | Appropriate for single-site pilot (<10 operators). Production deployment requires enterprise LDAP/OIDC integration. |
| LIM-003 | Architecture | Single-node deployment | Medium | Pilot runs as a sovereign standalone node. Does not support multi-node distributed clustering. |
| LIM-004 | Provisioning | Manual model distribution | Low | Model artifact (`qwen3-4b-instruct-q4_k_m.gguf`) must be provisioned via air-gap media with verified SHA256 checksum. |
| LIM-005 | Vision/OCR | OCR accuracy varies across noisy scans | Medium | Human-in-the-loop review workflow included; self-check stage inspects generated outputs against required section schemas. |
| LIM-006 | Network | Zero runtime internet access required | Operational | External cloud calls are strictly forbidden; egress monitor triggers automated kill-switch upon non-loopback network socket creation. |
