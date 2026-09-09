"""
SWARAJ Hardware Detection & Calibration Module.

Automatically detects available hardware (NVIDIA GPU via pynvml / nvidia-smi,
Apple Silicon MPS, or CPU-only) and computes the optimal llama-cpp-python
n_gpu_layers setting.  Results are persisted to disk so that the first cold-start
penalty is paid only once.

No network calls are made.  All detection is strictly local / air-gapped.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("swaraj.runtime.hardware")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class HardwareTier(str, Enum):
    """Hardware capability tier, coarsest to finest."""
    CPU_ONLY   = "cpu_only"
    CPU_AVX2   = "cpu_avx2"
    GPU_PARTIAL = "gpu_partial"   # < 6 GB VRAM
    GPU_FULL    = "gpu_full"      # ≥ 6 GB VRAM — can offload all layers
    GPU_HIGH_END = "gpu_high_end" # ≥ 12 GB VRAM


@dataclass
class HardwareInfo:
    """Snapshot of the host hardware capabilities."""
    tier: str = HardwareTier.CPU_ONLY
    gpu_name: Optional[str] = None
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    cpu_cores: int = 1
    ram_total_mb: int = 0
    n_gpu_layers_recommended: int = 0
    n_threads_recommended: int = 4
    detected_at: float = field(default_factory=time.time)
    detection_method: str = "none"
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "HardwareInfo":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_via_pynvml() -> Optional[HardwareInfo]:
    """Try NVIDIA detection via pynvml (fastest, most accurate)."""
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        if count == 0:
            return None

        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode()

        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_total_mb = mem.total // (1024 * 1024)
        vram_free_mb = mem.free // (1024 * 1024)
        pynvml.nvmlShutdown()

        tier, n_layers = _classify_gpu(vram_total_mb)
        return HardwareInfo(
            tier=tier,
            gpu_name=name,
            vram_total_mb=vram_total_mb,
            vram_free_mb=vram_free_mb,
            n_gpu_layers_recommended=n_layers,
            detection_method="pynvml",
        )
    except Exception as exc:
        logger.debug("pynvml detection failed: %s", exc)
        return None


def _detect_via_nvidia_smi() -> Optional[HardwareInfo]:
    """Fall back to parsing nvidia-smi output."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        line = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            return None

        name = parts[0]
        vram_total_mb = int(float(parts[1]))
        vram_free_mb = int(float(parts[2]))

        tier, n_layers = _classify_gpu(vram_total_mb)
        return HardwareInfo(
            tier=tier,
            gpu_name=name,
            vram_total_mb=vram_total_mb,
            vram_free_mb=vram_free_mb,
            n_gpu_layers_recommended=n_layers,
            detection_method="nvidia_smi",
        )
    except Exception as exc:
        logger.debug("nvidia-smi detection failed: %s", exc)
        return None


def _detect_apple_mps() -> Optional[HardwareInfo]:
    """Detect Apple Silicon MPS availability."""
    try:
        import platform
        if platform.system() != "Darwin":
            return None
        # Try torch MPS detection
        import torch  # type: ignore
        if not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            return None
        import psutil
        ram = psutil.virtual_memory()
        ram_mb = ram.total // (1024 * 1024)
        # Apple unified memory — use a conservative fraction for GPU
        vram_approx = ram_mb // 2
        tier, n_layers = _classify_gpu(vram_approx)
        return HardwareInfo(
            tier=tier,
            gpu_name="Apple Silicon (MPS)",
            vram_total_mb=vram_approx,
            vram_free_mb=vram_approx,
            n_gpu_layers_recommended=n_layers,
            detection_method="apple_mps",
        )
    except Exception as exc:
        logger.debug("Apple MPS detection failed: %s", exc)
        return None


def _classify_gpu(vram_mb: int) -> tuple[str, int]:
    """Return (tier, recommended_n_gpu_layers) for the given VRAM size.

    IMPORTANT: Always returns n_gpu_layers=-1 (full GPU offload) when any GPU
    is detected.  Partial offload (some layers GPU, some CPU) triggers a hard
    GGML_ASSERT crash in llama-cpp-python ≤0.3.35 with Qwen3 tensor shapes.
    Full offload avoids the problematic CPU repack code path entirely.
    """
    if vram_mb >= 12_000:
        return HardwareTier.GPU_HIGH_END, -1   # full offload — all layers on GPU
    elif vram_mb >= 6_000:
        return HardwareTier.GPU_FULL, -1        # full offload
    elif vram_mb >= 2_000:
        return HardwareTier.GPU_PARTIAL, -1     # full offload (Qwen3-4B-Q4 fits in 4 GB)
    else:
        return HardwareTier.CPU_ONLY, 0         # no GPU — pure CPU inference


def _detect_cpu_baseline() -> HardwareInfo:
    """Detect CPU / RAM baseline (always succeeds)."""
    try:
        import psutil
        cpu_count = psutil.cpu_count(logical=False) or os.cpu_count() or 1
        ram_mb = psutil.virtual_memory().total // (1024 * 1024)
    except Exception:
        cpu_count = os.cpu_count() or 1
        ram_mb = 0

    # Prefer AVX2 for faster CPU inference if available
    try:
        import cpuinfo  # type: ignore
        info = cpuinfo.get_cpu_info()
        flags = info.get("flags", [])
        tier = HardwareTier.CPU_AVX2 if "avx2" in flags else HardwareTier.CPU_ONLY
    except Exception:
        tier = HardwareTier.CPU_ONLY

    n_threads = min(cpu_count, 8)
    return HardwareInfo(
        tier=tier,
        cpu_cores=cpu_count,
        ram_total_mb=ram_mb,
        n_gpu_layers_recommended=0,
        n_threads_recommended=n_threads,
        detection_method="cpu_baseline",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_CACHE_VERSION = 2
_CALIBRATION_TTL_SECONDS = 3600  # re-detect every hour


class HardwareDetector:
    """
    Singleton-friendly hardware detector with disk-persisted calibration cache.

    Usage::

        detector = HardwareDetector(cache_path=Path("data/hw_calibration.json"))
        info = detector.detect()
        print(info.tier, info.n_gpu_layers_recommended)
    """

    def __init__(self, cache_path: Optional[Path] = None):
        self._cache_path = cache_path
        self._cached: Optional[HardwareInfo] = None

    def detect(self, force: bool = False) -> HardwareInfo:
        """Return hardware info, using disk cache when valid."""
        if not force:
            cached = self._load_cache()
            if cached is not None:
                self._cached = cached
                return cached

        info = self._run_detection()
        self._cached = info
        self._save_cache(info)
        return info

    @property
    def cached(self) -> Optional[HardwareInfo]:
        """Return last detection result without triggering a new detection."""
        return self._cached

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_detection(self) -> HardwareInfo:
        logger.info("Running hardware detection…")

        # Try GPU detection in order of reliability
        for fn in (_detect_via_pynvml, _detect_via_nvidia_smi, _detect_apple_mps):
            result = fn()
            if result is not None:
                # Enrich with CPU info
                cpu_info = _detect_cpu_baseline()
                result.cpu_cores = cpu_info.cpu_cores
                result.ram_total_mb = cpu_info.ram_total_mb
                result.n_threads_recommended = cpu_info.n_threads_recommended
                logger.info(
                    "GPU detected via %s: %s, VRAM=%dMB, tier=%s, n_gpu_layers=%d",
                    result.detection_method,
                    result.gpu_name,
                    result.vram_total_mb,
                    result.tier,
                    result.n_gpu_layers_recommended,
                )
                return result

        # CPU-only fallback
        info = _detect_cpu_baseline()
        logger.info(
            "No GPU detected — CPU-only mode, tier=%s, threads=%d",
            info.tier,
            info.n_threads_recommended,
        )
        return info

    def _load_cache(self) -> Optional[HardwareInfo]:
        if self._cache_path is None or not self._cache_path.exists():
            return None
        try:
            data = json.loads(self._cache_path.read_text())
            if data.get("_version") != _CACHE_VERSION:
                return None
            age = time.time() - data.get("detected_at", 0)
            if age > _CALIBRATION_TTL_SECONDS:
                logger.debug("Hardware cache expired (age=%.0fs)", age)
                return None
            return HardwareInfo.from_dict({k: v for k, v in data.items() if k != "_version"})
        except Exception as exc:
            logger.debug("Could not load hardware cache: %s", exc)
            return None

    def _save_cache(self, info: HardwareInfo) -> None:
        if self._cache_path is None:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = info.to_dict()
            payload["_version"] = _CACHE_VERSION
            self._cache_path.write_text(json.dumps(payload, indent=2))
        except Exception as exc:
            logger.warning("Could not save hardware cache: %s", exc)


# Module-level singleton — lazily initialised
_detector: Optional[HardwareDetector] = None


def get_hardware_detector(cache_path: Optional[Path] = None) -> HardwareDetector:
    """Return the module-level singleton detector, creating it if needed."""
    global _detector
    if _detector is None:
        _detector = HardwareDetector(cache_path=cache_path)
    return _detector


def detect_hardware(force: bool = False, cache_path: Optional[Path] = None) -> HardwareInfo:
    """Convenience one-liner: detect (or load cached) hardware info."""
    return get_hardware_detector(cache_path=cache_path).detect(force=force)
