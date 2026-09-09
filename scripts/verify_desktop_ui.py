import subprocess
import time
import urllib.request

print("Launching SwarajDesktop.exe...")
proc = subprocess.Popen(["dist/SwarajDesktop/SwarajDesktop.exe"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(4)

try:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/",
        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        headers = dict(resp.headers)
        print("HTTP Status:", resp.status)
        print("Content-Type:", headers.get("Content-Type"))
        print("\nHTML Preview (First 200 chars):")
        print(content[:200])
        if "<div id=\"root\"></div>" in content or "<html" in content.lower():
            print("\n>>> VERIFICATION PASSED: Frontend HTML is served with 200 OK! <<<")
        else:
            print("\n>>> VERIFICATION FAILED: HTML did not contain expected tags! <<<")
            print("Content:", content)
finally:
    proc.terminate()
