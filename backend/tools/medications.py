"""Medication extraction and drug interaction checking."""

import logging
from typing import Optional

from llm import call_medgemma_json
from models import InteractionFlag, Medication, Severity
from agents import MEDICATION_EXTRACTION_PROMPT, INTERACTION_CHECK_PROMPT

logger = logging.getLogger(__name__)


async def extract_medications(
    chunk_text: str,
    chunk_id: Optional[str] = None,
    source: str = "transcript",  # "patient_reported" | "prescribed" | "transcript"
) -> list[Medication]:
    """Extract medications from a transcript chunk.

    Args:
        chunk_text: Raw transcript text to extract from.
        chunk_id: ID of the source transcript chunk.
        source: Provenance of the medication mention —
            "patient_reported" (patient said it), "prescribed" (doctor said it),
            or "transcript" (unknown/default).
    """
    prompt = MEDICATION_EXTRACTION_PROMPT.format(text=chunk_text)
    result = await call_medgemma_json(prompt)

    medications: list[Medication] = []
    for entry in result.get("medications", []):
        if not entry.get("name"):
            continue
        medications.append(
            Medication(
                name=entry["name"],
                dose=entry.get("dose"),
                frequency=entry.get("frequency"),
                source=source,
                chunk_id=chunk_id,
            )
        )
    return medications


async def check_interactions(
    medications: list[Medication],
) -> list[InteractionFlag]:
    """Check for drug-drug interactions among current medications."""
    if len(medications) < 2:
        return []

    med_list = ", ".join(
        f"{m.name}" + (f" {m.dose}" if m.dose else "") for m in medications
    )
    prompt = INTERACTION_CHECK_PROMPT.format(medications=med_list)
    result = await call_medgemma_json(prompt)

    flags: list[InteractionFlag] = []
    for entry in result.get("interactions", []):
        severity_raw = entry.get("severity", "low").lower()
        try:
            severity = Severity(severity_raw)
        except ValueError:
            severity = Severity.LOW

        flags.append(
            InteractionFlag(
                drug_a=entry.get("drug_a", ""),
                drug_b=entry.get("drug_b", ""),
                severity=severity,
                mechanism=entry.get("mechanism"),
                recommendation=entry.get("recommendation"),
            )
        )
    return flags
