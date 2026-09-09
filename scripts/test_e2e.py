import urllib.request
import json
import uuid
import time

# 1. Test Ingestion with a real sample document
boundary = f"----FormBoundary{uuid.uuid4().hex}"
lines = [
    f"--{boundary}",
    'Content-Disposition: form-data; name="user_id"',
    "",
    "admin_user",
    f"--{boundary}",
    'Content-Disposition: form-data; name="role"',
    "",
    "Admin",
    f"--{boundary}",
    'Content-Disposition: form-data; name="file"; filename="spec_notes.txt"',
    "Content-Type: text/plain",
    "",
    "Project Architecture: Clean architecture with repository pattern and secure air-gapped enclave.",
    f"--{boundary}--",
    ""
]
body_bytes = "\r\n".join(lines).encode("utf-8")

req = urllib.request.Request(
    "http://127.0.0.1:8000/ingest/document",
    data=body_bytes,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
)

with urllib.request.urlopen(req) as r:
    ingest_result = json.loads(r.read().decode())
    print("Ingest result:", ingest_result, flush=True)
    doc_id = ingest_result["document_id"]

# 2. Test Agent Run with Coding Task
run_payload = json.dumps({
    "task_description": "Write a Python module to parse and validate transaction payloads",
    "user_id": "admin_user",
    "role": "Admin",
    "source_documents": [doc_id]
}).encode("utf-8")

req_run = urllib.request.Request(
    "http://127.0.0.1:8000/agent/run",
    data=run_payload,
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req_run) as r:
    run_result = json.loads(r.read().decode())
    print("Run result:", run_result, flush=True)
    run_id = run_result["run_id"]

# Wait 3 seconds for background agent execution to finish
time.sleep(3)

# 3. Test Trace
with urllib.request.urlopen(f"http://127.0.0.1:8000/agent/trace/{run_id}") as r:
    trace_result = json.loads(r.read().decode())
    print("Trace status:", trace_result["state"]["status"], flush=True)
    print("Generated artifacts:", trace_result["state"]["generated_artifacts"], flush=True)
    print("ALL DONE!", flush=True)
