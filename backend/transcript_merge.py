"""LLM-based transcript merger — combines MedASR + Whisper + pyannote diarization."""

import json
import logging
from typing import Optional
from llm import call_medgemma_json

logger = logging.getLogger(__name__)

# The system prompt for the merge LLM
_MERGE_SYSTEM_PROMPT = """You are a medical transcript merger. You receive two ASR transcriptions of the same audio and speaker diarization timestamps.

Your job: produce ONE accurate, speaker-labeled transcript by combining:
- MedASR output: trust this for medical terminology (drug names, diagnoses, procedures, anatomy)
- Whisper output: trust this for conversational speech (greetings, small talk, filler words, names)
- Speaker segments: use these timestamps to assign speaker labels

Rules:
1. Prefer MedASR spelling for medical terms (e.g., "amoxicillin" not "amoxicilin")
2. Prefer Whisper for conversational phrases (e.g., "Good morning, I'm Doctor Chen" not "doctorch")
3. Assign each portion of text to the speaker active at that time based on diarization
4. If previous conversation context is provided, ensure continuity — don't repeat text already transcribed
5. Output valid JSON only — no markdown, no explanation"""


async def merge_transcripts(
    medasr_text: str,
    whisper_text: str,
    speaker_segments: list[dict],
    previous_turns: list[dict] | None = None,
) -> list[dict]:
    """Merge MedASR + Whisper transcriptions using speaker diarization.
    
    Args:
        medasr_text: Full transcription from MedASR
        whisper_text: Full transcription from Whisper
        speaker_segments: List of {"speaker_id": str, "start": float, "end": float}
        previous_turns: Previous conversation turns for context/continuity
        
    Returns:
        List of {"speaker_id": str, "text": str, "start": float, "end": float}
    """
    if not medasr_text and not whisper_text:
        return []
    
    # Build the prompt
    prompt_parts = []
    
    if previous_turns:
        # Include last few turns for context
        recent = previous_turns[-6:]  # last 6 turns max
        context_lines = []
        for t in recent:
            sid = t.get("speaker_id", "unknown")
            text = t.get("text", "")
            context_lines.append(f"[{sid}]: {text}")
        prompt_parts.append(f"PREVIOUS CONTEXT (already transcribed, do NOT repeat):\n" + "\n".join(context_lines))
    
    prompt_parts.append(f"MEDASR TRANSCRIPTION:\n{medasr_text}")
    prompt_parts.append(f"WHISPER TRANSCRIPTION:\n{whisper_text}")
    
    # Format speaker segments
    seg_lines = []
    for s in speaker_segments:
        seg_lines.append(f"  {s['speaker_id']}: {s['start']:.1f}s - {s['end']:.1f}s")
    prompt_parts.append(f"SPEAKER DIARIZATION:\n" + "\n".join(seg_lines))
    
    prompt_parts.append(
        'Produce a JSON array of speaker turns:\n'
        '[{"speaker_id": "spk_0", "text": "...", "start": 0.0, "end": 3.5}, ...]\n'
        'Merge the two transcriptions for accuracy. Assign text to speakers based on diarization timestamps.'
    )
    
    prompt = "\n\n".join(prompt_parts)
    
    try:
        result = await call_medgemma_json(
            prompt,
            system_prompt=_MERGE_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=2048,
        )
        
        # Handle both list and dict responses
        if isinstance(result, list):
            turns = result
        elif isinstance(result, dict):
            # Try common keys
            turns = result.get("turns") or result.get("transcript") or result.get("_raw", [])
            if isinstance(turns, str):
                logger.warning("LLM returned string instead of list, falling back")
                return _fallback_merge(medasr_text, whisper_text, speaker_segments)
        else:
            turns = []
        
        # Validate structure
        validated = []
        for t in turns:
            if isinstance(t, dict) and "text" in t:
                validated.append({
                    "speaker_id": t.get("speaker_id", "unknown"),
                    "text": t["text"],
                    "start": float(t.get("start", 0)),
                    "end": float(t.get("end", 0)),
                })
        
        if validated:
            return validated
        
        logger.warning("LLM merge returned no valid turns, using fallback")
        return _fallback_merge(medasr_text, whisper_text, speaker_segments)
        
    except Exception as exc:
        logger.warning("LLM merge failed (%s), using fallback", exc)
        return _fallback_merge(medasr_text, whisper_text, speaker_segments)


def _fallback_merge(
    medasr_text: str,
    whisper_text: str,
    speaker_segments: list[dict],
) -> list[dict]:
    """Simple fallback when LLM merge fails: use whisper text with speaker labels."""
    # Use whichever text is longer (usually more complete)
    text = whisper_text if len(whisper_text) >= len(medasr_text) else medasr_text
    
    if not speaker_segments:
        return [{"speaker_id": "unknown", "text": text, "start": 0.0, "end": 0.0}]
    
    # Split text roughly by number of segments
    words = text.split()
    n_segs = len(speaker_segments)
    words_per_seg = max(1, len(words) // n_segs)
    
    turns = []
    for i, seg in enumerate(speaker_segments):
        start_idx = i * words_per_seg
        end_idx = start_idx + words_per_seg if i < n_segs - 1 else len(words)
        seg_text = " ".join(words[start_idx:end_idx]).strip()
        if seg_text:
            turns.append({
                "speaker_id": seg["speaker_id"],
                "text": seg_text,
                "start": seg["start"],
                "end": seg["end"],
            })
    
    return turns if turns else [{"speaker_id": "unknown", "text": text, "start": 0.0, "end": 0.0}]
