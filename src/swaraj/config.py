"""Configuration management for SWARAJ v2.

Uses Pydantic Settings for environment-based configuration with fail-closed defaults.
"""

import sys
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_bundle_dir() -> Path:
    """Return read-only bundle directory (supports PyInstaller sys._MEIPASS)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def _get_base_dir() -> Path:
    """Return application base directory (where executable or project root lives)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


class SwarajSettings(BaseSettings):
    """SWARAJ application settings.
    
    All security-sensitive defaults are fail-closed.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="SWARAJ_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application identity
    app_name: str = "SWARAJ"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # Paths - relative to bundle root or base directory
    project_root: Path = _get_bundle_dir()
    models_dir: Path = _get_base_dir() / "models"
    registry_dir: Path = _get_bundle_dir() / "src" / "swaraj" / "registry" / "manifests"
    data_dir: Path = _get_base_dir() / "data"
    logs_dir: Path = _get_base_dir() / "logs"
    policy_dir: Path = _get_bundle_dir() / "policies"
    users_file: Path = _get_bundle_dir() / "users.json"
    audit_db_path: Path = _get_base_dir() / "data" / "audit.db"
    
    # Security settings
    signing_key_dir: Path = _get_base_dir() / "keys"
    keys_dir: Path = _get_base_dir() / "keys"
    signing_private_key_path: Optional[Path] = None
    signing_public_key_path: Optional[Path] = None
    
    # Model settings
    default_model_name: str = "qwen3-4b-instruct"
    require_checksum_verification: bool = True
    allow_placeholder_checksums: bool = False
    
    # Hardware calibration
    gpu_layers_auto: bool = True
    max_context_length: int = 8192
    
    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    @property
    def private_key_path(self) -> Path:
        """Return the private key path, creating directory if needed."""
        if self.signing_private_key_path:
            return self.signing_private_key_path
        self.signing_key_dir.mkdir(parents=True, exist_ok=True)
        return self.signing_key_dir / "signing_private.pem"
    
    @property
    def public_key_path(self) -> Path:
        """Return the public key path."""
        if self.signing_public_key_path:
            return self.signing_public_key_path
        return self.signing_key_dir / "signing_public.pem"
    
    def validate_paths(self) -> None:
        """Validate that critical paths exist or can be created.
        
        Raises:
            RuntimeError: If a required path cannot be created.
        """
        critical_dirs = [
            self.models_dir,
            self.data_dir,
            self.logs_dir,
            self.signing_key_dir,
        ]
        for dir_path in critical_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise RuntimeError(f"Cannot create required directory {dir_path}: {e}") from e


# Global settings instance
settings = SwarajSettings()


def get_settings() -> SwarajSettings:
    """Return the global settings instance."""
    return settings
