"""Speaker role assignment using MedGemma-27b-text-it."""

import logging

from llm import call_medgemma_json
from agents import SPEAKER_ROLE_ASSIGNMENT_PROMPT

logger = logging.getLogger(__name__)

ROLE_ASSIGNMENT_THRESHOLD = 3  # minimum exchanges before attempting assignment


async def assign_roles(
    labeled_exchanges: list[dict],  # [{speaker_id, text}]
) -> dict[str, dict]:
    """Infer speaker roles from labeled transcript exchanges.

    Args:
        labeled_exchanges: List of {speaker_id: str, text: str} dicts

    Returns:
        {speaker_id: {role, confidence, reasoning}} mapping
    """
    # Only attempt after enough exchanges
    if len(labeled_exchanges) < ROLE_ASSIGNMENT_THRESHOLD:
        return {}

    # Format exchanges for the prompt (cap at 20 to keep context manageable)
    formatted = "\n".join(
        f"{ex['speaker_id']}: {ex['text']}"
        for ex in labeled_exchanges[:20]
    )

    prompt = SPEAKER_ROLE_ASSIGNMENT_PROMPT.format(labeled_exchanges=formatted)
    result = await call_medgemma_json(prompt)

    if not isinstance(result.get("assignments"), list):
        logger.warning("Unexpected role assignment response: %s", result)
        return {}

    assignments: dict[str, dict] = {}
    for entry in result.get("assignments", []):
        sid = entry.get("speaker_id", "")
        role = entry.get("role", "unknown")
        if sid and role:
            assignments[sid] = {
                "role": role,
                "confidence": float(entry.get("confidence", 0.0)),
                "reasoning": entry.get("reasoning", ""),
            }

    return assignments


async def should_reassign(
    current_assignments: dict[str, str],
    new_speaker_ids: list[str],
) -> bool:
    """Check if role assignment should be re-evaluated.

    Returns True if a new, unassigned speaker appears.
    """
    for sid in new_speaker_ids:
        if sid not in current_assignments:
            return True
    return False
