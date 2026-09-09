"""Tests for SWARAJ Certificate - Ed25519 cryptographic attestation."""

import json
import pytest
from pathlib import Path

from swaraj.governance.certificate import (
    CertificateManager,
    RunCertificate,
    CertificateVerificationResult,
    CertificateGenerationError,
)


@pytest.fixture
def keys_dir(tmp_path):
    """Create temporary keys directory."""
    keys = tmp_path / "keys"
    keys.mkdir()
    return keys


@pytest.fixture
def cert_manager(keys_dir):
    """Create CertificateManager instance."""
    return CertificateManager(keys_dir)


@pytest.fixture
def sample_run_data():
    """Sample run data for certificate generation."""
    return {
        "run_id": "test-run-uuid-123",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:05:00Z",
        "model_used": "qwen3-4b@sha256:abc123",
        "egress_events": [],
        "hash_chain_head": "sha256:def456",
        "security_status": "success",
    }


class TestValidCertificate:
    """Test valid certificate generation and verification."""
    
    def test_generate_valid_certificate(self, cert_manager, sample_run_data):
        """Valid certificate can be generated."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        assert cert.run_id == sample_run_data["run_id"]
        assert cert.signature.startswith("ed25519:")
        assert cert.signer_pubkey.startswith("ed25519:")
    
    def test_verify_valid_certificate(self, cert_manager, sample_run_data):
        """Valid certificate verifies successfully."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        result = cert_manager.verify_certificate(cert)
        
        assert result.valid is True
        assert "verified successfully" in result.reason
    
    def test_certificate_has_all_fields(self, cert_manager, sample_run_data):
        """Certificate contains all required fields."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        cert_dict = cert.to_dict()
        
        required_fields = [
            "run_id", "started_at", "ended_at", "model_used",
            "egress_events", "hash_chain_head", "signature", "signer_pubkey"
        ]
        
        for field in required_fields:
            assert field in cert_dict


class TestTamperingDetection:
    """Test tampering detection."""
    
    def test_tampered_hash_chain_fails(self, cert_manager, sample_run_data):
        """Tampered hash chain fails verification."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        # Tamper with hash chain head
        cert_dict = cert.to_dict()
        cert_dict["hash_chain_head"] = "tampered_value"
        tampered_cert = RunCertificate.from_dict(cert_dict)
        
        result = cert_manager.verify_certificate(tampered_cert)
        
        assert result.valid is False
        assert "Signature verification failed" in result.reason
    
    def test_tampered_payload_fails(self, cert_manager, sample_run_data):
        """Tampered payload fails verification."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        # Tamper with run_id
        cert_dict = cert.to_dict()
        cert_dict["run_id"] = "different-run-id"
        tampered_cert = RunCertificate.from_dict(cert_dict)
        
        result = cert_manager.verify_certificate(tampered_cert)
        
        assert result.valid is False
    
    def test_invalid_signature_fails(self, cert_manager, sample_run_data):
        """Invalid signature fails verification."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        # Tamper with signature
        cert_dict = cert.to_dict()
        cert_dict["signature"] = "ed25519:0000000000000000"
        tampered_cert = RunCertificate.from_dict(cert_dict)
        
        result = cert_manager.verify_certificate(tampered_cert)
        
        assert result.valid is False


class TestSecurityFailedRun:
    """Test that security-failed runs cannot be certified."""
    
    def test_security_failed_run_rejected(self, cert_manager, sample_run_data):
        """Runs with security status 'failed' cannot be certified."""
        with pytest.raises(CertificateGenerationError) as exc_info:
            cert_manager.sign_certificate(
                run_id=sample_run_data["run_id"],
                started_at=sample_run_data["started_at"],
                ended_at=sample_run_data["ended_at"],
                model_used=sample_run_data["model_used"],
                egress_events=sample_run_data["egress_events"],
                hash_chain_head=sample_run_data["hash_chain_head"],
                security_status="failed",
            )
        
        assert "security status" in str(exc_info.value).lower()
    
    def test_forbidden_egress_rejected(self, cert_manager, sample_run_data):
        """Runs with forbidden egress cannot be certified."""
        egress_events = [
            {
                "timestamp": "2024-01-01T00:01:00Z",
                "remote_address": "8.8.8.8",
                "is_forbidden": True,
            }
        ]
        
        with pytest.raises(CertificateGenerationError) as exc_info:
            cert_manager.sign_certificate(
                run_id=sample_run_data["run_id"],
                started_at=sample_run_data["started_at"],
                ended_at=sample_run_data["ended_at"],
                model_used=sample_run_data["model_used"],
                egress_events=egress_events,
                hash_chain_head=sample_run_data["hash_chain_head"],
                security_status="success",
            )
        
        assert "forbidden egress" in str(exc_info.value).lower()


class TestPrivateKeySecurity:
    """Test private key security."""
    
    def test_private_key_not_in_certificate(self, cert_manager, sample_run_data):
        """Private key is not included in certificate."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        cert_dict = cert.to_dict()
        
        # Certificate should never contain private key
        assert "private_key" not in cert_dict
        assert "signer_pubkey" in cert_dict  # Public key is OK
    
    def test_private_key_file_permissions(self, keys_dir):
        """Private key file has restrictive permissions."""
        cert_manager = CertificateManager(keys_dir)
        private_key_path = keys_dir / "swaraj_private.key"
        
        # Check file permissions (should be 0600 on POSIX)
        import sys
        if sys.platform != "win32":
            import stat
            file_stat = private_key_path.stat()
            mode = file_stat.st_mode & 0o777
            assert mode == 0o600, f"Private key permissions should be 0600, got {oct(mode)}"
        else:
            assert private_key_path.exists()
    
    def test_public_key_exposed_safely(self, cert_manager):
        """Public key can be safely exposed."""
        public_pem = cert_manager.get_public_key_pem()
        
        assert "BEGIN PUBLIC KEY" in public_pem
        assert "PRIVATE" not in public_pem


class TestCertificateStructure:
    """Test certificate structure validation."""
    
    def test_missing_field_fails_verification(self, cert_manager, sample_run_data):
        """Certificate missing required field fails verification."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        # Remove a required field
        cert_dict = cert.to_dict()
        del cert_dict["run_id"]
        
        # Create malformed certificate
        incomplete_cert = RunCertificate(
            run_id="",  # Empty but present
            started_at=cert_dict["started_at"],
            ended_at=cert_dict["ended_at"],
            model_used=cert_dict["model_used"],
            egress_events=cert_dict["egress_events"],
            hash_chain_head=cert_dict["hash_chain_head"],
            signature=cert_dict["signature"],
            signer_pubkey=cert_dict["signer_pubkey"],
        )
        
        # This will fail because run_id doesn't match what was signed
        result = cert_manager.verify_certificate(incomplete_cert)
        assert result.valid is False
    
    def test_invalid_signature_format_fails(self, cert_manager, sample_run_data):
        """Invalid signature format fails verification."""
        cert = cert_manager.sign_certificate(
            run_id=sample_run_data["run_id"],
            started_at=sample_run_data["started_at"],
            ended_at=sample_run_data["ended_at"],
            model_used=sample_run_data["model_used"],
            egress_events=sample_run_data["egress_events"],
            hash_chain_head=sample_run_data["hash_chain_head"],
            security_status=sample_run_data["security_status"],
        )
        
        cert_dict = cert.to_dict()
        cert_dict["signature"] = "invalid_format"
        bad_cert = RunCertificate.from_dict(cert_dict)
        
        result = cert_manager.verify_certificate(bad_cert)
        
        assert result.valid is False
        assert "Invalid signature format" in result.reason
