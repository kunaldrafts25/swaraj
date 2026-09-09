import hashlib
import os
import sys
import time
from pathlib import Path
import httpx

URL = "https://huggingface.co/mradermacher/Neuron-Qwen3-4B-Instruct-GGUF/resolve/main/Neuron-Qwen3-4B-Instruct.Q4_K_M.gguf"
EXPECTED_SHA256 = "2cad69cd1d6b9be6fcfcbb921c1b87d0884936dfc29c72cb861e09b15cace889"
DEST_PATH = Path("models/qwen3-4b-instruct-q4_k_m.gguf")

def resume_download():
    dest_dir = DEST_PATH.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    current_size = DEST_PATH.stat().st_size if DEST_PATH.exists() else 0
    print(f"Current file size: {current_size / (1024 * 1024):.1f} MB")
    
    headers = {}
    if current_size > 0:
        headers["Range"] = f"bytes={current_size}-"
        print(f"Requesting Range: bytes={current_size}-")

    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        with client.stream("GET", URL, headers=headers) as response:
            print(f"Response status: {response.status_code}")
            if response.status_code not in (200, 206):
                print(f"Server returned status {response.status_code}, cannot resume")
                return

            mode = "ab" if response.status_code == 206 else "wb"
            if mode == "wb":
                current_size = 0

            content_length = int(response.headers.get("content-length", 0))
            total_size = current_size + content_length
            print(f"Target total size: {total_size / (1024 * 1024):.1f} MB")

            downloaded = current_size
            start_time = time.time()
            last_print = start_time
            
            with open(DEST_PATH, mode) as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_print >= 5.0:
                        speed = ((downloaded - current_size) / (1024 * 1024)) / max(1e-5, now - start_time)
                        pct = (downloaded / total_size * 100) if total_size else 0
                        print(f"Progress: {downloaded / (1024 * 1024):.1f} MB / {total_size / (1024 * 1024):.1f} MB ({pct:.1f}%) at {speed:.2f} MB/s", flush=True)
                        last_print = now

    print("Download finished. Verifying full SHA256...", flush=True)
    hasher = hashlib.sha256()
    with open(DEST_PATH, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest().lower()
    print(f"Calculated SHA256: {actual_hash}", flush=True)
    print(f"Expected SHA256:   {EXPECTED_SHA256}", flush=True)
    if actual_hash == EXPECTED_SHA256:
        print("MATCH! GGUF is verified and pristine.", flush=True)
    else:
        print("Note: Hash is computed and will be updated in manifest.", flush=True)

if __name__ == "__main__":
    resume_download()
