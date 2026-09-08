"""
SWARAJ Sandbox Execution - Restricted subprocess execution with Docker fallback.

SECURITY BOUNDARIES:
- Primary: docker run --network none for network isolation
- Fallback: restricted subprocess (no shell, no network flags) when Docker unavailable
- Never executes user-controlled shell strings through unrestricted shell
- Documents security limitations of fallback mode
"""

import subprocess
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    used_docker: bool
    degraded_mode: bool
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
    Executes untrusted code in restricted sandbox.
    
    SECURITY BOUNDARIES:
    - Docker with --network none preferred
    - Fallback mode explicitly flagged as degraded
    - No shell execution for user-controlled strings
    - Network access blocked in both modes where possible
    
    LIMITATIONS:
    - Fallback mode cannot guarantee network isolation as strongly as Docker
    - Fallback relies on subprocess restrictions, not containerization
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
        """Check if running in degraded (non-Docker) mode."""
        return not self._docker_available
    
    def execute(
        self,
        python_code: str,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
    ) -> SandboxResult:
        """
        Execute Python code in sandbox.
        
        SECURITY BOUNDARY:
        - Uses Docker --network none when available
        - Falls back to restricted subprocess (degraded mode)
        - Never uses shell=True with user-controlled input
        
        Args:
            python_code: Python code to execute
            args: Command-line arguments for the script
            env: Environment variables (filtered for security)
        
        Returns:
            SandboxResult with execution outcome
        
        Raises:
            RuntimeError: If execution fails catastrophically
        """
        if self._docker_available:
            return self._execute_docker(python_code, args, env)
        else:
            return self._execute_fallback(python_code, args, env)
    
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
    
    def _execute_fallback(
        self,
        python_code: str,
        args: Optional[list[str]],
        env: Optional[dict[str, str]],
    ) -> SandboxResult:
        """
        Execute using restricted subprocess (DEGRADED MODE).
        
        SECURITY LIMITATIONS:
        - Cannot guarantee network isolation
        - Relies on Python subprocess restrictions
        - Should only be used when Docker unavailable
        
        This is a BEST-EFFORT fallback, not a security equivalent to Docker.
        """
        try:
            # Build command without shell
            cmd = ["python", "-c", python_code]
            
            if args:
                cmd.extend(args)
            
            # Restrictive environment
            safe_env = {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",  # Don't import user site-packages
            }
            
            if env:
                # Only allow specific safe variables
                safe_keys = {'PYTHONPATH'}
                for key in env:
                    if key in safe_keys and key.isidentifier():
                        safe_env[key] = env[key]
            
            # Execute WITHOUT shell (SECURITY CRITICAL)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=safe_env,
                shell=False,  # SECURITY: Never use shell with user input
                cwd=str(self.workspace_mount) if self.workspace_mount else None,
            )
            
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                used_docker=False,
                degraded_mode=True,  # Explicitly flag degraded security
                error_message="WARNING: Degraded mode - network isolation not guaranteed" if result.returncode != 0 else None,
            )
            
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self.timeout_seconds}s",
                return_code=-1,
                used_docker=False,
                degraded_mode=True,
                error_message="timeout",
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                used_docker=False,
                degraded_mode=True,
                error_message=f"fallback_execution_error: {e}",
            )
    
    def get_status(self) -> dict[str, Any]:
        """Get executor status for API/monitoring."""
        return {
            "docker_available": self._docker_available,
            "using_docker": self._docker_available,
            "degraded_mode": not self._docker_available,
            "docker_image": self.docker_image,
            "workspace_mount": str(self.workspace_mount) if self.workspace_mount else None,
            "timeout_seconds": self.timeout_seconds,
            "security_note": (
                "Full network isolation via Docker --network none"
                if self._docker_available
                else "DEGRADED: Fallback mode cannot guarantee network isolation"
            ),
        }
