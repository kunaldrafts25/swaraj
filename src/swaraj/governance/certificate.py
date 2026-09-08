"""
SWARAJ Certificate Manager - Ed25519 cryptographic attestation.

SECURITY BOUNDARIES:
- Uses real Ed25519 via cryptography.hazmat.primitives.asymmetric.ed25519
- Private key NEVER exposed via API, logs, or responses
- Private key stored with restrictive filesystem permissions (0600)
- Certificate issuance fails if run security-failed or forbidden egress detected
- Deterministic canonicalization before signing (sorted JSON keys)
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


@dataclass
class RunCertificate:
    """Cryptographic certificate for a completed run."""
    run_id: str
    started_at: str
    ended_at: str
    model_used: str
    egress_events: list[dict]
    hash_chain_head: str
    signature: str
    signer_pubkey: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "model_used": self.model_used,
            "egress_events": self.egress_events,
            "hash_chain_head": self.hash_chain_head,
            "signature": self.signature,
            "signer_pubkey": self.signer_pubkey,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RunCertificate":
        """Create from dictionary."""
        return cls(
            run_id=data["run_id"],
            started_at=data["started_at"],
            ended_at=data["ended_at"],
            model_used=data["model_used"],
            egress_events=data.get("egress_events", []),
            hash_chain_head=data["hash_chain_head"],
            signature=data["signature"],
            signer_pubkey=data["signer_pubkey"],
        )


@dataclass
class CertificateVerificationResult:
    """Result of certificate verification."""
    valid: bool
    reason: str
    certificate: Optional[RunCertificate] = None


class CertificateManager:
    """
    Manages Ed25519 keypair and certificate generation/verification.
    
    SECURITY BOUNDARIES:
    - Private key never leaves filesystem
    - Private key never logged or returned by API
    - Key generated only if not exists
    - Restrictive permissions set on private key file
    """
    
    def __init__(self, keys_dir: Path):
        self.keys_dir = keys_dir
        self.private_key_path = keys_dir / "swaraj_private.key"
        self.public_key_path = keys_dir / "swaraj_public.key"
        
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key: Optional[Ed25519PublicKey] = None
        
        # Ensure directory exists
        keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or generate keypair
        self._load_or_generate_keypair()
    
    def _load_or_generate_keypair(self) -> None:
        """Load existing keypair or generate new one."""
        if self.private_key_path.exists() and self.public_key_path.exists():
            self._load_keypair()
        else:
            self._generate_keypair()
    
    def _load_keypair(self) -> None:
        """Load existing keypair from disk."""
        # Load private key
        private_pem = self.private_key_path.read_bytes()
        self._private_key = serialization.load_pem_private_key(
            private_pem,
            password=None,
            backend=default_backend(),
        )
        
        # Load public key
        public_pem = self.public_key_path.read_bytes()
        self._public_key = serialization.load_pem_public_key(
            public_pem,
            backend=default_backend(),
        )
    
    def _generate_keypair(self) -> None:
        """Generate new Ed25519 keypair with secure permissions."""
        # Generate keypair
        self._private_key = Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        
        # Serialize keys
        private_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        
        public_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        
        # Write private key with restrictive permissions (0600)
        # SECURITY: Only owner can read/write
        fd = self.private_key_path.open('wb')
        try:
            fd.write(private_pem)
        finally:
            fd.close()
        self.private_key_path.chmod(0o600)
        
        # Write public key
        self.public_key_path.write_bytes(public_pem)
    
    def get_public_key_pem(self) -> str:
        """Get public key as PEM string (safe to expose)."""
        if self._public_key is None:
            raise RuntimeError("Public key not available")
        
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode('utf-8')
    
    def _get_payload_hash(self, certificate_data: dict) -> str:
        """
        Compute deterministic hash of certificate payload.
        
        Uses sorted JSON keys for canonicalization.
        """
        # Remove signature fields for hashing
        payload = {k: v for k, v in certificate_data.items() 
                   if k not in ('signature', 'signer_pubkey')}
        
        # Deterministic JSON serialization
        payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
    
    def sign_certificate(
        self,
        run_id: str,
        started_at: str,
        ended_at: str,
        model_used: str,
        egress_events: list[dict],
        hash_chain_head: str,
        security_status: str,
    ) -> RunCertificate:
        """
        Generate and sign a certificate for a completed run.
        
        SECURITY BOUNDARY:
        - Fails if security_status is not "success"
        - Fails if forbidden egress detected
        
        Args:
            run_id: Unique run identifier
            started_at: ISO timestamp
            ended_at: ISO timestamp
            model_used: Model identifier with SHA256
            egress_events: List of observed egress events
            hash_chain_head: Head of audit log hash chain
            security_status: Must be "success" to certify
        
        Returns:
            Signed RunCertificate
        
        Raises:
            CertificateGenerationError: If run cannot be certified
        """
        # FAIL-CLOSED: Cannot certify failed runs
        if security_status != "success":
            raise CertificateGenerationError(
                f"Cannot certify run {run_id}: security status is '{security_status}'"
            )
        
        # FAIL-CLOSED: Check for forbidden egress
        for event in egress_events:
            if event.get("is_forbidden", False):
                raise CertificateGenerationError(
                    f"Cannot certify run {run_id}: forbidden egress detected"
                )
        
        # Build certificate data - preserve the original hash_chain_head from input
        cert_data = {
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "model_used": model_used,
            "egress_events": egress_events if egress_events else [],
            "hash_chain_head": hash_chain_head,  # Use the input value, don't overwrite
        }
        
        # Compute payload hash for signing (this is what gets signed)
        payload_json = json.dumps(cert_data, sort_keys=True, separators=(',', ':'))
        payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
        
        # Sign the payload hash
        if self._private_key is None:
            raise RuntimeError("Private key not available")
        
        message = payload_hash.encode('utf-8')
        signature = self._private_key.sign(message)
        
        # Encode signature as hex
        signature_hex = signature.hex()
        
        # Get public key as hex
        pubkey_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        pubkey_hex = pubkey_bytes.hex()
        
        return RunCertificate(
            run_id=run_id,
            started_at=started_at,
            ended_at=ended_at,
            model_used=model_used,
            egress_events=cert_data["egress_events"],
            hash_chain_head=hash_chain_head,  # Preserve original input
            signature=f"ed25519:{signature_hex}",
            signer_pubkey=f"ed25519:{pubkey_hex}",
        )
    
    def verify_certificate(self, certificate: RunCertificate) -> CertificateVerificationResult:
        """
        Verify a certificate's signature and structure.
        
        Can be used independently without access to private key.
        
        Args:
            certificate: Certificate to verify
        
        Returns:
            CertificateVerificationResult with validity status
        """
        try:
            # Verify structure
            required_fields = [
                "run_id", "started_at", "ended_at", "model_used",
                "egress_events", "hash_chain_head", "signature", "signer_pubkey"
            ]
            
            cert_dict = certificate.to_dict()
            for field_name in required_fields:
                if field_name not in cert_dict:
                    return CertificateVerificationResult(
                        valid=False,
                        reason=f"Missing required field: {field_name}",
                    )
            
            # Parse signature
            sig_parts = certificate.signature.split(":")
            if len(sig_parts) != 2 or sig_parts[0] != "ed25519":
                return CertificateVerificationResult(
                    valid=False,
                    reason="Invalid signature format",
                )
            signature_bytes = bytes.fromhex(sig_parts[1])
            
            # Parse public key
            pubkey_parts = certificate.signer_pubkey.split(":")
            if len(pubkey_parts) != 2 or pubkey_parts[0] != "ed25519":
                return CertificateVerificationResult(
                    valid=False,
                    reason="Invalid public key format",
                )
            pubkey_bytes = bytes.fromhex(pubkey_parts[1])
            
            # Reconstruct public key from raw bytes
            public_key = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            
            # Recompute payload hash (must match exactly what was signed)
            payload = {k: v for k, v in cert_dict.items() if k not in ('signature', 'signer_pubkey')}
            payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
            payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
            message = payload_hash.encode('utf-8')
            
            # Verify signature
            try:
                public_key.verify(signature_bytes, message)
            except InvalidSignature:
                return CertificateVerificationResult(
                    valid=False,
                    reason="Signature verification failed",
                )
            
            return CertificateVerificationResult(
                valid=True,
                reason="Certificate verified successfully",
                certificate=certificate,
            )
            
        except Exception as e:
            return CertificateVerificationResult(
                valid=False,
                reason=f"Verification error: {str(e)}",
            )


class CertificateGenerationError(Exception):
    """Raised when certificate generation fails."""
    pass
