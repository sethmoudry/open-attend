#!/usr/bin/env python3
"""Generate a test WAV file with speech-like characteristics.

Produces a 5-second 16kHz mono WAV with mixed tones and amplitude
modulation to approximate speech energy patterns. Not real speech,
but enough to exercise the ASR pipeline without triggering silence
detection.

Output: benchmarks/test_audio.wav
"""

import argparse
import struct
import sys
from pathlib import Path

SAMPLE_RATE = 16000
DURATION_S = 5
NUM_SAMPLES = SAMPLE_RATE * DURATION_S


def generate_speech_like_samples(num_samples: int, sample_rate: int) -> list[int]:
    """Generate PCM16 samples that mimic speech energy patterns.

    Uses a mix of fundamental (150 Hz) + harmonics modulated by a
    low-frequency envelope (~3 Hz) to simulate syllable-rate amplitude
    variation. Adds a second formant-like tone at 800 Hz.
    """
    import math

    samples: list[int] = []
    for i in range(num_samples):
        t = i / sample_rate

        # Low-freq envelope simulating syllable rhythm (~3 Hz)
        envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 3.0 * t)

        # Fundamental + harmonics (rough vocal quality)
        fundamental = math.sin(2 * math.pi * 150 * t)
        harmonic2 = 0.5 * math.sin(2 * math.pi * 300 * t)
        harmonic3 = 0.3 * math.sin(2 * math.pi * 450 * t)

        # Second formant region
        formant = 0.4 * math.sin(2 * math.pi * 800 * t)

        raw = envelope * (fundamental + harmonic2 + harmonic3 + formant)

        # Scale to 16-bit range (use ~60% to avoid clipping)
        sample = int(raw * 0.6 * 32767)
        sample = max(-32768, min(32767, sample))
        samples.append(sample)

    return samples


def write_wav(path: Path, samples: list[int], sample_rate: int) -> None:
    """Write PCM16 mono WAV file from scratch (no external deps)."""
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(samples) * block_align

    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")

        # fmt sub-chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # sub-chunk size
        f.write(struct.pack("<H", 1))   # PCM format
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))

        # data sub-chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        for s in samples:
            f.write(struct.pack("<h", s))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test audio WAV file")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path (default: benchmarks/test_audio.wav)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DURATION_S,
        help="Duration in seconds (default: 5)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    output_path = Path(args.output) if args.output else repo_root / "benchmarks" / "test_audio.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    num_samples = int(SAMPLE_RATE * args.duration)
    print(f"Generating {args.duration}s test audio at {SAMPLE_RATE} Hz mono...")
    samples = generate_speech_like_samples(num_samples, SAMPLE_RATE)
    write_wav(output_path, samples, SAMPLE_RATE)

    file_size = output_path.stat().st_size
    print(f"Written: {output_path} ({file_size:,} bytes)")


if __name__ == "__main__":
    main()
