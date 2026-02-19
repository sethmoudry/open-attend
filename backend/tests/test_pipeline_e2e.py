"""End-to-end pipeline test: dual-ASR (MedASR + Whisper) + Pyannote + LLM merge.

Simulates the buffer-and-batch flow: accumulate audio in 15s batches,
run MedASR + Whisper + Pyannote in parallel, LLM-merge into clean
speaker-labeled transcript.

Run with: python -m pytest tests/test_pipeline_e2e.py -v -s

Requires: pytest-asyncio, LLM_BASE_URL env var pointing to vLLM (for LLM merge)
"""
import pytest
import asyncio
import time
import soundfile as sf
import io
import numpy as np
from pathlib import Path

# Skip entire module if sample WAV doesn't exist
SAMPLE_WAV = Path(__file__).parent.parent / "static" / "sample_conversation.wav"
pytestmark = pytest.mark.skipif(not SAMPLE_WAV.exists(), reason="Sample WAV not found")


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_full_pipeline():
    """Run the full dual-ASR + LLM merge pipeline on sample audio."""
    from audio_buffer import AudioBuffer
    from transcribe import transcribe, transcribe_whisper
    from diarize import diarize
    from audio_ws import _merge_adjacent_segments
    from speaker_registry import SpeakerRegistry
    from transcript_merge import merge_transcripts

    # Read full audio
    audio, sr = sf.read(str(SAMPLE_WAV), dtype="float32")
    total_dur = len(audio) / sr
    print(f"\nSample audio: {total_dur:.1f}s @ {sr}Hz")

    # Split into ~5s frontend-style chunks (simulate VAD)
    CHUNK_S = 5.0
    chunk_boundaries = []
    pos = 0.0
    while pos < total_dur:
        end = min(pos + CHUNK_S, total_dur)
        chunk_boundaries.append((pos, end))
        pos = end

    # Feed chunks into buffer, process every 15s
    buffer = AudioBuffer(flush_interval_s=15.0, first_flush_s=15.0)
    registry = SpeakerRegistry()
    all_turns = []
    previous_merge_turns = []
    cumulative_time = 0.0
    batch_count = 0

    async def process_batch(flushed_wav, flushed_dur, is_final=False):
        nonlocal cumulative_time, batch_count
        batch_count += 1
        label = f"Batch #{batch_count}" + (" (final)" if is_final else "")
        print(f"\n--- {label}: {flushed_dur:.1f}s ---")

        # Step 1: Run MedASR + Whisper + Pyannote in parallel
        medasr_task = asyncio.create_task(transcribe(flushed_wav))
        whisper_task = asyncio.create_task(transcribe_whisper(flushed_wav))

        async def _diarize_safe():
            try:
                return await diarize(flushed_wav, min_speakers=1, max_speakers=2)
            except Exception as exc:
                print(f"  Diarization failed: {exc}")
                return [], []

        diarize_task = asyncio.create_task(_diarize_safe())

        medasr_chunk, whisper_chunk, (segments, embeddings) = await asyncio.gather(
            medasr_task, whisper_task, diarize_task
        )

        medasr_text = (medasr_chunk.text or "").strip()
        whisper_text = (whisper_chunk.text or "").strip()
        print(f"  MedASR:  {medasr_text[:120]!r}")
        print(f"  Whisper: {whisper_text[:120]!r}")
        print(f"  Pyannote: {len(segments)} segments")

        if not medasr_text and not whisper_text:
            cumulative_time += flushed_dur
            return

        # Step 2: Map speaker IDs and merge adjacent segments
        speaker_seg_dicts = []
        if segments:
            raw_ids = list({s.speaker_id for s in segments})
            emb_dicts = [{"speaker_id": e.speaker_id, "embedding": e.embedding} for e in embeddings]
            id_map = registry.match_speakers(raw_ids, emb_dicts)
            merged = _merge_adjacent_segments(segments, id_map, gap_threshold=1.5)
            print(f"  Segments: {len(segments)} raw -> {len(merged)} merged")

            for seg in merged:
                consistent_id = id_map.get(seg.speaker_id, seg.speaker_id)
                speaker_seg_dicts.append({
                    "speaker_id": consistent_id,
                    "start": seg.start,
                    "end": seg.end,
                })

        # Step 3: LLM merge
        try:
            merged_turns = await merge_transcripts(
                medasr_text=medasr_text,
                whisper_text=whisper_text,
                speaker_segments=speaker_seg_dicts,
                previous_turns=previous_merge_turns,
            )
            print(f"  LLM merge → {len(merged_turns)} turns")
        except Exception as exc:
            print(f"  LLM merge failed: {exc}")
            merged_turns = [{"speaker_id": "unknown", "text": whisper_text or medasr_text, "start": 0.0, "end": flushed_dur}]

        for mt in merged_turns:
            text = mt.get("text", "").strip()
            if not text:
                continue
            sid = mt.get("speaker_id", "unknown")
            ts = cumulative_time + mt.get("start", 0)
            print(f"  [{sid}] {ts:.1f}s: {text}")
            all_turns.append({
                "speaker_id": sid,
                "timestamp": ts,
                "text": text,
            })
            previous_merge_turns.append(mt)

        cumulative_time += flushed_dur

    # Main loop: feed chunks and process batches
    for start_s, end_s in chunk_boundaries:
        chunk_audio = audio[int(start_s * sr):int(end_s * sr)]
        buf = io.BytesIO()
        sf.write(buf, chunk_audio, sr, format="WAV", subtype="PCM_16")
        wav_bytes = buf.getvalue()

        buffer.add(wav_bytes)

        if buffer.duration() >= 15.0:
            buffer._last_flush = time.monotonic() - buffer._flush_interval - 1

        if buffer.should_flush():
            result = buffer.flush_at_silence()
            assert result is not None
            await process_batch(*result)

    # Force flush remaining audio
    if buffer.duration() > 0:
        result = buffer.force_flush()
        if result:
            await process_batch(*result, is_final=True)

    # --- Assertions ---
    print(f"\n=== RESULTS: {len(all_turns)} turns across {batch_count} batches ===\n")
    full_transcript = " ".join(t["text"] for t in all_turns)
    print(f"Full transcript ({len(full_transcript)} chars):\n{full_transcript}\n")

    # 1. We got some turns
    assert len(all_turns) >= 4, f"Expected at least 4 turns, got {len(all_turns)}"

    # 2. Transcript is non-trivial
    assert len(full_transcript) > 200, f"Transcript too short: {len(full_transcript)} chars"

    # 3. Key phrases (medical + conversational) — LLM merge should capture both
    key_phrases = [
        "sore throat",
        "three days",
        "fever",
        "swallowing",
        "amoxicillin",
    ]
    transcript_lower = full_transcript.lower()
    found = {p: p in transcript_lower for p in key_phrases}
    print(f"Key phrases: {found}")
    missing = [p for p, ok in found.items() if not ok]
    assert len(missing) <= 1, f"Too many missing key phrases: {missing}"

    # 4. Conversational accuracy — LLM merge should fix MedASR garbling
    #    These should now be present thanks to Whisper + LLM merge
    conversational = ["doctor", "morning"]
    conv_found = {p: p in transcript_lower for p in conversational}
    print(f"Conversational phrases: {conv_found}")

    # 5. No garbled artifacts — LLM merge should eliminate these
    garbled = ["doctorch", "highDctorchin", "morningm"]
    for g in garbled:
        assert g.lower() not in transcript_lower, f"Found garbled text: {g!r}"

    # 6. Speaker IDs detected
    speaker_ids = {t["speaker_id"] for t in all_turns if t["speaker_id"] and t["speaker_id"] != "unknown"}
    print(f"Speaker IDs: {speaker_ids}")
    assert len(speaker_ids) >= 1, "No speaker IDs detected"

    # 7. Medical content quality
    medical_terms = [
        "tonsil", "lymph", "pharyn", "exudate", "palpable",
        "bilateral", "allergic", "ibuprofen", "prescrib",
    ]
    medical_hits = sum(1 for t in medical_terms if t in transcript_lower)
    print(f"Medical terms found: {medical_hits}/{len(medical_terms)}")
    assert medical_hits >= 3, f"Only {medical_hits} medical terms found"

    print("\nAll assertions passed!")
