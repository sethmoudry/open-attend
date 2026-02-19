"""Thread-safe in-memory session store with SQLite write-through cache."""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from models import Session, VisitType, PatientContext
from speaker_registry import SpeakerRegistry

logger = logging.getLogger(__name__)

# Try encrypted SQLite; fall back to plain sqlite3
_use_sqlcipher = False
try:
    from pysqlcipher3 import dbapi2 as sqlcipher  # type: ignore[import-untyped]
    _use_sqlcipher = True
    logger.info("pysqlcipher3 available — encrypted SQLite enabled")
except ImportError:
    logger.warning(
        "pysqlcipher3 not installed — falling back to plain sqlite3. "
        "Sessions will NOT be encrypted at rest."
    )


def _default_db_path() -> str:
    return str(Path.home() / ".openattend" / "sessions.db")


def _get_connection() -> sqlite3.Connection:
    """Open a SQLite connection, optionally with encryption."""
    db_path = os.environ.get("OPENATTEND_DB_PATH", _default_db_path())
    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    if _use_sqlcipher:
        conn = sqlcipher.connect(db_path)  # type: ignore[possibly-undefined]
        db_key = os.environ.get("OPENATTEND_DB_KEY")
        if db_key:
            conn.execute(f"PRAGMA key = '{db_key}'")
            logger.debug("SQLCipher encryption key applied")
    else:
        conn = sqlite3.connect(db_path)

    return conn


class SessionStore:
    TTL_HOURS = 0  # No auto-expiry — sessions persist until manual delete

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._db_ready = False

    # ---- lifecycle -------------------------------------------------------

    async def start(self) -> None:
        await self._init_db()
        await self.load_from_db()
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    # ---- SQLite helpers (all run via to_thread) --------------------------

    async def _init_db(self) -> None:
        def _create_tables() -> None:
            conn = _get_connection()
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS sessions ("
                    "  id TEXT PRIMARY KEY,"
                    "  created_at TEXT NOT NULL,"
                    "  data TEXT NOT NULL"
                    ")"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS properties ("
                    "  key TEXT PRIMARY KEY,"
                    "  value TEXT NOT NULL"
                    ")"
                )
                # Seed defaults if properties table is empty
                row = conn.execute(
                    "SELECT COUNT(*) FROM properties"
                ).fetchone()
                if row and row[0] == 0:
                    conn.execute(
                        "INSERT INTO properties (key, value) VALUES (?, ?)",
                        ("fhir_base_url", "https://r4.smarthealthit.org"),
                    )
                conn.commit()
                logger.info("SQLite session store connected: %s",
                            os.environ.get("OPENATTEND_DB_PATH", _default_db_path()))
            finally:
                conn.close()

        await asyncio.to_thread(_create_tables)
        self._db_ready = True

    async def load_from_db(self) -> None:
        """Hydrate in-memory dict from SQLite on startup."""
        def _load_all() -> list[tuple[str, str]]:
            conn = _get_connection()
            try:
                rows = conn.execute("SELECT id, data FROM sessions").fetchall()
                return rows
            finally:
                conn.close()

        rows = await asyncio.to_thread(_load_all)
        loaded = 0
        for session_id, data_json in rows:
            try:
                session = Session.model_validate_json(data_json)
                self._sessions[session_id] = session
                loaded += 1
            except Exception:
                logger.exception("Failed to deserialize session %s — skipping", session_id)
        logger.info("Loaded %d sessions from SQLite", loaded)

    async def _db_write(self, session: Session) -> None:
        if not self._db_ready:
            return

        def _write() -> None:
            conn = _get_connection()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO sessions (id, created_at, data) "
                    "VALUES (?, ?, ?)",
                    (
                        session.id,
                        session.created_at.isoformat(),
                        session.model_dump_json(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        try:
            await asyncio.to_thread(_write)
        except Exception:
            logger.exception("SQLite write failed for session %s", session.id)

    async def _db_delete(self, session_id: str) -> None:
        if not self._db_ready:
            return

        def _delete() -> None:
            conn = _get_connection()
            try:
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                conn.commit()
            finally:
                conn.close()

        try:
            await asyncio.to_thread(_delete)
        except Exception:
            logger.exception("SQLite delete failed for session %s", session_id)

    # ---- public API (unchanged signatures) --------------------------------

    async def create_session(
        self, visit_type: VisitType, patient_context: Optional[PatientContext] = None
    ) -> Session:
        session = Session(visit_type=visit_type, patient_context=patient_context)
        async with self._lock:
            self._sessions[session.id] = session
        await self._db_write(session)
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def list_sessions(self) -> list[Session]:
        async with self._lock:
            return sorted(
                self._sessions.values(),
                key=lambda s: s.created_at,
                reverse=True,
            )

    async def update_session(
        self, session_id: str, updates: dict[str, Any]
    ) -> Optional[Session]:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            updated = session.model_copy(update=updates)
            self._sessions[session_id] = updated
        await self._db_write(updated)
        return updated

    async def delete_session(self, session_id: str) -> bool:
        async with self._lock:
            removed = self._sessions.pop(session_id, None) is not None
        if removed:
            await self._db_delete(session_id)
        return removed

    def get_speaker_registry(self, session: Session) -> SpeakerRegistry:
        """Reconstruct a SpeakerRegistry from a session's stored profiles."""
        return SpeakerRegistry.from_dict(session.speaker_profiles)

    async def save_speaker_registry(
        self, session_id: str, registry: SpeakerRegistry
    ) -> Optional[Session]:
        """Persist a SpeakerRegistry back into the session's speaker_profiles."""
        from models import SpeakerProfile as ModelSpeakerProfile

        profiles = [
            ModelSpeakerProfile(
                consistent_id=d["consistent_id"],
                role=d.get("role", "unknown"),
                confidence=d.get("confidence", 0.0),
                reasoning=d.get("reasoning", ""),
            )
            for d in registry.to_dict()
        ]
        return await self.update_session(
            session_id, {"speaker_profiles": profiles}
        )

    # ---- properties table ---------------------------------------------------

    async def get_property(self, key: str) -> Optional[str]:
        def _get() -> Optional[str]:
            conn = _get_connection()
            try:
                row = conn.execute(
                    "SELECT value FROM properties WHERE key = ?", (key,)
                ).fetchone()
                return row[0] if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_get)

    async def set_property(self, key: str, value: str) -> None:
        def _set() -> None:
            conn = _get_connection()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO properties (key, value) VALUES (?, ?)",
                    (key, value),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_set)

    async def get_all_properties(self) -> dict[str, str]:
        def _get_all() -> dict[str, str]:
            conn = _get_connection()
            try:
                rows = conn.execute("SELECT key, value FROM properties").fetchall()
                return {k: v for k, v in rows}
            finally:
                conn.close()

        return await asyncio.to_thread(_get_all)

    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup — only runs if TTL_HOURS > 0."""
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            if self.TTL_HOURS <= 0:
                continue  # no auto-expiry
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.TTL_HOURS)
            expired: list[str] = []
            async with self._lock:
                expired = [
                    sid
                    for sid, s in self._sessions.items()
                    if s.created_at < cutoff
                ]
                for sid in expired:
                    del self._sessions[sid]
            # Also remove expired sessions from SQLite
            for sid in expired:
                await self._db_delete(sid)


store = SessionStore()
session_store = store  # convenience alias
