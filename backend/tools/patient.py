"""Patient-facing summary generation."""

import logging

import httpx

from llm import call_medgemma_json
from models import FollowUpItem, Medication, PatientSummary, SOAPNote
from agents import PATIENT_SUMMARY_PROMPT

logger = logging.getLogger(__name__)


async def generate_patient_summary(
    soap: SOAPNote,
    medications: list[Medication],
    follow_ups: list[FollowUpItem],
) -> PatientSummary:
    """Generate plain-language patient summary."""
    soap_text = (
        f"Subjective: {soap.subjective}\n"
        f"Objective: {soap.objective}\n"
        f"Assessment: {soap.assessment}\n"
        f"Plan: {soap.plan}"
    )
    med_list = ", ".join(
        f"{m.name}" + (f" {m.dose}" if m.dose else "")
        + (f" {m.frequency}" if m.frequency else "")
        for m in medications
    ) or "None"
    fu_list = ", ".join(
        f"{f.action} ({f.type.value})"
        + (f" - {f.timeframe}" if f.timeframe else "")
        for f in follow_ups
    ) or "None"

    prompt = PATIENT_SUMMARY_PROMPT.format(
        soap_note=soap_text,
        medications=med_list,
        follow_ups=fu_list,
    )
    try:
        result = await call_medgemma_json(prompt, max_tokens=2048)
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("Patient summary generation failed")
        return PatientSummary()

    return PatientSummary(
        visit_summary=result.get("visit_summary", ""),
        new_medications=result.get("new_medications", []),
        follow_up_steps=result.get("follow_up_steps", []),
        when_to_seek_care=result.get("when_to_seek_care", ""),
    )
