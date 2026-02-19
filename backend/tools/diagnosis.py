"""Differential diagnosis generation."""

import logging

from llm import call_medgemma_json
from agents import DIFFERENTIAL_PROMPT

logger = logging.getLogger(__name__)


async def build_differential(
    symptoms: list[str], history: list[str]
) -> list[str]:
    """Build a ranked differential diagnosis from symptoms and history."""
    if not symptoms:
        return []

    prompt = DIFFERENTIAL_PROMPT.format(
        symptoms=", ".join(symptoms),
        history=", ".join(history) if history else "None provided",
    )
    result = await call_medgemma_json(prompt)
    return result.get("differential", [])
