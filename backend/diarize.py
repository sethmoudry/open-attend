"""Speaker diarization using pyannote/speaker-diarization-3.1.

Gracefully degrades: if pyannote.audio is not installed or HF_TOKEN is
missing, diarize() returns empty segments and logs a warning.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SpeakerSegment:
    speaker_id: str   # e.g. "SPEAKER_00"
    start: float      # seconds
    end: float        # seconds


@dataclass
class SpeakerEmbedding:
    speaker_id: str
    embedding: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Lazy-loaded singleton (same pattern as transcribe.py)
# ---------------------------------------------------------------------------

_pipeline = None
_available: bool | None = None  # None = not yet checked


def _check_available() -> bool:
    """Return True if pyannote.audio is importable."""
    global _available
    if _available is not None:
        return _available
    try:
        import pyannote.audio  # noqa: F401
        _available = True
    except ImportError:
        _available = False
        logger.warning(
            "pyannote.audio is not installed — speaker diarization disabled. "
            "Install with: pip install 'pyannote.audio>=3.1.0'"
        )
    return _available


def _load_pipeline():
    """Load pyannote speaker-diarization-3.1 pipeline (CPU)."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    if not _check_available():
        return None

    hf_token = os.getenv("HF_TOKEN", "")
    if not hf_token:
        logger.warning(
            "HF_TOKEN not set — pyannote models require a Hugging Face token. "
            "Speaker diarization disabled."
        )
        return None

    from pyannote.audio import Pipeline
    import torch

    model_name = os.getenv(
        "DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1"
    )
    logger.info("Loading diarization model: %s", model_name)

    try:
        _pipeline = Pipeline.from_pretrained(
            model_name, use_auth_token=hf_token
        )
        _pipeline.to(torch.device("cpu"))
        logger.info("Diarization model loaded successfully: %s", model_name)
    except Exception as exc:
        logger.error("Failed to load diarization model %s: %s", model_name, exc)
        _pipeline = None

    return _pipeline


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def diarize(
    audio_bytes: bytes,
    min_speakers: int = 1,
    max_speakers: int = 8,
) -> tuple[list[SpeakerSegment], list[SpeakerEmbedding]]:
    """Run speaker diarization on audio bytes.

    Returns:
        segments: list of SpeakerSegment(speaker_id, start, end)
        embeddings: speaker voice embeddings for cross-chunk consistency
    """
    if not _check_available():
        return [], []

    pipe = _load_pipeline()
    if pipe is None:
        return [], []

    # Reuse audio helpers from transcribe module
    from transcribe import convert_to_wav, _wav_bytes_to_numpy

    try:
        wav_bytes = convert_to_wav(audio_bytes)
        audio_array, sample_rate = _wav_bytes_to_numpy(wav_bytes)
    except Exception as exc:
        logger.error("Audio conversion failed for diarization: %s", exc)
        return [], []

    import torch

    # pyannote expects {"waveform": Tensor[1, samples], "sample_rate": int}
    waveform = torch.tensor(audio_array, dtype=torch.float32).unsqueeze(0)
    audio_input = {"waveform": waveform, "sample_rate": sample_rate}

    # Run in executor so we don't block the event loop
    loop = asyncio.get_event_loop()
    try:
        diarization = await loop.run_in_executor(
            None,
            lambda: pipe(
                audio_input,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
            ),
        )
    except Exception as exc:
        logger.error("Diarization inference failed: %s", exc)
        return [], []

    # Extract segments
    segments: list[SpeakerSegment] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append(
            SpeakerSegment(
                speaker_id=speaker, start=turn.start, end=turn.end
            )
        )

    # Extract speaker embeddings (best-effort)
    embeddings = _extract_embeddings(segments, audio_array, sample_rate)

    return segments, embeddings


def _extract_embeddings(
    segments: list[SpeakerSegment],
    audio_array,
    sample_rate: int,
) -> list[SpeakerEmbedding]:
    """Extract one embedding per unique speaker. Best-effort — returns empty
    list on any failure."""
    embeddings: list[SpeakerEmbedding] = []
    try:
        import torch
        from pyannote.audio import Inference

        hf_token = os.getenv("HF_TOKEN", "")
        embedding_model = Inference(
            os.getenv("SPEAKER_EMBEDDING_MODEL", "pyannote/embedding"),
            use_auth_token=hf_token or None,
        )
        embedding_model.to(torch.device("cpu"))

        seen_speakers: set[str] = set()
        for seg in segments:
            if seg.speaker_id in seen_speakers:
                continue
            seen_speakers.add(seg.speaker_id)

            start_sample = int(seg.start * sample_rate)
            end_sample = int(seg.end * sample_rate)
            speaker_audio = audio_array[start_sample:end_sample]

            # Need at least 0.5 s of audio for a meaningful embedding
            if len(speaker_audio) < int(sample_rate * 0.5):
                continue

            speaker_waveform = (
                torch.tensor(speaker_audio, dtype=torch.float32).unsqueeze(0)
            )
            emb = embedding_model(
                {"waveform": speaker_waveform, "sample_rate": sample_rate}
            )
            embeddings.append(
                SpeakerEmbedding(
                    speaker_id=seg.speaker_id,
                    embedding=emb.flatten().tolist(),
                )
            )
    except Exception as exc:
        logger.warning("Speaker embedding extraction failed: %s", exc)

    return embeddings
