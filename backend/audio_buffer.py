"""Server-side audio buffer that accumulates incoming chunks and flushes periodically.

Converts each incoming audio blob to 16 kHz mono PCM on arrival, then concatenates
and wraps in a WAV header on flush.  This gives downstream ASR and diarization
models longer audio context for better accuracy.
"""

import io
import time

import numpy as np
import soundfile as sf

from transcribe import convert_to_wav, _wav_bytes_to_numpy


class AudioBuffer:
    """Accumulates WAV PCM data, flushes on a configurable interval."""

    def __init__(
        self,
        flush_interval_s: float = 15.0,
        first_flush_s: float = 5.0,
    ):
        self._pcm_chunks: list[np.ndarray] = []
        self._sample_rate: int = 16000
        self._flush_interval = flush_interval_s
        self._first_flush = first_flush_s
        self._last_flush = time.monotonic()
        self._flush_count = 0

    # ------------------------------------------------------------------

    def add(self, audio_bytes: bytes) -> None:
        """Convert incoming audio to PCM and append to buffer."""
        wav = convert_to_wav(audio_bytes)
        arr, sr = _wav_bytes_to_numpy(wav)
        self._pcm_chunks.append(arr)
        self._sample_rate = sr

    def duration(self) -> float:
        """Total buffered audio duration in seconds."""
        if not self._pcm_chunks:
            return 0.0
        total_samples = sum(len(c) for c in self._pcm_chunks)
        return total_samples / self._sample_rate

    def should_flush(self) -> bool:
        """True if enough time has elapsed since the last flush."""
        if not self._pcm_chunks:
            return False
        elapsed = time.monotonic() - self._last_flush
        threshold = self._first_flush if self._flush_count == 0 else self._flush_interval
        return elapsed >= threshold

    def flush(self) -> tuple[bytes, float] | None:
        """Concatenate buffered PCM into WAV bytes.

        Returns ``(wav_bytes, duration_s)`` or ``None`` if buffer is empty.
        """
        if not self._pcm_chunks:
            return None
        return self._do_flush()

    def force_flush(self) -> tuple[bytes, float] | None:
        """Flush whatever is in the buffer, regardless of duration."""
        if not self._pcm_chunks:
            return None
        return self._do_flush()

    def partial_flush(self, cut_at_s: float) -> tuple[bytes, float] | None:
        """Flush audio up to cut_at_s seconds, keep the remainder in the buffer.

        Returns (wav_bytes, duration) for the flushed portion, or None if empty.
        The audio after cut_at_s stays in self._pcm_chunks for the next batch.
        """
        if not self._pcm_chunks:
            return None

        combined = np.concatenate(self._pcm_chunks)
        cut_sample = int(cut_at_s * self._sample_rate)
        cut_sample = min(cut_sample, len(combined))

        flushed_pcm = combined[:cut_sample]
        remainder_pcm = combined[cut_sample:]

        # Reset buffer with remainder
        self._pcm_chunks = [remainder_pcm] if len(remainder_pcm) > 0 else []
        self._last_flush = time.monotonic()
        self._flush_count += 1

        dur = len(flushed_pcm) / self._sample_rate
        buf = io.BytesIO()
        sf.write(buf, flushed_pcm, self._sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), dur

    def flush_at_silence(
        self,
        silence_threshold: float = 0.01,
        min_silence_ms: int = 300,
        search_window_s: float = 5.0,
    ) -> tuple[bytes, float] | None:
        """Flush up to the last silence gap, keeping the remainder.

        Scans backward from the end of the buffer looking for a silence gap
        of at least ``min_silence_ms`` ms.  Cuts at the *start* of that gap
        so no speech is split.  Falls back to full flush if no gap is found
        within ``search_window_s`` of the end.
        """
        if not self._pcm_chunks:
            return None

        combined = np.concatenate(self._pcm_chunks)
        sr = self._sample_rate
        frame_len = int(sr * min_silence_ms / 1000)

        # Search backward from end, within the search window
        search_start = max(0, len(combined) - int(search_window_s * sr))
        best_cut = len(combined)  # default: flush everything

        # Walk backward in frame_len steps looking for silence
        for i in range(len(combined) - frame_len, search_start, -frame_len):
            frame = combined[i : i + frame_len]
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if rms < silence_threshold:
                best_cut = i
                break

        if best_cut == len(combined) or best_cut < len(combined) // 2:
            # No good silence found or would discard too much — flush all
            return self._do_flush()

        flushed_pcm = combined[:best_cut]
        remainder_pcm = combined[best_cut:]

        self._pcm_chunks = [remainder_pcm] if len(remainder_pcm) > 0 else []
        self._last_flush = time.monotonic()
        self._flush_count += 1

        dur = len(flushed_pcm) / sr
        buf = io.BytesIO()
        sf.write(buf, flushed_pcm, sr, format="WAV", subtype="PCM_16")
        return buf.getvalue(), dur

    def get_wav(self) -> bytes | None:
        """Get the full buffer as WAV bytes without flushing. Used for diarization."""
        if not self._pcm_chunks:
            return None
        combined = np.concatenate(self._pcm_chunks)
        buf = io.BytesIO()
        sf.write(buf, combined, self._sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    # ------------------------------------------------------------------

    def _do_flush(self) -> tuple[bytes, float]:
        combined = np.concatenate(self._pcm_chunks)
        self._pcm_chunks.clear()
        self._last_flush = time.monotonic()
        self._flush_count += 1

        dur = len(combined) / self._sample_rate

        buf = io.BytesIO()
        sf.write(buf, combined, self._sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue(), dur
