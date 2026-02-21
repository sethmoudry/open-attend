"""Tests for the FastAPI REST endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from models import SessionMode, VisitType


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app():
    """Create the FastAPI app with demo seeding disabled."""
    with patch("main._seed_demo_data", new_callable=AsyncMock):
        from main import app
        yield app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_session(self, client):
        resp = await client.post(
            "/session", json={"visit_type": "urgent"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["visit_type"] == "urgent"

    @pytest.mark.asyncio
    async def test_get_session(self, client):
        create_resp = await client.post(
            "/session", json={"visit_type": "new_patient"}
        )
        session_id = create_resp.json()["id"]

        get_resp = await client.get(f"/session/{session_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == session_id

    @pytest.mark.asyncio
    async def test_get_session_404(self, client):
        resp = await client.get("/session/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        await client.post("/session", json={"visit_type": "urgent"})
        await client.post("/session", json={"visit_type": "follow_up"})

        resp = await client.get("/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        create_resp = await client.post(
            "/session", json={"visit_type": "urgent"}
        )
        session_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/session/{session_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/session/{session_id}")
        assert get_resp.status_code == 404


class TestSOAPEndpoints:
    @pytest.mark.asyncio
    async def test_update_soap(self, client):
        create_resp = await client.post(
            "/session", json={"visit_type": "urgent"}
        )
        session_id = create_resp.json()["id"]

        patch_resp = await client.patch(
            f"/session/{session_id}/soap",
            json={"subjective": "Patient has headache"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["soap_note"]["subjective"] == "Patient has headache"

    @pytest.mark.asyncio
    async def test_end_visit(self, client):
        create_resp = await client.post(
            "/session", json={"visit_type": "urgent"}
        )
        session_id = create_resp.json()["id"]

        end_resp = await client.post(f"/session/{session_id}/end-visit")
        assert end_resp.status_code == 200
        data = end_resp.json()
        assert data["session"]["mode"] == "post_visit"
        assert "llm_usage" in data

    @pytest.mark.asyncio
    async def test_end_visit_already_ended(self, client):
        create_resp = await client.post(
            "/session", json={"visit_type": "urgent"}
        )
        session_id = create_resp.json()["id"]

        await client.post(f"/session/{session_id}/end-visit")
        resp = await client.post(f"/session/{session_id}/end-visit")
        assert resp.status_code == 400
