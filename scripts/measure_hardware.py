#!/usr/bin/env python3
"""
SWARAJ Hardware Measurement Script

Detects hardware capabilities and runs calibration inference.
Distinguishes TARGET performance from MEASURED performance.
Never fakes results - reports N/A when measurements unavailable.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


def detect_hardware() -> Dict[str, Any]:
    """Detect available hardware (CPU, GPU, VRAM)."""
    hardware = {
        "cpu_cores": os.cpu_count() or 0,
        "cpu_name": "Unknown",
        "gpu_available": False,
        "gpu_name": None,
        "vram_gb": 0,
        "platform": sys.platform
    }
    
    # Try to get CPU name
    try:
        if sys.platform == "linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        hardware["cpu_name"] = line.split(":")[1].strip()
                        break
    except Exception:
        pass
    
    # Try to detect NVIDIA GPU
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if lines:
                parts = lines[0].split(", ")
                hardware["gpu_available"] = True
                hardware["gpu_name"] = parts[0]
                try:
                    vram_mb = int(parts[1].replace(" MiB", ""))
                    hardware["vram_gb"] = round(vram_mb / 1024, 1)
                except (ValueError, IndexError):
                    pass
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    
    # Try torch CUDA detection as fallback
    try:
        import torch
        if torch.cuda.is_available():
            hardware["gpu_available"] = True
            hardware["gpu_name"] = torch.cuda.get_device_name(0)
            hardware["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
    except (ImportError, Exception):
        pass
    
    return hardware


def classify_tier(vram_gb: float, gpu_available: bool) -> str:
    """Classify hardware tier based on VRAM."""
    if gpu_available and vram_gb >= 6:
        return "tier_1_gpu"
    elif gpu_available and vram_gb >= 4:
        return "tier_2_partial_gpu"
    else:
        return "tier_3_cpu_only"


def run_calibration_inference(model_path: Path) -> Optional[Dict[str, float]]:
    """
    Run short calibration inference to measure actual latency.
    Returns measured tokens/second or None if model unavailable.
    """
    if not model_path.exists():
        return None
    
    try:
        from llama_cpp import Llama
        import time
        
        # Load model with conservative settings
        llm = Llama(
            model_path=str(model_path),
            n_ctx=512,  # Short context for calibration
            n_threads=4,
            verbose=False
        )
        
        # Warm-up
        llm.create_prompt("Hello", max_tokens=10, stop=["."])
        
        # Measure inference
        prompt = "The quick brown fox jumps over the lazy dog. " * 5
        start = time.perf_counter()
        output = llm.create_prompt(prompt, max_tokens=100, stop=["\n\n"])
        elapsed = time.perf_counter() - start
        
        # Count generated tokens (approximate)
        generated_tokens = len(output.get("choices", [{}])[0].get("text", "").split())
        
        if elapsed > 0 and generated_tokens > 0:
            tokens_per_second = generated_tokens / elapsed
            seconds_per_500_tokens = 500 / tokens_per_second
            
            return {
                "tokens_per_second": round(tokens_per_second, 2),
                "seconds_per_500_tokens": round(seconds_per_500_tokens, 1),
                "calibration_prompt_length": len(prompt),
                "generated_tokens": generated_tokens,
                "elapsed_seconds": round(elapsed, 2)
            }
        return None
        
    except (ImportError, FileNotFoundError, Exception) as e:
        print(f"Calibration skipped: {e}", file=sys.stderr)
        return None


def main():
    """Main measurement routine."""
    print("=" * 60)
    print("SWARAJ Hardware Measurement")
    print("=" * 60)
    print()
    
    # Detect hardware
    print("Detecting hardware...")
    hardware = detect_hardware()
    tier = classify_tier(hardware["vram_gb"], hardware["gpu_available"])
    
    print(f"  CPU: {hardware['cpu_name']} ({hardware['cpu_cores']} cores)")
    print(f"  GPU: {'Yes' if hardware['gpu_available'] else 'No'}", end="")
    if hardware["gpu_available"]:
        print(f" ({hardware['gpu_name']}, {hardware['vram_gb']} GB VRAM)", end="")
    print()
    print(f"  Platform: {hardware['platform']}")
    print(f"  Classified Tier: {tier}")
    print()
    
    # Find model
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent
    model_path = root_dir / "models" / "qwen3-4b-instruct-q4_k_m.gguf"
    
    # Run calibration if model exists
    measured = None
    if model_path.exists():
        print("Running calibration inference...")
        measured = run_calibration_inference(model_path)
        if measured:
            print(f"  Measured: {measured['tokens_per_second']} tokens/sec")
            print(f"  Estimated time for 500 tokens: {measured['seconds_per_500_tokens']}s")
        else:
            print("  Calibration failed (model may be incompatible)")
    else:
        print("Model artifact not found. Skipping calibration.")
        print(f"  Expected path: {model_path}")
    
    print()
    
    # Build report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hardware": hardware,
        "tier": tier,
        "target_performance": {
            "tier_1_gpu": {"seconds_per_500_tokens_target": "2-4s"},
            "tier_2_partial_gpu": {"seconds_per_500_tokens_target": "6-10s"},
            "tier_3_cpu_only": {"seconds_per_500_tokens_target": "15-25s"}
        }[tier],
        "measured_performance": measured,
        "notes": []
    }
    
    # Add honesty notes
    if not measured:
        report["notes"].append("No measured performance: model artifact missing or llama-cpp unavailable")
        report["notes"].append("Target performance is GOAL only, not actual measurement")
    
    if not hardware["gpu_available"]:
        report["notes"].append("CPU-only mode: expect higher latency than GPU targets")
    
    # Save report
    data_dir = root_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_path = data_dir / "calibration.json"
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Report saved to: {report_path}")
    print()
    
    # Print summary table
    print("Performance Summary:")
    print("-" * 60)
    print(f"  Tier:              {tier}")
    print(f"  Target (500 tok):  {report['target_performance']['seconds_per_500_tokens_target']}")
    if measured:
        print(f"  Measured (500 tok): {measured['seconds_per_500_tokens']}s")
    else:
        print(f"  Measured (500 tok): N/A (requires model artifact)")
    print("-" * 60)
    print()
    
    if not measured:
        print("WARNING: No measured performance available.")
        print("  To get accurate measurements:")
        print("  1. Place qwen3-4b-instruct-q4_k_m.gguf in models/")
        print("  2. Install llama-cpp-python")
        print("  3. Re-run this script")
        print()
    
    print("IMPORTANT: Target performance is NOT actual performance.")
    print("           Always use measured values for capacity planning.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
