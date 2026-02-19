#!/usr/bin/env python3
"""Generate sample clinical conversation audio using ElevenLabs TTS.

Uses ElevenLabs neural voices for doctor (female) and patient (male),
with an embedded royalty-free cough sound for HeAR analysis demo.

Dependencies: elevenlabs, pydub, ffmpeg (system)
Output: backend/static/sample_conversation.wav (16kHz mono 16-bit PCM)

Usage:
    ELEVENLABS_API_KEY=sk_... python scripts/generate_sample_audio.py
"""

import os
import tempfile
from pathlib import Path

from elevenlabs import ElevenLabs
from pydub import AudioSegment

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "backend" / "static" / "sample_conversation.wav"
COUGH_PATH = REPO_ROOT / "scripts" / "assets" / "cough_2219.wav"

# ElevenLabs voice IDs
DOCTOR_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel — female, calm, professional
PATIENT_VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam — male, deep, conversational

# Silence durations (ms)
BETWEEN_SPEAKERS_MS = 1500  # 1.5s — exceeds VAD's 1.0s split threshold
WITHIN_SPEAKER_MS = 600     # 0.6s — stays under VAD split threshold
BEFORE_COUGH_MS = 300
AFTER_COUGH_MS = 1500

# Dialogue script: (speaker, text) where speaker is "doctor", "patient", or "cough"
DIALOGUE = [
    ("doctor", "Good morning! What brings you in today?"),
    ("patient", "I've had this cough that won't go away for about three weeks now."),
    ("cough", None),  # embedded cough sound
    ("patient", "It's worse at night, sometimes I cough up yellowish mucus."),
    ("doctor", "Any shortness of breath? Chest pain? Fever?"),
    ("patient",
     "Yeah, I get short of breath going up stairs, "
     "and I've had some chest tightness."),
    ("doctor", "What medications are you currently taking?"),
    ("patient",
     "Lisinopril twenty milligrams for blood pressure, "
     "and warfarin because I had a DVT last year."),
    ("patient",
     "Oh, and my doctor just started me on ibuprofen for my knee."),
    ("doctor", "Any allergies?"),
    ("patient", "I'm allergic to penicillin. I get hives."),
    ("doctor",
     "I'm hearing some wheezing bilaterally, "
     "decreased breath sounds at the right base."),
    ("doctor",
     "Let's get a chest X-ray and a CBC today, "
     "and I want to check your INR given the ibuprofen."),
    ("doctor", "I'm also going to refer you to pulmonology."),
    ("patient",
     "I've been really anxious about this. "
     "Haven't been sleeping well, lost my appetite."),
    ("doctor",
     "Based on what I'm seeing, I'm concerned about a possible lower "
     "respiratory infection, though given your smoking history we need "
     "to rule out something more serious. I'm going to start you on "
     "azithromycin, we'll get those imaging and labs done today, and I "
     "want you to follow up in one week. Also, I'd recommend stopping "
     "the ibuprofen given you're on warfarin. We'll find a safer "
     "alternative for your knee pain."),
]


def generate_line(client: ElevenLabs, text: str, voice_id: str, output_path: Path) -> None:
    """Generate a single TTS line via ElevenLabs."""
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
    )
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)


def main() -> None:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise SystemExit("Set ELEVENLABS_API_KEY env var")

    client = ElevenLabs(api_key=api_key)

    voices = {
        "doctor": DOCTOR_VOICE,
        "patient": PATIENT_VOICE,
    }

    # Load cough sound
    if not COUGH_PATH.exists():
        print(f"WARNING: Cough sound not found at {COUGH_PATH}")
        cough_segment = AudioSegment.silent(duration=100)
    else:
        cough_segment = AudioSegment.from_file(str(COUGH_PATH))
        print(f"Loaded cough: {COUGH_PATH.name} ({len(cough_segment)}ms)")

    combined = AudioSegment.empty()
    prev_speaker = None

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, (speaker, text) in enumerate(DIALOGUE):
            if speaker == "cough":
                combined += AudioSegment.silent(duration=BEFORE_COUGH_MS)
                combined += cough_segment
                combined += AudioSegment.silent(duration=AFTER_COUGH_MS)
                prev_speaker = "patient"
                print(f"  Beat {i+1}: [cough] {len(cough_segment)}ms")
                continue

            mp3_path = Path(tmpdir) / f"line_{i:02d}.mp3"
            voice_id = voices[speaker]
            print(f"  Beat {i+1}: {speaker} — {text[:50]}...")
            generate_line(client, text, voice_id, mp3_path)

            segment = AudioSegment.from_mp3(str(mp3_path))

            if prev_speaker is not None:
                if speaker != prev_speaker:
                    combined += AudioSegment.silent(duration=BETWEEN_SPEAKERS_MS)
                else:
                    combined += AudioSegment.silent(duration=WITHIN_SPEAKER_MS)

            combined += segment
            prev_speaker = speaker

    # Convert to 16kHz mono 16-bit PCM
    combined = combined.set_channels(1).set_frame_rate(16000).set_sample_width(2)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(OUTPUT_PATH), format="wav")

    duration_s = len(combined) / 1000
    file_size = OUTPUT_PATH.stat().st_size
    print(f"\nOutput: {OUTPUT_PATH}")
    print(f"Duration: {duration_s:.1f}s ({duration_s/60:.1f} min)")
    print(f"Size: {file_size:,} bytes")
    print(f"Format: 16kHz mono 16-bit PCM WAV")


if __name__ == "__main__":
    print("Generating sample conversation (ElevenLabs)...")
    print(f"  Doctor: Rachel ({DOCTOR_VOICE[:8]}...)")
    print(f"  Patient: Adam ({PATIENT_VOICE[:8]}...)")
    print()
    main()
