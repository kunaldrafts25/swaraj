"""Configuration management for SWARAJ v2.

Uses Pydantic Settings for environment-based configuration with fail-closed defaults.
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    
    # Paths - relative to project root
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    models_dir: Path = Path(__file__).resolve().parent.parent.parent / "models"
    registry_dir: Path = Path(__file__).resolve().parent.parent.parent / "src" / "swaraj" / "registry" / "manifests"
    data_dir: Path = Path(__file__).resolve().parent.parent.parent / "data"
    logs_dir: Path = Path(__file__).resolve().parent.parent.parent / "logs"
    
    # Security settings
    signing_key_dir: Path = Path(__file__).resolve().parent.parent.parent / "keys"
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
