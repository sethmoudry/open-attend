"""Thread-safe in-memory session store with TTL eviction."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from models import Session, VisitType, PatientContext
from speaker_registry import SpeakerRegistry


class SessionStore:
    TTL_HOURS = 2

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def create_session(
        self, visit_type: VisitType, patient_context: Optional[PatientContext] = None
    ) -> Session:
        session = Session(visit_type=visit_type, patient_context=patient_context)
        async with self._lock:
            self._sessions[session.id] = session
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
            return updated

    async def delete_session(self, session_id: str) -> bool:
        async with self._lock:
            return self._sessions.pop(session_id, None) is not None

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

    async def _periodic_cleanup(self) -> None:
        while True:
            await asyncio.sleep(300)  # every 5 minutes
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.TTL_HOURS)
            async with self._lock:
                expired = [
                    sid
                    for sid, s in self._sessions.items()
                    if s.created_at < cutoff
                ]
                for sid in expired:
                    del self._sessions[sid]


store = SessionStore()
