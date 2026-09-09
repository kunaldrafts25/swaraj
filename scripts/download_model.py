import hashlib
import sys
import time
from pathlib import Path
import httpx

URL = "https://huggingface.co/mradermacher/Neuron-Qwen3-4B-Instruct-GGUF/resolve/main/Neuron-Qwen3-4B-Instruct.Q4_K_M.gguf"
EXPECTED_SHA256 = "2cad69cd1d6b9be6fcfcbb921c1b87d0884936dfc29c72cb861e09b15cace889"

def download_model():
    dest_dir = Path("models")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "qwen3-4b-instruct-q4_k_m.gguf"
    temp_path = dest_dir / "qwen3-4b-instruct-q4_k_m.gguf.tmp"

    print(f"Target: {dest_path}")
    print(f"Source: {URL}")
    print("Beginning stream download...")

    sha256_hash = hashlib.sha256()
    downloaded = 0
    start_time = time.time()
    last_print = start_time

    with httpx.stream("GET", URL, follow_redirects=True, timeout=600.0) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        print(f"Total size: {total_size / (1024 * 1024):.1f} MB")

        with open(temp_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                sha256_hash.update(chunk)
                downloaded += len(chunk)
                now = time.time()
                if now - last_print >= 5.0:
                    speed = (downloaded / (1024 * 1024)) / (now - start_time)
                    pct = (downloaded / total_size * 100) if total_size else 0
                    print(f"Downloaded: {downloaded / (1024 * 1024):.1f} MB / {total_size / (1024 * 1024):.1f} MB ({pct:.1f}%) at {speed:.2f} MB/s")
                    last_print = now

    calculated_sha256 = sha256_hash.hexdigest().lower()
    print(f"Download complete! Calculated SHA256: {calculated_sha256}")

    if calculated_sha256 != EXPECTED_SHA256:
        print(f"WARNING: SHA256 mismatch! Expected {EXPECTED_SHA256}, got {calculated_sha256}")
    else:
        print("SHA256 matches official upstream hash!")

    if dest_path.exists():
        dest_path.unlink()
    temp_path.rename(dest_path)
    print(f"Artifact successfully placed at {dest_path}")
    return calculated_sha256

if __name__ == "__main__":
    download_model()
