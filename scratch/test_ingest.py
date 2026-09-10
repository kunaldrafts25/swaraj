import urllib.request
import uuid
import json

boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
file_path = r"e:\swaraj\data\workspace\uploads\8c44d13a-ae30-4aed-9936-d0e5bbd78b3f.pdf"
with open(file_path, "rb") as f:
    file_bytes = f.read()

body = bytearray()
def add_field(name, val):
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode("utf-8"))

add_field("user_id", "inspector_user")
add_field("role", "Inspector")

body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"AdmitCard.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode("utf-8"))
body.extend(file_bytes)
body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

req = urllib.request.Request(
    "http://127.0.0.1:8000/ingest/document",
    data=bytes(body),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST"
)

try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("Ingest Success!")
        print("Doc ID:", res.get("document_id"))
        print("Pages:", res.get("pages_processed"))
        prev = res.get("extracted_preview", "")
        print("Extracted preview length:", len(prev))
        print("Preview snippet:")
        print(prev[:300])
except Exception as e:
    print("Error:", e)
