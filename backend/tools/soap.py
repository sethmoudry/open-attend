"""SOAP note section drafting and full-transcript generation."""

import asyncio
import json as _json
import logging

import os

from llm import call_medgemma_json
from models import Medication, SOAPNote
from agents import SOAP_DRAFT_PROMPT, FULL_TRANSCRIPT_SOAP_PROMPT, ACI_NOTE_PROMPT, TRANSCRIPT_SECTION_PROMPT, SOAP_VERIFICATION_PROMPT

logger = logging.getLogger(__name__)


async def draft_soap_section(section: str, data: dict) -> str:
    """Draft a single SOAP section from structured data.

    Args:
        section: One of "Subjective", "Objective", "Assessment", "Plan".
        data: Dict of relevant clinical data for this section.

    Returns:
        Drafted text for the section.
    """
    data_str = _json.dumps(data, indent=2, default=str)
    prompt = SOAP_DRAFT_PROMPT.format(section=section, data=data_str)
    result = await call_medgemma_json(prompt)
    return result.get("text", "")


async def draft_full_soap(
    symptoms: list[str],
    medications: list[Medication],
    exam_findings: list[str],
    differential: list[str],
    orders: list[dict],
    allergies: list[str],
    family_history: list[str],
) -> SOAPNote:
    """Draft all four SOAP sections and return a SOAPNote."""
    subjective_data = {
        "chief_complaint_symptoms": symptoms,
        "medications_reported": [m.model_dump() for m in medications],
        "allergies": allergies,
        "family_history": family_history,
    }
    objective_data = {
        "exam_findings": exam_findings,
    }
    assessment_data = {
        "symptoms": symptoms,
        "differential_diagnosis": differential,
    }
    plan_data = {
        "medications": [m.model_dump() for m in medications],
        "orders": orders,
        "differential": differential,
    }

    # Draft all sections concurrently
    s, o, a, p = await asyncio.gather(
        draft_soap_section("Subjective", subjective_data),
        draft_soap_section("Objective", objective_data),
        draft_soap_section("Assessment", assessment_data),
        draft_soap_section("Plan", plan_data),
    )

    return SOAPNote(subjective=s, objective=o, assessment=a, plan=p)


async def draft_soap_from_transcript(transcript: str) -> dict:
    """Generate a SOAP note from a complete conversation transcript (eval-only).

    Returns:
        {"full_text": str, "sections": {"subjective": ..., "objective": ..., "assessment": ..., "plan": ...}}
    """
    result = await call_medgemma_json(
        FULL_TRANSCRIPT_SOAP_PROMPT.format(transcript=transcript),
        temperature=0.0,
        max_tokens=2048,
    )
    sections = {
        "subjective": result.get("subjective", ""),
        "objective": result.get("objective", ""),
        "assessment": result.get("assessment", ""),
        "plan": result.get("plan", ""),
    }
    full_text = (
        f"SUBJECTIVE\n{sections['subjective']}\n\n"
        f"OBJECTIVE\n{sections['objective']}\n\n"
        f"ASSESSMENT\n{sections['assessment']}\n\n"
        f"PLAN\n{sections['plan']}"
    )
    return {"full_text": full_text, "sections": sections}


# Section-specific guidance for TRANSCRIPT_SECTION_PROMPT
_SECTION_GUIDANCE = {
    "Subjective": (
        "Extract patient-reported information ONLY: Chief Complaint, "
        "HPI using OLDCARTS (Onset, Location, Duration, Character, "
        "Aggravating/Relieving, Timing, Severity — only elements discussed), "
        "ROS (only symptoms explicitly confirmed or denied), "
        "PMH/PSH/FH/SH, current medications, allergies."
    ),
    "Objective": (
        "Extract physician-observed and measured data ONLY: "
        "vital signs (only if numeric values stated), "
        "physical exam findings (only those verbally described — if exam performed "
        "but not verbalized, write 'Exam performed, findings not documented'), "
        "lab/imaging results discussed."
    ),
    "Assessment": (
        "Extract the physician's clinical assessment: "
        "working diagnoses as stated, clinical reasoning connecting "
        "subjective/objective findings to each diagnosis, "
        "ICD-10 codes only if diagnosis clearly stated."
    ),
    "Plan": (
        "Extract the treatment plan as stated by the physician: "
        "medications prescribed (name, dose, frequency as stated), "
        "diagnostic orders, referrals, follow-up timeline, "
        "patient education given. Only include explicitly communicated elements."
    ),
}


async def draft_soap_from_transcript_sectional(transcript: str) -> dict:
    """Generate SOAP note section-by-section from transcript (eval path).

    Makes 4 LLM calls, one per section, each focused on extracting
    only that section's content from the full transcript. Then runs
    a verification pass to remove hallucinations and catch omissions.
    """
    sections = {}
    for section_name in ["Subjective", "Objective", "Assessment", "Plan"]:
        prompt = TRANSCRIPT_SECTION_PROMPT.format(
            section=section_name,
            section_guidance=_SECTION_GUIDANCE[section_name],
            transcript=transcript,
        )
        result = await call_medgemma_json(prompt, temperature=0.0, max_tokens=1024)
        sections[section_name.lower()] = result.get("text", "Not documented.")

    # Two-pass verification
    verified = await verify_soap_note(transcript, sections)
    sections = {
        "subjective": verified.get("subjective", sections["subjective"]),
        "objective": verified.get("objective", sections["objective"]),
        "assessment": verified.get("assessment", sections["assessment"]),
        "plan": verified.get("plan", sections["plan"]),
    }

    full_text = (
        f"SUBJECTIVE\n{sections['subjective']}\n\n"
        f"OBJECTIVE\n{sections['objective']}\n\n"
        f"ASSESSMENT\n{sections['assessment']}\n\n"
        f"PLAN\n{sections['plan']}"
    )
    return {"full_text": full_text, "sections": sections}


async def verify_soap_note(transcript: str, soap_sections: dict) -> dict:
    """Two-pass verification: send draft + transcript back for self-correction."""
    soap_text = "\n\n".join(
        f"{k.upper()}\n{v}" for k, v in soap_sections.items()
    )
    result = await call_medgemma_json(
        SOAP_VERIFICATION_PROMPT.format(transcript=transcript, soap_note=soap_text),
        temperature=0.0,
        max_tokens=2048,
    )
    changes = result.pop("changes_made", [])
    if changes:
        logger.info("Verification made %d changes: %s", len(changes), changes[:5])
    return result


async def generate_aci_note(transcript: str) -> dict:
    """Generate an ACI-Bench format clinical note from a dialogue (eval-only).

    Returns:
        {"full_text": str, "sections": {"history_of_present_illness": ..., ...}}
    """
    result = await call_medgemma_json(
        ACI_NOTE_PROMPT.format(transcript=transcript),
        temperature=0.0,
        max_tokens=2048,
    )
    sections = {
        "history_of_present_illness": result.get("history_of_present_illness", ""),
        "physical_examination": result.get("physical_examination", ""),
        "results": result.get("results", ""),
        "assessment_and_plan": result.get("assessment_and_plan", ""),
    }
    full_text = (
        f"HISTORY OF PRESENT ILLNESS\n{sections['history_of_present_illness']}\n\n"
        f"PHYSICAL EXAMINATION\n{sections['physical_examination']}\n\n"
        f"RESULTS\n{sections['results']}\n\n"
        f"ASSESSMENT AND PLAN\n{sections['assessment_and_plan']}"
    )
    return {"full_text": full_text, "sections": sections}
