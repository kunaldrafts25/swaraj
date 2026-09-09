#!/usr/bin/env python3
"""
SWARAJ Certificate Verification Script - Standalone Ed25519 certificate verification.

This script runs independently from the FastAPI application.

Usage:
    python verify_certificate.py path/to/certificate.json

Exit codes:
    0 - Certificate verified successfully
    1 - Verification failed (tampering, invalid signature, etc.)
    2 - Usage error (file not found, invalid JSON, etc.)

Requirements:
    - No network access required
    - No private key required
    - Only needs the certificate JSON file
"""

import sys
import json
from pathlib import Path


def load_certificate(cert_path: str) -> dict:
    """Load certificate from JSON file."""
    path = Path(cert_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Certificate file not found: {cert_path}")
    
    with open(path, 'r') as f:
        return json.load(f)


def verify_certificate_standalone(cert_data: dict) -> tuple[bool, str]:
    """
    Verify certificate using swaraj.governance.certificate module.
    
    Returns:
        Tuple of (valid, reason)
    """
    from swaraj.governance.certificate import (
        RunCertificate,
        CertificateManager,
    )
    from tempfile import TemporaryDirectory
    
    # Reconstruct certificate object
    try:
        cert = RunCertificate(
            run_id=cert_data["run_id"],
            started_at=cert_data["started_at"],
            ended_at=cert_data["ended_at"],
            model_used=cert_data["model_used"],
            egress_events=cert_data.get("egress_events", []),
            hash_chain_head=cert_data["hash_chain_head"],
            signature=cert_data["signature"],
            signer_pubkey=cert_data["signer_pubkey"],
        )
    except KeyError as e:
        return False, f"Missing required field: {e}"
    
    # Create a temporary certificate manager for verification
    # We only need the public key which is embedded in the certificate
    with TemporaryDirectory() as tmpdir:
        try:
            cm = CertificateManager(Path(tmpdir))
            result = cm.verify_certificate(cert)
            return result.valid, result.reason
        except Exception as e:
            return False, f"Verification error: {str(e)}"


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python verify_certificate.py <certificate.json>")
        print("")
        print("Verifies a SWARAJ run certificate using Ed25519 signature.")
        print("")
        print("Exit codes:")
        print("  0 - Certificate verified successfully")
        print("  1 - Verification failed (tampering, invalid signature)")
        print("  2 - Usage error (file not found, invalid JSON)")
        sys.exit(2)
    
    cert_path = sys.argv[1]
    
    print(f"Loading certificate: {cert_path}")
    
    try:
        cert_data = load_certificate(cert_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in certificate file: {e}")
        sys.exit(2)
    
    print(f"Certificate for run: {cert_data.get('run_id', 'unknown')}")
    print(f"Model used: {cert_data.get('model_used', 'unknown')}")
    print(f"Started: {cert_data.get('started_at', 'unknown')}")
    print(f"Ended: {cert_data.get('ended_at', 'unknown')}")
    print("")
    
    # Verify the certificate
    print("Verifying Ed25519 signature...")
    valid, reason = verify_certificate_standalone(cert_data)
    
    if valid:
        print("")
        print("=" * 50)
        print("VERIFICATION SUCCESSFUL")
        print("=" * 50)
        print(f"Reason: {reason}")
        print("")
        print("The certificate is authentic and has not been tampered with.")
        sys.exit(0)
    else:
        print("")
        print("=" * 50)
        print("VERIFICATION FAILED")
        print("=" * 50)
        print(f"Reason: {reason}")
        print("")
        print("WARNING: The certificate may have been tampered with or is invalid.")
        print("Do not trust the associated run artifacts.")
        sys.exit(1)


if __name__ == "__main__":
    main()
