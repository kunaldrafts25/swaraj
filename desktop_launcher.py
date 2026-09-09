"""
SWARAJ Desktop Launcher
Launches the SWARAJ Sovereign Core API server and opens the modern UI in a browser window.
"""
import sys
import os
import time
import socket
import webbrowser
import threading
import uvicorn
from pathlib import Path

# When packaged with PyInstaller, sys._MEIPASS holds the bundled resources path
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    BASE_DIR = BUNDLE_DIR

# Ensure bundle and base directories are on sys.path
sys.path.insert(0, str(BUNDLE_DIR / "src"))
sys.path.insert(0, str(BUNDLE_DIR))

def find_free_port(preferred_port=8000):
    """Check if preferred port is available, otherwise find a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", preferred_port)) != 0:
            return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def open_ui(url, delay=1.5):
    """Open the local web UI in user's default browser after server boot."""
    time.sleep(delay)
    print(f"[*] Opening SWARAJ Desktop UI: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[!] Could not open browser automatically: {e}")

def check_model(models_dir: Path) -> bool:
    """Return True if at least one valid GGUF model is present."""
    if not models_dir.exists():
        return False
    return any(
        p.suffix == ".gguf" and p.stat().st_size > 10 * 1024 * 1024
        for p in models_dir.iterdir()
        if p.is_file()
    )

def main():
    port = find_free_port(8000)
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    print("=" * 60)
    print(" [SWARAJ] Sovereign Desktop Engine v2.0")
    print(" 100% Air-Gapped | Local LLM Inference | Fail-Closed RBAC")
    print("=" * 60)
    print(f"[*] Initializing Sovereign Runtime on {url} ...")

    # Set environment variables so settings know the directories
    os.environ["SWARAJ_API_PORT"] = str(port)
    os.environ["SWARAJ_API_HOST"] = host
    
    if getattr(sys, "frozen", False):
        os.environ["SWARAJ_PROJECT_ROOT"] = str(BUNDLE_DIR)
        os.environ["SWARAJ_REGISTRY_DIR"] = str(BUNDLE_DIR / "src" / "swaraj" / "registry" / "manifests")
        os.environ["SWARAJ_POLICY_DIR"] = str(BUNDLE_DIR / "policies")
        os.environ["SWARAJ_USERS_FILE"] = str(BUNDLE_DIR / "users.json")
        os.environ["SWARAJ_DATA_DIR"] = str(BASE_DIR / "data")
        os.environ["SWARAJ_LOGS_DIR"] = str(BASE_DIR / "logs")
        os.environ["SWARAJ_SIGNING_KEY_DIR"] = str(BASE_DIR / "keys")
        os.environ["SWARAJ_KEYS_DIR"] = str(BASE_DIR / "keys")

    # In frozen mode, set data and model directories relative to executable or app data
    models_dir = BASE_DIR / "models"
    if not models_dir.exists():
        models_dir.mkdir(parents=True, exist_ok=True)
    os.environ["SWARAJ_MODELS_DIR"] = str(models_dir)

    # ── Model presence check ──────────────────────────────────────────────────
    if not check_model(models_dir):
        print()
        print("  ⚠  WARNING: No GGUF model found in:", models_dir)
        print("  ─────────────────────────────────────────────────────")
        print("  SWARAJ will start but AI inference will be disabled.")
        print()
        print("  To enable AI responses, download a GGUF model and place it in:")
        print(f"    {models_dir}")
        print()
        print("  Recommended:  Qwen3-4B-Instruct-Q4_K_M.gguf  (~2.4 GB)")
        print("  Download from: https://huggingface.co/Qwen/Qwen3-4B-GGUF")
        print()

    # Check for headless / test mode
    headless = "--headless" in sys.argv or "--test-headless" in sys.argv

    if not headless:
        # Start browser in separate background thread
        browser_thread = threading.Thread(target=open_ui, args=(url,), daemon=True)
        browser_thread.start()

    from swaraj.api.main import create_app
    app = create_app()

    if "--test-headless" in sys.argv:
        print("[*] Running in test mode - initialization successful!")
        sys.exit(0)

    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()

