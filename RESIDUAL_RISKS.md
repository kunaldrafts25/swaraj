# SWARAJ v2 Residual Risks

This document lists risks that are genuinely unavoidable due to physics, operating system constraints, hardware constraints, or explicit scope decisions.

**Note:** Risks marked as BLOCKED or NEEDS_EVIDENCE are NOT ACCEPTED. They require explicit scope decisions or evidence collection before production deployment.

---

## Risk Register

| ID | Risk | Category | Why Unavoidable | Compensating Control | Status |
|----|------|----------|-----------------|---------------------|--------|
| RR-001 | GPU performance unmeasured | Environment | No GPU hardware in test environment | CPU-only mode fully validated, GPU path implemented and tested via unit tests | ⚠️ NEEDS_EVIDENCE |
| RR-002 | Browser compatibility (Safari/Edge) | Testing Scope | CI limited to Chrome/Firefox | Standard web APIs used, no browser-specific features | ⚠️ NEEDS_EVIDENCE |
| RR-003 | OCR accuracy variance | Model Limitation | Depends on document quality, scan resolution, language | Self-check validation catches extraction errors, human review step in workflow | ✅ COMPENSATED |
| RR-004 | Single-node concurrency limit | Architecture | Without Redis cluster, must limit to prevent resource exhaustion | Hard limit of 5 concurrent runs enforced in config | ✅ COMPENSATED |
| RR-005 | Docker daemon required | Infrastructure | Sandbox execution requires Docker runtime | Fail-closed: if Docker unavailable, untrusted execution blocked entirely | ✅ FAIL_CLOSED |

---

## Eliminated Risks (No Longer Accepted)

The following were previously listed as "pilot limitations" but have been **ELIMINATED**:

| Former Limitation | Resolution |
|------------------|------------|
| OCR requires installation | ✅ Bundled in Docker image with self-test |
| Flat-file authentication | ✅ Replaced with SQLite + Argon2id + JWT |
| Weaker sandbox fallback | ✅ Removed entirely; Docker mandatory |
| No distributed clustering | ✅ Implemented `swaraj.cluster` module |
| Hardware latency not measured | ✅ `measure_hardware.py` with fail-closed routing |

---

## Risk Status Summary

- **COMPENSATED:** 2 risks (adequate controls in place)
- **FAIL_CLOSED:** 1 risk (system refuses to operate rather than accept weakness)
- **NEEDS_EVIDENCE:** 2 risks (require physical hardware/browser testing)
- **ACCEPTED:** 0 risks (zero accepted weaknesses)

**Last Updated:** 2024-01-15  
**Version:** 2.0.0
