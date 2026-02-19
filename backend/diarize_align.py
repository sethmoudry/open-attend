"""Align MedASR transcript with pyannote speaker segments.

Given a transcript string and a list of speaker segments (from diarize.py),
assigns each word to the speaker who was talking at that point in time.
Consecutive words from the same speaker are grouped into DiarizedWord spans.
"""

from dataclasses import dataclass


@dataclass
class DiarizedWord:
    speaker_id: str
    start: float
    end: float
    text: str


def align_transcript_with_speakers(
    transcript_text: str,
    transcript_start: float,
    transcript_end: float,
    speaker_segments: list,  # list of SpeakerSegment from diarize.py
) -> list[DiarizedWord]:
    """Align transcript text with speaker segments by temporal overlap.

    Since MedASR may not provide word-level timestamps, words are distributed
    proportionally across [transcript_start, transcript_end].  Each word's
    estimated time range is matched to the speaker segment with maximum
    temporal overlap.

    Returns a list of DiarizedWord spans — consecutive same-speaker words
    are merged into a single span.
    """
    if not transcript_text or not transcript_text.strip():
        return []

    words = transcript_text.split()
    if not words:
        return []

    duration = transcript_end - transcript_start
    if duration <= 0:
        # Can't distribute temporally; assign everything to first speaker or UNKNOWN
        seg0 = speaker_segments[0] if speaker_segments else None
        fallback_speaker = (
            (seg0["speaker"] if isinstance(seg0, dict) else seg0.speaker_id)
            if seg0 else "UNKNOWN"
        )
        return [
            DiarizedWord(
                speaker_id=fallback_speaker,
                start=transcript_start,
                end=transcript_end,
                text=transcript_text.strip(),
            )
        ]

    # --- Distribute words proportionally across the duration ----------------
    word_duration = duration / len(words)
    word_timings: list[tuple[str, float, float]] = []
    for i, word in enumerate(words):
        w_start = transcript_start + i * word_duration
        w_end = w_start + word_duration
        word_timings.append((word, w_start, w_end))

    # --- Assign each word to a speaker by max overlap ----------------------
    assigned: list[tuple[str, str, float, float]] = []  # (speaker, word, start, end)

    for word, w_start, w_end in word_timings:
        speaker = _find_best_speaker(w_start, w_end, speaker_segments)
        assigned.append((speaker, word, w_start, w_end))

    # --- Merge consecutive same-speaker words into spans -------------------
    if not assigned:
        return []

    spans: list[DiarizedWord] = []
    cur_speaker, cur_word, cur_start, cur_end = assigned[0]
    cur_words = [cur_word]

    for speaker, word, w_start, w_end in assigned[1:]:
        if speaker == cur_speaker:
            cur_words.append(word)
            cur_end = w_end
        else:
            spans.append(
                DiarizedWord(
                    speaker_id=cur_speaker,
                    start=cur_start,
                    end=cur_end,
                    text=" ".join(cur_words),
                )
            )
            cur_speaker = speaker
            cur_words = [word]
            cur_start = w_start
            cur_end = w_end

    # Flush last span
    spans.append(
        DiarizedWord(
            speaker_id=cur_speaker,
            start=cur_start,
            end=cur_end,
            text=" ".join(cur_words),
        )
    )

    return spans


def _find_best_speaker(
    w_start: float,
    w_end: float,
    speaker_segments: list,
) -> str:
    """Find the speaker segment with the most temporal overlap for a word.

    Falls back to "UNKNOWN" if no segments overlap.
    """
    if not speaker_segments:
        return "UNKNOWN"

    best_speaker = "UNKNOWN"
    best_overlap = 0.0

    for seg in speaker_segments:
        seg_start = seg["start"] if isinstance(seg, dict) else seg.start
        seg_end = seg["end"] if isinstance(seg, dict) else seg.end
        seg_speaker = seg["speaker"] if isinstance(seg, dict) else seg.speaker_id
        overlap_start = max(w_start, seg_start)
        overlap_end = min(w_end, seg_end)
        overlap = max(0.0, overlap_end - overlap_start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = seg_speaker

    return best_speaker
