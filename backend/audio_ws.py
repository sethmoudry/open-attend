"""WebSocket handler for streaming audio transcription.

Buffer-and-batch approach: accumulates incoming audio in an AudioBuffer,
flushes periodically (5s first, then every 15s), diarizes + transcribes
the full buffer, and runs the orchestrator once per batch.
"""

import asyncio
import logging
import re

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

    buffer = AudioBuffer(flush_interval_s=15.0, first_flush_s=5.0)
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
        # 1. Send turns to frontend
        for turn in turns:
            try:
                await websocket.send_json(turn.model_dump(mode="json"))
            except Exception:
                pass

        # 2. Persist all turns
        if turns:
            sess = await store.get_session(session_id)
            if sess:
                updated_chunks = list(sess.transcript_chunks) + turns
                await store.update_session(
                    session_id, {"transcript_chunks": updated_chunks}
                )

        await _persist_profiles()

        # 3. Run orchestrator once for the batch (use last turn)
        if turns:
            try:
                from orchestrator import process_chunk

                sess = await store.get_session(session_id)
                if sess:
                    updates = await process_chunk(turns[-1], sess)
                    updates.pop("transcript_chunks", None)
                    if updates:
                        await store.update_session(session_id, updates)
            except Exception as exc:
                logger.warning("Orchestrator failed: %s", exc)

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
