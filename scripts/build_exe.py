"""
Automated Build Pipeline for SWARAJ Desktop Native Executable.

Steps:
  1. Build the React/Vite frontend (npm run build)
  2. Compile Python backend into a one-dir bundle via PyInstaller
  3. Create models/ placeholder folder beside the exe with setup README
  4. Verify the executable boots cleanly in --test-headless mode

Usage:
  python scripts/build_exe.py

After building, copy your GGUF model:
  dist/SwarajDesktop/models/<model-name>.gguf
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "dist" / "SwarajDesktop"


def run_cmd(cmd, cwd=BASE_DIR):
    print(f"\n[*] Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(cwd), shell=True)
    if res.returncode != 0:
        print(f"[!] Command failed with return code {res.returncode}")
        sys.exit(res.returncode)


def create_models_placeholder():
    """Create models/ directory beside exe with a human-readable setup guide."""
    models_dir = DIST_DIR / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    readme = models_dir / "README.txt"
    readme.write_text(
        "SWARAJ — Model Setup\n"
        "====================\n\n"
        "Place your GGUF model file here so SWARAJ can run AI inference.\n\n"
        "Recommended models:\n"
        "  • Qwen3-4B-Instruct-Q4_K_M.gguf  (~2.4 GB, GPU or CPU)\n"
        "  • Qwen3-4B-Instruct-Q8_0.gguf    (~4.7 GB, best quality)\n"
        "  • Any other GGUF-format model      (>10 MB)\n\n"
        "How to download:\n"
        "  1. Visit https://huggingface.co/Qwen/Qwen3-4B-GGUF\n"
        "  2. Download a .gguf file\n"
        "  3. Move it into THIS folder (models/)\n\n"
        "SWARAJ will auto-detect and load the largest .gguf file on startup.\n",
        encoding="utf-8",
    )
    print(f"[*] Created models/ placeholder at: {models_dir}")
    print(f"[*] Setup guide written to: {readme}")


def main():
    print("=" * 60)
    print(" SWARAJ Desktop — Production Build Pipeline")
    print("=" * 60)

    # Step 1 — Build frontend
    print("\n[Step 1/4] Building UI Web Distribution...")
    run_cmd("npm run build", cwd=BASE_DIR / "ui-web")

    # Step 2 — Run PyInstaller
    print("\n[Step 2/4] Compiling Native Windows Executable...")
    pyinstaller_bin = BASE_DIR / ".venv" / "Scripts" / "pyinstaller.exe"
    if not pyinstaller_bin.exists():
        pyinstaller_bin = "pyinstaller"
    run_cmd(f'"{pyinstaller_bin}" -y --clean swaraj_desktop.spec', cwd=BASE_DIR)

    # Step 3 — Create models/ placeholder
    print("\n[Step 3/4] Setting up models/ directory...")
    create_models_placeholder()

    # Step 4 — Verify executable boots
    exe_path = DIST_DIR / "SwarajDesktop.exe"
    if not exe_path.exists():
        print(f"[!] Error: {exe_path} not found!")
        sys.exit(1)

    print(f"\n[Step 4/4] Verifying SwarajDesktop.exe ({exe_path.stat().st_size / (1024*1024):.0f} MB)...")
    run_cmd(f'"{exe_path}" --test-headless', cwd=DIST_DIR)

    print("\n" + "=" * 60)
    print(" ✓ BUILD COMPLETE")
    print(f"   Executable : {exe_path}")
    print(f"   Models dir : {DIST_DIR / 'models'}")
    print()
    print(" NEXT STEP: Copy your .gguf model into:")
    print(f"   {DIST_DIR / 'models'}")
    print()
    print(" Then double-click SwarajDesktop.exe to launch.")
    print("=" * 60)


if __name__ == "__main__":
    main()

