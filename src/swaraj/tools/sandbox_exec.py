"""
SWARAJ Sandbox Execution - Docker-only isolated execution.

SECURITY BOUNDARIES:
- Docker with --network none REQUIRED for all untrusted execution
- NO fallback available - fails closed if Docker unavailable
- Never executes user-controlled shell strings through unrestricted shell
"""

import subprocess
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any


class DockerUnavailableError(Exception):
    """Raised when Docker is unavailable and untrusted execution cannot proceed."""
    pass


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    used_docker: bool = True
    degraded_mode: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "used_docker": self.used_docker,
            "degraded_mode": self.degraded_mode,
            "error_message": self.error_message,
        }


class SandboxExecutor:
    """
    Executes untrusted code in Docker sandbox with --network none.
    
    SECURITY BOUNDARIES:
    - Docker with --network none REQUIRED
    - NO fallback - fails closed if Docker unavailable
    - No shell execution for user-controlled strings
    
    If Docker is unavailable, raises DockerUnavailableError.
    Untrusted execution is BLOCKED, not downgraded.
    """
    
    def __init__(
        self,
        docker_image: str = "python:3.11-slim",
        workspace_mount: Optional[Path] = None,
        timeout_seconds: int = 60,
    ):
        self.docker_image = docker_image
        self.workspace_mount = workspace_mount
        self.timeout_seconds = timeout_seconds
        
        # Check Docker availability
        self._docker_available = self._check_docker()
        
        # FAIL CLOSED: Raise immediately if Docker unavailable
        if not self._docker_available:
            raise DockerUnavailableError(
                "Untrusted execution requires Docker with --network none. "
                "Docker daemon is not available. "
                "No fallback is provided for security reasons. "
                "Install Docker and ensure the daemon is running."
            )
    
    def _check_docker(self) -> bool:
        """Check if Docker is available and functional."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False
    
    @property
    def docker_available(self) -> bool:
        """Check if Docker is available."""
        return self._docker_available
    
    @property
    def is_degraded(self) -> bool:
        """Always False - degraded mode removed."""
        return False
    
    def execute(
        self,
        python_code: str,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
    ) -> SandboxResult:
        """
        Execute Python code in Docker sandbox with --network none.
        
        SECURITY BOUNDARY:
        - Uses Docker --network none (REQUIRED)
        - NO fallback - raises DockerUnavailableError if Docker unavailable
        - Never uses shell=True with user-controlled input
        
        Args:
            python_code: Python code to execute
            args: Command-line arguments for the script
            env: Environment variables (filtered for security)
        
        Returns:
            SandboxResult with execution outcome
        
        Raises:
            DockerUnavailableError: If Docker is not available
            RuntimeError: If execution fails catastrophically
        """
        # Already checked in __init__, but verify again
        if not self._docker_available:
            raise DockerUnavailableError("Docker unavailable")
        
        return self._execute_docker(python_code, args, env)
    
    def _execute_docker(
        self,
        python_code: str,
        args: Optional[list[str]],
        env: Optional[dict[str, str]],
    ) -> SandboxResult:
        """Execute using Docker with --network none."""
        try:
            # Build docker command with network isolation
            cmd = [
                "docker", "run", "--rm",
                "--network", "none",  # SECURITY: No network access
                "--read-only",  # Read-only filesystem where possible
                "--tmpfs", "/tmp",  # Writable temp directory
            ]
            
            # Mount workspace if specified
            if self.workspace_mount and self.workspace_mount.exists():
                cmd.extend([
                    "-v", f"{self.workspace_mount}:/workspace:ro",  # Read-only mount
                ])
            
            cmd.extend([
                self.docker_image,
                "python", "-c", python_code,
            ])
            
            # Add arguments if provided
            if args:
                cmd.extend(args)
            
            # Build environment
            docker_env = {}
            if env:
                # Filter out dangerous environment variables
                safe_keys = {'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE'}
                for key in env:
                    if key in safe_keys:
                        docker_env[key] = env[key]
            
            # Convert env to docker format
            for key, value in docker_env.items():
                cmd.insert(3, "-e")  # Insert after "run"
                cmd.insert(4, f"{key}={value}")
            
            # Execute without shell
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,  # SECURITY: Never use shell
            )
            
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                used_docker=True,
                degraded_mode=False,
            )
            
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self.timeout_seconds}s",
                return_code=-1,
                used_docker=True,
                degraded_mode=False,
                error_message="timeout",
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                used_docker=True,
                degraded_mode=False,
                error_message=f"docker_execution_error: {e}",
            )
    
    def get_status(self) -> dict[str, Any]:
        """Get executor status for API/monitoring."""
        return {
            "docker_available": self._docker_available,
            "using_docker": True,  # Always uses Docker or fails
            "degraded_mode": False,  # No degraded mode
            "docker_image": self.docker_image,
            "workspace_mount": str(self.workspace_mount) if self.workspace_mount else None,
            "timeout_seconds": self.timeout_seconds,
            "security_note": "Full network isolation via Docker --network none (REQUIRED)",
        }
