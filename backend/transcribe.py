"""MedASR transcription tool — audio bytes in, TranscriptChunk out."""

import asyncio
import logging
import os
import platform
import subprocess
import time
from uuid import uuid4

import numpy as np
import soundfile as sf

from models import Speaker, TranscriptChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform detection — pick MLX on Apple Silicon, HF pipeline on CUDA/CPU
# ---------------------------------------------------------------------------

def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


_USE_MLX = _is_apple_silicon() and not _has_cuda()

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
        fallback = "openai/whisper-tiny"
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
# Lazy-loaded MLX ASR model (Apple Silicon path)
# ---------------------------------------------------------------------------

_mlx_model = None
_mlx_decoder = None
_mlx_processor = None


def _load_mlx_model():
    """Load the MLX ASR model and decoder once."""
    global _mlx_model, _mlx_decoder, _mlx_processor
    if _mlx_model is not None:
        return _mlx_model, _mlx_decoder

    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "medasr_mlx"))
    from model import load_mlx_model as _load_mlx
    from decode import CTCTextDecoder, DecoderConfig
    from huggingface_hub import snapshot_download

    model_id = os.getenv("MLX_ASR_MODEL", "ainergiz/medasr-mlx-fp16")
    logger.info("Loading MLX ASR model: %s", model_id)

    local_dir = snapshot_download(model_id)
    _mlx_model = _load_mlx(local_dir)

    # Load tokenizer for CTC decoding (processor/ dir has tokenizer.json)
    from pathlib import Path
    from transformers import PreTrainedTokenizerFast
    processor_path = Path(local_dir) / "processor"
    tokenizer_file = processor_path / "tokenizer.json"
    if tokenizer_file.exists():
        tokenizer = PreTrainedTokenizerFast(tokenizer_file=str(tokenizer_file))
    else:
        tokenizer = PreTrainedTokenizerFast.from_pretrained("google/medasr")
    _mlx_decoder = CTCTextDecoder(
        processor=tokenizer,
        config=DecoderConfig(mode="greedy"),
    )
    logger.info("MLX ASR model loaded: %s", model_id)
    return _mlx_model, _mlx_decoder


def _compute_mel_features(audio_array: np.ndarray, sample_rate: int) -> np.ndarray:
    """Compute 128-bin log-mel spectrogram matching LasrFeatureExtractor config.

    Config: n_fft=512, hop_length=160, win_length=400, n_mels=128, sr=16000.
    """
    import librosa
    mel = librosa.feature.melspectrogram(
        y=audio_array.astype(np.float32),
        sr=sample_rate,
        n_fft=512,
        hop_length=160,
        win_length=400,
        n_mels=128,
        fmax=sample_rate / 2,
    )
    log_mel = np.log(mel + 1e-6)
    # Shape: (1, n_mels, time) → model expects (batch, time, n_mels)
    return log_mel.T[np.newaxis, :]  # (1, time, 128)


def _ctc_collapse(ids: list[int], blank_id: int = 0) -> list[int]:
    """Remove consecutive duplicates and blank tokens (standard CTC decode)."""
    result = []
    prev = -1
    for i in ids:
        if i != prev and i != blank_id:
            result.append(i)
        prev = i
    return result


def _run_mlx_asr(audio_array: np.ndarray, sample_rate: int) -> str:
    """Run ASR inference using the MLX backend."""
    import mlx.core as mx

    model, decoder = _load_mlx_model()

    # Compute mel features
    features = _compute_mel_features(audio_array, sample_rate)
    input_features = mx.array(features)
    attention_mask = mx.ones(features.shape[:2], dtype=mx.bool_)

    logits = model(input_features=input_features, attention_mask=attention_mask)

    # CTC greedy decode: argmax → collapse repeats/blanks → tokenizer decode
    raw_ids = np.asarray(mx.argmax(logits, axis=-1))[0].tolist()
    collapsed = _ctc_collapse(raw_ids)
    text = decoder.processor.decode(collapsed, skip_special_tokens=True)
    return text


# ---------------------------------------------------------------------------
# Audio conversion helpers
# ---------------------------------------------------------------------------


def slice_wav_bytes(wav_bytes: bytes, start_s: float, end_s: float) -> bytes:
    """Extract a time range from WAV bytes, return new WAV bytes."""
    import io as _io
    audio_array, sr = _wav_bytes_to_numpy(wav_bytes)
    s_idx = max(0, int(start_s * sr))
    e_idx = min(len(audio_array), int(end_s * sr))
    segment = audio_array[s_idx:e_idx]
    buf = _io.BytesIO()
    sf.write(buf, segment, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


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


def _trim_silence(audio_array: np.ndarray, sr: int, threshold: float = 0.008, frame_ms: int = 10) -> np.ndarray:
    """Trim leading and trailing silence from audio to give the ASR model clean input."""
    frame_len = int(sr * frame_ms / 1000)
    if len(audio_array) < frame_len:
        return audio_array

    # Find first frame above threshold
    start = 0
    for i in range(0, len(audio_array), frame_len):
        frame = audio_array[i : i + frame_len]
        if float(np.sqrt(np.mean(frame ** 2))) > threshold:
            start = max(0, i - frame_len)  # keep one frame of lead-in
            break

    # Find last frame above threshold
    end = len(audio_array)
    for i in range(len(audio_array) - frame_len, -1, -frame_len):
        frame = audio_array[i : i + frame_len]
        if float(np.sqrt(np.mean(frame ** 2))) > threshold:
            end = min(len(audio_array), i + 2 * frame_len)  # keep one frame of tail
            break

    trimmed = audio_array[start:end]
    return trimmed if len(trimmed) > frame_len else audio_array


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

    # -- Convert to WAV (in thread to avoid blocking on ffmpeg) ---------------
    try:
        wav_bytes = await asyncio.to_thread(convert_to_wav, audio_bytes)
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

    # -- Trim leading/trailing silence before ASR ----------------------------
    audio_array = _trim_silence(audio_array, sample_rate)
    duration = len(audio_array) / sample_rate if sample_rate else 0.0

    # -- Run ASR (in thread pool to avoid blocking the event loop) -----------
    def _run_asr() -> str:
        if _USE_MLX:
            return _run_mlx_asr(audio_array, sample_rate)

        # HF pipeline path (CUDA / CPU)
        pipe = _load_pipeline()
        is_ctc = hasattr(pipe.model, "ctc_head") or "ctc" in type(pipe.model).__name__.lower()
        if is_ctc:
            result = pipe(
                {"raw": audio_array, "sampling_rate": sample_rate},
                chunk_length_s=20,
                stride_length_s=2,
            )
        else:
            result = pipe(
                {"raw": audio_array, "sampling_rate": sample_rate},
                return_timestamps=False,
            )
        return result.get("text", "").strip() if isinstance(result, dict) else str(result).strip()

    try:
        text = await asyncio.to_thread(_run_asr)
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


# ---------------------------------------------------------------------------
# Whisper-based ASR (separate, parallel path)
# ---------------------------------------------------------------------------

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "openai/whisper-base")

_whisper_pipeline = None


def _load_whisper_pipeline():
    """Load the Whisper ASR pipeline once on first call (CPU only)."""
    global _whisper_pipeline
    if _whisper_pipeline is not None:
        return _whisper_pipeline

    from transformers import pipeline as hf_pipeline

    logger.info("Loading Whisper model: %s (CPU)", WHISPER_MODEL)
    _whisper_pipeline = hf_pipeline(
        "automatic-speech-recognition",
        model=WHISPER_MODEL,
        device=-1,
    )
    logger.info("Whisper model loaded: %s", WHISPER_MODEL)
    return _whisper_pipeline


async def transcribe_whisper(audio_bytes: bytes) -> TranscriptChunk:
    """Transcribe audio using Whisper and return a ``TranscriptChunk``.

    Accepts any format ffmpeg can decode. Converts to 16 kHz mono WAV,
    runs Whisper inference on CPU, and returns the result.
    """
    chunk_id = uuid4().hex[:12]
    t_start = time.monotonic()

    # -- Convert to WAV -------------------------------------------------------
    try:
        wav_bytes = await asyncio.to_thread(convert_to_wav, audio_bytes)
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

    # -- Trim leading/trailing silence ----------------------------------------
    audio_array = _trim_silence(audio_array, sample_rate)
    duration = len(audio_array) / sample_rate if sample_rate else 0.0

    # -- Run Whisper inference (in thread to avoid blocking event loop) -------
    def _run_whisper() -> str:
        pipe = _load_whisper_pipeline()
        # Use return_timestamps=True for long audio (>30s) to avoid mel feature limit
        use_timestamps = duration > 28.0
        result = pipe(
            {"raw": audio_array, "sampling_rate": sample_rate},
            return_timestamps=use_timestamps,
        )
        if isinstance(result, dict):
            if use_timestamps and "chunks" in result:
                return " ".join(c["text"].strip() for c in result["chunks"] if c.get("text", "").strip())
            return result.get("text", "").strip()
        return str(result).strip()

    try:
        text = await asyncio.to_thread(_run_whisper)
    except Exception as exc:
        logger.error("Whisper inference failed for chunk %s: %s", chunk_id, exc)
        text = ""

    elapsed = time.monotonic() - t_start
    print(f"[Whisper] chunk {chunk_id}: {duration:.1f}s audio → {elapsed:.2f}s processing, {len(text)} chars")

    return TranscriptChunk(
        id=chunk_id,
        timestamp_start=0.0,
        timestamp_end=duration,
        speaker=Speaker.OTHER,
        text=text,
        processed=False,
    )
