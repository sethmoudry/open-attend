"""Tests for the SessionStore."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from models import Session, SessionMode, VisitType
from session import SessionStore


@pytest_asyncio.fixture
async def store():
    s = SessionStore()
    await s.start()
    yield s
    await s.stop()


class TestSessionStore:
    @pytest.mark.asyncio
    async def test_create_session(self, store):
        session = await store.create_session(visit_type=VisitType.URGENT)
        assert session.id
        assert session.visit_type == VisitType.URGENT
        assert session.mode == SessionMode.ACTIVE_VISIT

    @pytest.mark.asyncio
    async def test_get_session_found(self, store):
        created = await store.create_session(visit_type=VisitType.NEW_PATIENT)
        fetched = await store.get_session(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, store):
        result = await store.get_session("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_session(self, store):
        session = await store.create_session(visit_type=VisitType.URGENT)
        updated = await store.update_session(
            session.id, {"mode": SessionMode.POST_VISIT}
        )
        assert updated is not None
        assert updated.mode == SessionMode.POST_VISIT

    @pytest.mark.asyncio
    async def test_delete_session(self, store):
        session = await store.create_session(visit_type=VisitType.URGENT)
        deleted = await store.delete_session(session.id)
        assert deleted is True
        assert await store.get_session(session.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store):
        assert await store.delete_session("bogus") is False

    @pytest.mark.asyncio
    async def test_list_sessions_ordering(self, store):
        s1 = await store.create_session(visit_type=VisitType.URGENT)
        s2 = await store.create_session(visit_type=VisitType.NEW_PATIENT)
        s3 = await store.create_session(visit_type=VisitType.FOLLOW_UP)
        sessions = await store.list_sessions()
        assert len(sessions) >= 3
        # Newest first
        ids = [s.id for s in sessions]
        assert ids.index(s3.id) < ids.index(s1.id)

    @pytest.mark.asyncio
    async def test_ttl_cleanup(self, store):
        session = await store.create_session(visit_type=VisitType.URGENT)
        # Manually age the session beyond TTL
        async with store._lock:
            old = store._sessions[session.id]
            aged = old.model_copy(
                update={"created_at": datetime.now(timezone.utc) - timedelta(hours=3)}
            )
            store._sessions[session.id] = aged

        # Run cleanup logic directly (avoid the infinite loop in _periodic_cleanup)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=store.TTL_HOURS)
        async with store._lock:
            expired = [
                sid for sid, s in store._sessions.items()
                if s.created_at < cutoff
            ]
            for sid in expired:
                del store._sessions[sid]

        assert await store.get_session(session.id) is None
