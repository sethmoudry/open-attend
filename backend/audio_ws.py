"""WebSocket handler for streaming audio transcription.

Buffer-and-batch approach: accumulates incoming audio in an AudioBuffer,
flushes periodically (5s first, then every 15s), diarizes + transcribes
the full buffer, and runs the orchestrator once per batch.

Audio persistence: chunks are also written to disk at
~/.openattend/audio/{session_id}.wav as proper WAV files (16-bit PCM, 16kHz
mono).  Files older than 7 days are cleaned up by a background task.
"""

import asyncio
import hashlib
import io
import logging
import re
import time
import wave
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

from audio_buffer import AudioBuffer
from diarize import SpeakerSegment, diarize
from models import Speaker, SpeakerProfile, TranscriptChunk
from session import store
from speaker_registry import SpeakerRegistry
from transcribe import transcribe, transcribe_whisper
from transcript_merge import merge_transcripts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audio directory & constants
# ---------------------------------------------------------------------------

AUDIO_DIR = Path.home() / ".openattend" / "audio"
_SAMPLE_RATE = 16000
_SAMPLE_WIDTH = 2  # 16-bit
_CHANNELS = 1
_AUDIO_TTL_DAYS = 7

# ---------------------------------------------------------------------------
# Session audio storage — keeps raw WAV chunks for post-visit playback/HeAR
# Also persists to disk for survival across restarts.
# ---------------------------------------------------------------------------

_session_audio: dict[str, list[bytes]] = {}
_session_audio_hash: dict[str, str] = {}  # session_id -> hash of last persisted audio


def _ensure_audio_dir() -> None:
    """Create the audio directory if it doesn't exist."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _audio_path(session_id: str) -> Path:
    """Return the disk path for a session's WAV file."""
    return AUDIO_DIR / f"{session_id}.wav"


def _extract_pcm(wav_bytes: bytes) -> bytes:
    """Extract raw PCM data from a WAV byte string."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        return wf.readframes(wf.getnframes())


def _write_wav_to_disk(session_id: str, chunks: list[bytes]) -> None:
    """Write all PCM chunks as a single WAV file (blocking I/O)."""
    _ensure_audio_dir()
    path = _audio_path(session_id)
    pcm_parts = [_extract_pcm(c) for c in chunks]
    all_pcm = b"".join(pcm_parts)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(all_pcm)
    logger.info("Wrote %s (%.1f KB)", path, len(all_pcm) / 1024)


def _read_wav_from_disk(session_id: str) -> bytes | None:
    """Read a session WAV file from disk (blocking I/O). Returns raw WAV bytes or None."""
    path = _audio_path(session_id)
    if not path.exists():
        return None
    data = path.read_bytes()
    logger.info("Read %s from disk (%.1f KB)", path, len(data) / 1024)
    return data


def _delete_wav_from_disk(session_id: str) -> None:
    """Remove a session's WAV file from disk (blocking I/O)."""
    path = _audio_path(session_id)
    if path.exists():
        path.unlink()
        logger.info("Deleted %s", path)


def store_audio_chunk(session_id: str, wav_bytes: bytes) -> None:
    """Append a flushed WAV chunk to the session's audio store and persist to disk."""
    _session_audio.setdefault(session_id, []).append(wav_bytes)
    # Hash-check: skip disk write if content hasn't changed
    chunks = _session_audio[session_id]
    content_hash = hashlib.sha256(b"".join(chunks)).hexdigest()
    if _session_audio_hash.get(session_id) == content_hash:
        return  # no new data
    _session_audio_hash[session_id] = content_hash
    asyncio.ensure_future(_persist_audio_to_disk(session_id, chunks))


async def _persist_audio_to_disk(session_id: str, chunks: list[bytes]) -> None:
    """Persist audio chunks to disk in a background thread."""
    try:
        await asyncio.to_thread(_write_wav_to_disk, session_id, list(chunks))
    except Exception as exc:
        logger.error("Failed to persist audio for session %s: %s", session_id, exc)


def get_session_audio(session_id: str) -> bytes | None:
    """Return the full recording for a session as a single WAV, or None.

    Falls back to reading from disk if the session's audio isn't in RAM.
    """
    chunks = _session_audio.get(session_id)
    if chunks:
        # Build WAV from in-memory chunks
        pcm_parts = [_extract_pcm(c) for c in chunks]
        all_pcm = b"".join(pcm_parts)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(_CHANNELS)
            wf.setsampwidth(_SAMPLE_WIDTH)
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(all_pcm)
        return buf.getvalue()
    # Fallback: read from disk
    return _read_wav_from_disk(session_id)


async def get_session_audio_async(session_id: str) -> bytes | None:
    """Async version of get_session_audio with non-blocking disk fallback."""
    chunks = _session_audio.get(session_id)
    if chunks:
        return get_session_audio(session_id)
    return await asyncio.to_thread(_read_wav_from_disk, session_id)


def clear_session_audio(session_id: str) -> None:
    """Free audio storage for a session (RAM + disk)."""
    _session_audio.pop(session_id, None)
    _session_audio_hash.pop(session_id, None)
    asyncio.ensure_future(asyncio.to_thread(_delete_wav_from_disk, session_id))


# ---------------------------------------------------------------------------
# Background cleanup — delete audio files older than 7 days
# ---------------------------------------------------------------------------

def _cleanup_old_audio_files() -> int:
    """Delete WAV files older than _AUDIO_TTL_DAYS. Returns count deleted."""
    if not AUDIO_DIR.exists():
        return 0
    cutoff = time.time() - (_AUDIO_TTL_DAYS * 86400)
    deleted = 0
    for f in AUDIO_DIR.glob("*.wav"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                logger.info("Cleaned up expired audio: %s", f.name)
                deleted += 1
        except Exception as exc:
            logger.warning("Failed to clean up %s: %s", f.name, exc)
    return deleted


async def start_audio_cleanup_task() -> asyncio.Task:
    """Launch a background task that periodically cleans up old audio files.

    Call this from the app lifespan startup. Returns the task so it can be
    cancelled on shutdown.
    """
    async def _loop():
        while True:
            try:
                deleted = await asyncio.to_thread(_cleanup_old_audio_files)
                if deleted:
                    logger.info("Audio cleanup: removed %d expired file(s)", deleted)
            except Exception as exc:
                logger.warning("Audio cleanup error: %s", exc)
            await asyncio.sleep(3600)  # Run every hour

    task = asyncio.create_task(_loop())
    logger.info("Audio cleanup task started (TTL=%d days)", _AUDIO_TTL_DAYS)
    return task


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
    if doc_score == 0 and pat_score == 0:
        stripped = text.strip()
        if stripped.endswith("?") and not any(
            stripped.lower().startswith(w) for w in ("is it", "and if", "anything")
        ):
            return Speaker.DOCTOR
    return Speaker.OTHER


# ---------------------------------------------------------------------------
# Segment merging helper
# ---------------------------------------------------------------------------


def _merge_adjacent_segments(
    segments: list[SpeakerSegment],
    id_map: dict[str, str],
    gap_threshold: float = 0.5,
) -> list[SpeakerSegment]:
    """Merge adjacent diarization segments from the same mapped speaker."""
    if not segments:
        return []
    merged: list[SpeakerSegment] = []
    current = SpeakerSegment(
        speaker_id=segments[0].speaker_id,
        start=segments[0].start,
        end=segments[0].end,
    )
    for seg in segments[1:]:
        same_speaker = id_map.get(seg.speaker_id) == id_map.get(current.speaker_id)
        small_gap = (seg.start - current.end) < gap_threshold
        if same_speaker and small_gap:
            current.end = seg.end  # extend
        else:
            merged.append(current)
            current = SpeakerSegment(
                speaker_id=seg.speaker_id, start=seg.start, end=seg.end
            )
    merged.append(current)
    return merged


# ---------------------------------------------------------------------------
# WebSocket handler — buffer-and-batch processing
# ---------------------------------------------------------------------------


async def _run_orchestrator(session_id: str, last_turn) -> None:
    """Run orchestrator in background — non-blocking to audio pipeline."""
    try:
        from orchestrator import process_chunk

        sess = await store.get_session(session_id)
        if sess:
            updates = await process_chunk(last_turn, sess)
            updates.pop("transcript_chunks", None)
            if updates:
                await store.update_session(session_id, updates)
    except Exception as exc:
        logger.warning("Orchestrator failed: %s", exc)


async def handle_audio_stream(websocket: WebSocket, session_id: str) -> None:
    """Receive streaming audio, buffer it, and process in batches.

    Audio is accumulated in an AudioBuffer and flushed periodically
    (first at 5s, then every 15s).  Each flush diarizes the full buffer,
    transcribes per-speaker segments, and runs the orchestrator once.
    """
    session = await store.get_session(session_id)
    if session is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    print(f"[WS] Audio stream opened for session {session_id}")

    # Speaker diarization registry
    registry = (
        SpeakerRegistry.from_dict(session.speaker_profiles)
        if session.speaker_profiles
        else SpeakerRegistry()
    )

    buffer = AudioBuffer(flush_interval_s=15.0, first_flush_s=15.0)
    cumulative_time = 0.0
    batch_count = 0

    async def _send_status(message: str):
        """Send a status control message to the frontend."""
        try:
            await websocket.send_json({"type": "status", "message": message})
        except Exception:
            pass

    async def _persist_profiles() -> None:
        """Save speaker registry to session, sanitizing NaN/Inf embeddings."""
        try:
            import math
            raw_profiles = registry.get_all_profiles()
            for p in raw_profiles:
                if p.get("mean_embedding"):
                    p["mean_embedding"] = [
                        0.0 if (math.isnan(x) or math.isinf(x)) else x
                        for x in p["mean_embedding"]
                    ]
                p["embeddings"] = [
                    [0.0 if (math.isnan(v) or math.isinf(v)) else v for v in emb]
                    for emb in p.get("embeddings", [])
                ]
            profiles = [SpeakerProfile(**p) for p in raw_profiles]
            await store.update_session(session_id, {"speaker_profiles": profiles})
        except Exception as exc:
            logger.warning("Failed to persist speaker profiles: %s", exc)

    async def _emit_and_persist(turns: list[TranscriptChunk]) -> None:
        """Send turns to frontend, persist to session, run orchestrator & role assignment."""
        # Dedup: filter out turns whose text already exists in the session
        sess = await store.get_session(session_id)
        if sess:
            existing_texts = {c.text.strip().lower() for c in sess.transcript_chunks}
            turns = [t for t in turns if t.text.strip().lower() not in existing_texts]

        if not turns:
            return

        # 1. Send turns to frontend
        for turn in turns:
            try:
                await websocket.send_json(turn.model_dump(mode="json"))
            except Exception:
                pass

        # 2. Persist all turns
        if sess:
            updated_chunks = list(sess.transcript_chunks) + turns
            await store.update_session(
                session_id, {"transcript_chunks": updated_chunks}
            )

        await _persist_profiles()

        # 3. Run orchestrator in background so it doesn't block the next audio batch
        if turns:
            asyncio.create_task(_run_orchestrator(session_id, turns[-1]))

        # 4. Role assignment — once per batch if any speaker lacks a role
        has_unassigned = (
            any(p.role is None for p in registry.profiles)
            if registry.profiles
            else False
        )
        diarized_count = sum(1 for t in turns if t.speaker_id)
        if has_unassigned and diarized_count > 0 and batch_count >= 2:
            try:
                from role_assignment import assign_roles

                sess = await store.get_session(session_id)
                if sess:
                    exchanges = [
                        {"speaker_id": c.speaker_id, "text": c.text}
                        for c in sess.transcript_chunks
                        if c.speaker_id
                    ]
                    role_map = await assign_roles(exchanges)
                    for cid, info in role_map.items():
                        try:
                            registry.set_role(cid, info["role"])
                        except (KeyError, TypeError):
                            pass

                    merge_map = registry.merge_by_role()
                    if merge_map:
                        # Relabel existing transcript chunks
                        sess = await store.get_session(session_id)
                        if sess:
                            new_chunks = []
                            updated = False
                            for c in sess.transcript_chunks:
                                if c.speaker_id and c.speaker_id in merge_map:
                                    c.speaker_id = merge_map[c.speaker_id]
                                    merged_role = registry.get_role(c.speaker_id)
                                    if merged_role == "doctor":
                                        c.speaker = Speaker.DOCTOR
                                    elif merged_role == "patient":
                                        c.speaker = Speaker.PATIENT
                                    updated = True
                                new_chunks.append(c)
                            if updated:
                                await store.update_session(
                                    session_id, {"transcript_chunks": new_chunks}
                                )
                                for c in new_chunks:
                                    try:
                                        await websocket.send_json(
                                            c.model_dump(mode="json")
                                        )
                                    except Exception:
                                        pass

                    await _persist_profiles()
            except Exception as exc:
                logger.warning("Role assignment failed: %s", exc)

    # Track previous turns for LLM merge context (cross-batch continuity)
    previous_merge_turns: list[dict] = []

    async def process_buffer(force: bool = False):
        nonlocal cumulative_time, batch_count

        buf_duration = buffer.duration()
        if buf_duration < 0.5:
            return

        # Flush at the last silence gap so we don't split mid-word.
        # On force (disconnect), flush everything.
        result = buffer.force_flush() if force else buffer.flush_at_silence()
        if not result:
            return
        wav_bytes, flushed_dur = result

        # Store raw audio for post-visit playback & HeAR analysis
        store_audio_chunk(session_id, wav_bytes)

        batch_count += 1
        await _send_status("processing")
        print(f"[WS] Batch #{batch_count}: processing {flushed_dur:.1f}s of audio")

        # --- Step 1: Run MedASR + Whisper + Pyannote in parallel ---
        medasr_task = asyncio.create_task(transcribe(wav_bytes))
        whisper_task = asyncio.create_task(transcribe_whisper(wav_bytes))

        async def _diarize_safe():
            try:
                return await diarize(wav_bytes, min_speakers=1, max_speakers=2)
            except Exception as exc:
                print(f"[WS] Batch #{batch_count}: diarization failed: {exc}")
                return [], []

        diarize_task = asyncio.create_task(_diarize_safe())

        medasr_chunk, whisper_chunk, (segments, embeddings) = await asyncio.gather(
            medasr_task, whisper_task, diarize_task
        )

        medasr_text = (medasr_chunk.text or "").strip()
        whisper_text = (whisper_chunk.text or "").strip()
        print(f"[WS] Batch #{batch_count}: MedASR  = {medasr_text[:100]!r}")
        print(f"[WS] Batch #{batch_count}: Whisper = {whisper_text[:100]!r}")
        print(f"[WS] Batch #{batch_count}: Pyannote → {len(segments)} segments")

        if not medasr_text and not whisper_text:
            cumulative_time += flushed_dur
            await _send_status("ready")
            return

        # --- Step 2: Map speaker IDs and merge adjacent segments ---
        speaker_seg_dicts: list[dict] = []
        id_map: dict[str, str] = {}

        if segments:
            raw_ids = list({s.speaker_id for s in segments})
            emb_dicts = [
                {"speaker_id": e.speaker_id, "embedding": e.embedding}
                for e in embeddings
            ]
            id_map = registry.match_speakers(raw_ids, emb_dicts)
            merged = _merge_adjacent_segments(segments, id_map, gap_threshold=1.5)

            for seg in merged:
                consistent_id = id_map.get(seg.speaker_id, seg.speaker_id)
                speaker_seg_dicts.append({
                    "speaker_id": consistent_id,
                    "start": seg.start,
                    "end": seg.end,
                })

        # --- Step 3: LLM merge — combine MedASR + Whisper + diarization ---
        try:
            merged_turns = await merge_transcripts(
                medasr_text=medasr_text,
                whisper_text=whisper_text,
                speaker_segments=speaker_seg_dicts,
                previous_turns=previous_merge_turns,
            )
            print(f"[WS] Batch #{batch_count}: LLM merge → {len(merged_turns)} turns")
        except Exception as exc:
            print(f"[WS] Batch #{batch_count}: LLM merge failed: {exc}")
            # Fallback: use whisper text as single turn
            merged_turns = [{"speaker_id": "unknown", "text": whisper_text or medasr_text, "start": 0.0, "end": flushed_dur}]

        # --- Step 4: Build TranscriptChunks from merged result ---
        turns: list[TranscriptChunk] = []
        from uuid import uuid4

        for mt in merged_turns:
            text = mt.get("text", "").strip()
            if not text:
                continue

            speaker_id = mt.get("speaker_id")
            role = registry.get_role(speaker_id) if speaker_id else None
            if role == "doctor":
                speaker = Speaker.DOCTOR
            elif role == "patient":
                speaker = Speaker.PATIENT
            else:
                speaker = _guess_speaker(text)

            turns.append(TranscriptChunk(
                id=uuid4().hex[:12],
                timestamp_start=cumulative_time + mt.get("start", 0),
                timestamp_end=cumulative_time + mt.get("end", 0),
                speaker=speaker,
                speaker_id=speaker_id,
                text=text,
                processed=False,
            ))
            print(f"[WS] Batch #{batch_count}: [{speaker.value}] {text[:80]!r}")

        # Update context for next batch
        for mt in merged_turns:
            if mt.get("text", "").strip():
                previous_merge_turns.append(mt)

        cumulative_time += flushed_dur

        await _emit_and_persist(turns)
        await _send_status("ready")

    # ------------------------------------------------------------------
    # Main loop: receive audio continuously, process in background
    # ------------------------------------------------------------------
    processing_task: asyncio.Task | None = None

    try:
        while True:
            try:
                audio_bytes = await asyncio.wait_for(
                    websocket.receive_bytes(), timeout=1.0
                )
                if audio_bytes:
                    buffer.add(audio_bytes)
            except asyncio.TimeoutError:
                pass  # No data — just check flush timer

            # Launch processing as a background task so we keep receiving audio
            if buffer.should_flush() and (processing_task is None or processing_task.done()):
                processing_task = asyncio.create_task(process_buffer())

    except WebSocketDisconnect:
        # Wait for any in-flight processing to finish
        if processing_task and not processing_task.done():
            await processing_task
        # Flush remaining audio
        if buffer.duration() > 0:
            await process_buffer(force=True)
        print(f"[WS] Audio stream closed for session {session_id}")
    except Exception as exc:
        print(f"[WS] Error on session {session_id}: {exc}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
