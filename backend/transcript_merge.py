"""LLM-based transcript merger — entity-guided correction of Whisper using MedASR medical terms."""

import json
import logging
from typing import Optional
from llm import call_medgemma_json

logger = logging.getLogger(__name__)

# System prompt for entity-guided correction
_MERGE_SYSTEM_PROMPT = """You are a medical transcript corrector. You receive a base transcript and a list of medical terms detected by a specialist medical ASR model.

Your job: correct any misspelled or misrecognized medical terminology in the transcript using the detected terms as reference.

Rules:
1. Use the detected medical terms to fix misspellings of drugs, diagnoses, procedures, anatomy, symptoms, and lab tests
2. Do NOT change non-medical words — preserve all conversational content exactly as-is
3. If a detected term doesn't clearly correspond to anything in the transcript, ignore it
4. Assign text to speakers based on diarization timestamps
5. Output valid JSON only — no markdown, no explanation"""

# Entity extraction prompt (same as eval pipeline uses)
_ENTITY_PROMPT = """\
You are a medical NLP system. Extract all medical entities from the text below. \
Include: medications, diagnoses, symptoms, procedures, lab tests, vital signs, \
anatomical terms, and medical devices.

TEXT:
{text}

Return JSON:
{{"entities": ["entity1", "entity2", ...]}}

Rules:
- Normalize to lowercase.
- Use generic drug names when possible.
- Remove duplicates."""


async def _extract_medasr_entities(medasr_text: str) -> list[str]:
    """Extract medical entities from MedASR output."""
    if not medasr_text or len(medasr_text.strip()) < 10:
        return []
    try:
        result = await call_medgemma_json(
            _ENTITY_PROMPT.format(text=medasr_text[:8000]),
            temperature=0.0,
            max_tokens=1024,
        )
        entities = result.get("entities", []) if isinstance(result, dict) else []
        return [e for e in entities if isinstance(e, str) and e.strip()]
    except Exception as exc:
        logger.warning("MedASR entity extraction failed: %s", exc)
        return []


async def merge_transcripts(
    medasr_text: str,
    whisper_text: str,
    speaker_segments: list[dict],
    previous_turns: list[dict] | None = None,
) -> list[dict]:
    """Merge MedASR + Whisper using entity-guided correction.

    Strategy: Use Whisper as the base transcript (lower WER overall),
    extract medical entities from MedASR (its strength), then ask
    the LLM to correct only medical terminology in Whisper using
    MedASR's entities as reference.

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

    # If only one transcript available, skip merge
    if not whisper_text:
        return _fallback_merge(medasr_text, "", speaker_segments)
    if not medasr_text:
        return _fallback_merge("", whisper_text, speaker_segments)

    # Step 1: Extract medical entities from MedASR output
    entities = await _extract_medasr_entities(medasr_text)

    if not entities:
        logger.info("No MedASR entities extracted, using Whisper text as-is")
        return _fallback_merge("", whisper_text, speaker_segments)

    logger.info("Extracted %d medical entities from MedASR for correction", len(entities))

    # Step 2: Build correction prompt
    prompt_parts = []

    if previous_turns:
        recent = previous_turns[-6:]
        context_lines = [f"[{t.get('speaker_id', 'unknown')}]: {t.get('text', '')}" for t in recent]
        prompt_parts.append(f"PREVIOUS CONTEXT (already transcribed, do NOT repeat):\n" + "\n".join(context_lines))

    prompt_parts.append(f"BASE TRANSCRIPT:\n{whisper_text}")
    prompt_parts.append(f"MEDICAL TERMS DETECTED BY SPECIALIST MODEL:\n{', '.join(entities)}")

    # Format speaker segments
    if speaker_segments:
        seg_lines = [f"  {s['speaker_id']}: {s['start']:.1f}s - {s['end']:.1f}s" for s in speaker_segments]
        prompt_parts.append(f"SPEAKER DIARIZATION:\n" + "\n".join(seg_lines))

    prompt_parts.append(
        'Correct any misspelled or misrecognized medical terminology in the transcript '
        'using the detected terms as reference. Do not alter non-medical words.\n'
        'Output a JSON array of speaker turns:\n'
        '[{"speaker_id": "spk_0", "text": "...", "start": 0.0, "end": 3.5}, ...]'
    )

    prompt = "\n\n".join(prompt_parts)

    try:
        result = await call_medgemma_json(
            prompt,
            system_prompt=_MERGE_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=8192,
        )

        # Handle both list and dict responses
        if isinstance(result, list):
            turns = result
        elif isinstance(result, dict):
            turns = result.get("turns") or result.get("transcript") or result.get("_raw", [])
            if isinstance(turns, str):
                # _raw may contain a JSON array that _extract_json couldn't parse
                try:
                    parsed = json.loads(turns)
                    if isinstance(parsed, list):
                        turns = parsed
                    else:
                        # LLM returned corrected text as plain string — use it
                        logger.info("LLM returned corrected text as string (%d chars)", len(turns))
                        return _fallback_merge("", turns, speaker_segments)
                except (json.JSONDecodeError, ValueError):
                    # Plain text correction — use it directly
                    logger.info("LLM returned corrected text as string (%d chars)", len(turns))
                    return _fallback_merge("", turns, speaker_segments)
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

        logger.warning("LLM correction returned no valid turns, using fallback")
        return _fallback_merge("", whisper_text, speaker_segments)

    except Exception as exc:
        logger.warning("LLM merge failed (%s), using fallback", exc)
        return _fallback_merge("", whisper_text, speaker_segments)


def _fallback_merge(
    medasr_text: str,
    whisper_text: str,
    speaker_segments: list[dict],
) -> list[dict]:
    """Simple fallback: use whisper text (or longer text) with speaker labels."""
    text = whisper_text if len(whisper_text) >= len(medasr_text) else medasr_text

    if not speaker_segments:
        return [{"speaker_id": "unknown", "text": text, "start": 0.0, "end": 0.0}]

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
