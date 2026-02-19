"""MedASR transcription tool — audio bytes in, TranscriptChunk out."""

import logging
import os
import subprocess
import time
from uuid import uuid4

import numpy as np
import soundfile as sf

from models import Speaker, TranscriptChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "google/medasr")

# Minimum RMS amplitude to consider audio as non-silence.
SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "0.005"))

# ---------------------------------------------------------------------------
# Lazy-loaded ASR pipeline (loaded once, reused across calls)
# ---------------------------------------------------------------------------

_pipeline = None


def _load_pipeline():
    """Load the ASR pipeline once.  Tries the configured model first, then
    falls back to openai/whisper-tiny as a known-good Whisper-compatible
    checkpoint."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    from transformers import pipeline as hf_pipeline

    model_name = TRANSCRIBE_MODEL
    logger.info("Loading ASR model: %s", model_name)

    # Use GPU if available (CUDA device 0), fall back to CPU
    import torch
    device = 0 if torch.cuda.is_available() else -1
    device_label = f"cuda:{device}" if device >= 0 else "cpu"

    try:
        _pipeline = hf_pipeline(
            "automatic-speech-recognition",
            model=model_name,
            device=device,
        )
        logger.info("ASR model loaded on %s: %s", device_label, model_name)
    except Exception as exc:
        fallback = "openai/whisper-small"
        logger.warning(
            "Failed to load %s (%s). Falling back to %s.",
            model_name,
            exc,
            fallback,
        )
        _pipeline = hf_pipeline(
            "automatic-speech-recognition",
            model=fallback,
            device=device,
        )
        logger.info("Fallback ASR model loaded on %s: %s", device_label, fallback)

    return _pipeline


# ---------------------------------------------------------------------------
# Audio conversion helpers
# ---------------------------------------------------------------------------


def _is_wav(audio_bytes: bytes) -> bool:
    """Check if audio_bytes starts with a RIFF/WAVE header."""
    return len(audio_bytes) > 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"


def convert_to_wav(audio_bytes: bytes) -> bytes:
    """Convert arbitrary audio (webm/opus/ogg/mp3/…) to 16 kHz mono WAV.

    If the input is already WAV, returns it as-is (soundfile handles any
    sample-rate / channel mismatch downstream).  Otherwise shells out to
    ffmpeg.  Raises ``RuntimeError`` on failure.
    """
    if not audio_bytes:
        raise ValueError("Empty audio input")

    # Already WAV — skip ffmpeg entirely
    if _is_wav(audio_bytes):
        logger.debug("Input is already WAV (%d bytes), skipping ffmpeg", len(audio_bytes))
        return audio_bytes

    process = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", "pipe:0",
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            "-acodec", "pcm_s16le",
            "pipe:1",
        ],
        input=audio_bytes,
        capture_output=True,
        timeout=30,
    )

    if process.returncode != 0:
        stderr = process.stderr.decode(errors="replace")[:500]
        raise RuntimeError(f"ffmpeg conversion failed (rc={process.returncode}): {stderr}")

    if not process.stdout or len(process.stdout) < 44:
        raise RuntimeError("ffmpeg produced empty or invalid WAV output")

    return process.stdout


def _wav_bytes_to_numpy(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Read WAV bytes into a numpy float32 array and sample rate."""
    import io
    data, samplerate = sf.read(io.BytesIO(wav_bytes), dtype="float32")
    return data, samplerate


def _is_silence(audio_array: np.ndarray) -> bool:
    """Return True if the audio is effectively silence."""
    if audio_array.size == 0:
        return True
    rms = float(np.sqrt(np.mean(audio_array ** 2)))
    return rms < SILENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def transcribe(audio_bytes: bytes) -> TranscriptChunk:
    """Transcribe raw audio bytes and return a ``TranscriptChunk``.

    Accepts any format ffmpeg can decode (webm, opus, ogg, wav, mp3, …).
    Converts to 16 kHz mono WAV, runs ASR, and returns the result.
    """
    chunk_id = uuid4().hex[:12]
    t_start = time.monotonic()

    # -- Convert to WAV -------------------------------------------------------
    try:
        wav_bytes = convert_to_wav(audio_bytes)
    except (ValueError, RuntimeError) as exc:
        logger.error("Audio conversion failed for chunk %s: %s", chunk_id, exc)
        return TranscriptChunk(
            id=chunk_id,
            timestamp_start=0.0,
            timestamp_end=0.0,
            speaker=Speaker.OTHER,
            text="",
            processed=False,
        )

    # -- Decode to numpy ------------------------------------------------------
    try:
        audio_array, sample_rate = _wav_bytes_to_numpy(wav_bytes)
    except Exception as exc:
        logger.error("WAV decode failed for chunk %s: %s", chunk_id, exc)
        return TranscriptChunk(
            id=chunk_id,
            timestamp_start=0.0,
            timestamp_end=0.0,
            speaker=Speaker.OTHER,
            text="",
            processed=False,
        )

    duration = len(audio_array) / sample_rate if sample_rate else 0.0

    # -- Silence check --------------------------------------------------------
    if _is_silence(audio_array):
        logger.debug("Silence detected in chunk %s (%.2fs)", chunk_id, duration)
        return TranscriptChunk(
            id=chunk_id,
            timestamp_start=0.0,
            timestamp_end=duration,
            speaker=Speaker.OTHER,
            text="",
            processed=False,
        )

    # -- Run ASR --------------------------------------------------------------
    try:
        pipe = _load_pipeline()
        # HF ASR pipelines accept {"raw": ndarray, "sampling_rate": int}
        result = pipe(
            {"raw": audio_array, "sampling_rate": sample_rate},
            return_timestamps=False,
        )
        text = result.get("text", "").strip() if isinstance(result, dict) else str(result).strip()
    except Exception as exc:
        logger.error("ASR inference failed for chunk %s: %s", chunk_id, exc)
        text = ""

    elapsed = time.monotonic() - t_start
    print(f"[ASR] chunk {chunk_id}: {duration:.1f}s audio → {elapsed:.2f}s processing, {len(text)} chars")

    return TranscriptChunk(
        id=chunk_id,
        timestamp_start=0.0,
        timestamp_end=duration,
        speaker=Speaker.OTHER,  # diarization is a stretch goal
        text=text,
        processed=False,
    )
