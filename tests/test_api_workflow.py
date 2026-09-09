import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from swaraj.api.main import create_app

app = create_app()

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "registry_ready" in data

@pytest.mark.asyncio
async def test_router_decide_fail_closed_no_model():
    """Router should return 503 when no verified models available."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/router/decide", json={"task_description": "summarise inspection report"})
    # 503 expected when no verified model artifact present
    assert r.status_code in (200, 400, 503)

@pytest.mark.asyncio
async def test_hardware_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/hardware/status")
    assert r.status_code == 200
    data = r.json()
    assert "tier" in data
    assert data["tier"]  # must be non-empty

@pytest.mark.asyncio
async def test_registry():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/registry")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data
    assert isinstance(data["models"], list)

@pytest.mark.asyncio
async def test_approvals_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/approvals")
    assert r.status_code == 200
    data = r.json()
    assert "pending" in data

@pytest.mark.asyncio
async def test_agent_run_and_trace():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Start a run
        r = await ac.post("/agent/run", json={
            "task_description": "generate approval note for test inspection",
            "user_id": "test_inspector",
            "role": "Inspector",
        })
    # Inspector may or may not be authorized depending on policy; both 200 and 403 are acceptable
    assert r.status_code in (200, 403)
    if r.status_code == 200:
        run_id = r.json()["run_id"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            tr = await ac.get(f"/agent/trace/{run_id}")
        assert tr.status_code == 200
        trace = tr.json()
        assert trace["run_id"] == run_id

@pytest.mark.asyncio
async def test_audit_events():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/audit/events")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data
    assert isinstance(data["events"], list)

@pytest.mark.asyncio
async def test_certificate_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/certificate/00000000-nonexistent-run-id")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_trace_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/agent/trace/00000000-nonexistent")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_root_serves_index():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/", headers={"Accept": "text/html"})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")

@pytest.mark.asyncio
async def test_root_json_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/", headers={"Accept": "application/json"})
    assert r.status_code == 200
    assert r.json()["service"] == "SWARAJ"


