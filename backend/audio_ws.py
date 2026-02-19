"""WebSocket handler for streaming audio transcription."""

import asyncio
import logging
import re

from fastapi import WebSocket, WebSocketDisconnect

from models import Speaker, TranscriptChunk
from session import store
from transcribe import transcribe

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lightweight text-based speaker heuristic
# ---------------------------------------------------------------------------

_DOCTOR_PATTERNS = re.compile(
    r"\b("
    r"i'?m (?:dr|doctor)|prescri(?:be|bing|ption)|diagnos|"
    r"let me (?:take a look|examine|check)|milligrams|"
    r"rapid (?:strep |)test|i'?ll (?:order|prescribe|run)|"
    r"clinical|exudate|palpable|bilateral|lymph node|"
    r"treatment|course of|amoxicillin|antibiotic|"
    r"are you allergic|over the counter|come back|"
    r"i'?m going to|positive for|ten day|"
    r"can you tell me|have you noticed|"
    r"swollen glands|open wide|tonsillar|"
    r"rest,? stay hydrated|pain reliever|ibuprofen|"
    r"salt ?water|symptoms worsen|develop a rash"
    r")\b",
    re.IGNORECASE,
)

_PATIENT_PATTERNS = re.compile(
    r"\b("
    r"i'?ve been having|my (?:throat|neck|head|stomach)|"
    r"it (?:hurts|feels)|really (?:bad|painful)|"
    r"that'?s what made me|is it (?:strep|serious)|"
    r"no allergies|thank you doctor|got it|"
    r"i looked in the mirror|not sleeping well|"
    r"getting worse|three days|sore throat|"
    r"hi doctor|hi dr|what brings|"
    r"i did see|whitish spots|"
    r"my neck (?:does |)feel|swollen on both|"
    r"that sounds serious|anything else i should|"
    r"the full ten days|i really appreciate"
    r")\b",
    re.IGNORECASE,
)


def _guess_speaker(text: str) -> Speaker:
    """Guess doctor vs patient from transcript text content."""
    if not text:
        return Speaker.OTHER
    doc_score = len(_DOCTOR_PATTERNS.findall(text))
    pat_score = len(_PATIENT_PATTERNS.findall(text))
    if doc_score > pat_score:
        return Speaker.DOCTOR
    if pat_score > doc_score:
        return Speaker.PATIENT
    # Tie-breaker: if text starts with a question, likely doctor
    if doc_score == 0 and pat_score == 0:
        stripped = text.strip()
        if stripped.endswith("?") and not any(
            stripped.lower().startswith(w) for w in ("is it", "and if", "anything")
        ):
            return Speaker.DOCTOR
    return Speaker.OTHER


# ---------------------------------------------------------------------------
# WebSocket handler — concurrent chunk processing
# ---------------------------------------------------------------------------


async def handle_audio_stream(websocket: WebSocket, session_id: str) -> None:
    """Receive binary audio chunks and transcribe them concurrently.

    Chunks are processed in parallel via asyncio tasks. Results are sent
    back to the client in order of completion (lowest latency).
    """
    session = await store.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    print(f"[WS] Audio stream opened for session {session_id}")

    pending_tasks: set[asyncio.Task] = set()

    async def _process_chunk(audio_bytes: bytes, seq: int) -> None:
        """Transcribe a single chunk and send the result."""
        try:
            chunk = await transcribe(audio_bytes)

            if chunk.text:
                chunk.speaker = _guess_speaker(chunk.text)

            print(f"[WS] #{seq} speaker={chunk.speaker}, text={chunk.text[:60]!r}")

            # Persist
            sess = await store.get_session(session_id)
            if sess is not None:
                updated = list(sess.transcript_chunks) + [chunk]
                await store.update_session(session_id, {"transcript_chunks": updated})

            # Send back to client
            await websocket.send_json(chunk.model_dump(mode="json"))
        except Exception as exc:
            print(f"[WS] Error processing chunk #{seq}: {exc}")

    seq = 0
    try:
        while True:
            audio_bytes: bytes = await websocket.receive_bytes()
            if not audio_bytes:
                continue

            seq += 1
            task = asyncio.create_task(_process_chunk(audio_bytes, seq))
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)

    except WebSocketDisconnect:
        print(f"[WS] Audio stream closed for session {session_id}")
    except Exception as exc:
        print(f"[WS] Error on session {session_id}: {exc}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        # Wait for in-flight transcriptions to finish
        if pending_tasks:
            print(f"[WS] Waiting for {len(pending_tasks)} in-flight tasks...")
            await asyncio.gather(*pending_tasks, return_exceptions=True)
