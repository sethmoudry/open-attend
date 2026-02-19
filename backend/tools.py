"""Individual tool functions called by the orchestrator.

Each tool takes minimal input, calls MedGemma with a focused prompt,
and returns structured data matching the Pydantic models.
"""

import logging
from typing import Optional

import httpx

from llm import call_medgemma_json
from models import (
    AlertPriority,
    AlertType,
    ClinicalAlert,
    DiagnosisCode,
    FollowUpItem,
    FollowUpType,
    InteractionFlag,
    LabReport,
    Medication,
    PatientSummary,
    Severity,
    SOAPNote,
)

from typing import Sequence
from prompts import (
    CPT_EXTRACTION_PROMPT,
    DIFFERENTIAL_PROMPT,
    FOLLOWUP_EXTRACTION_PROMPT,
    ICD10_EXTRACTION_PROMPT,
    INTERACTION_CHECK_PROMPT,
    LAB_ALERT_PROMPT,
    LAB_EXTRACTION_PROMPT,
    MEDICATION_EXTRACTION_PROMPT,
    MENTAL_HEALTH_PROMPT,
    ORDER_EXTRACTION_PROMPT,
    PATIENT_SUMMARY_PROMPT,
    RED_FLAG_PROMPT,
    SOAP_DRAFT_PROMPT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Medication extraction
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Drug interaction check
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Differential diagnosis
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SOAP section drafting
# ---------------------------------------------------------------------------

async def draft_soap_section(section: str, data: dict) -> str:
    """Draft a single SOAP section from structured data.

    Args:
        section: One of "Subjective", "Objective", "Assessment", "Plan".
        data: Dict of relevant clinical data for this section.

    Returns:
        Drafted text for the section.
    """
    import json as _json

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
    import asyncio

    s, o, a, p = await asyncio.gather(
        draft_soap_section("Subjective", subjective_data),
        draft_soap_section("Objective", objective_data),
        draft_soap_section("Assessment", assessment_data),
        draft_soap_section("Plan", plan_data),
    )

    return SOAPNote(subjective=s, objective=o, assessment=a, plan=p)


# ---------------------------------------------------------------------------
# Red flag detection
# ---------------------------------------------------------------------------

_URGENCY_TO_PRIORITY = {
    "critical": AlertPriority.CRITICAL,
    "high": AlertPriority.HIGH,
    "medium": AlertPriority.MEDIUM,
    "low": AlertPriority.LOW,
}


async def detect_red_flags(
    chunk_text: str,
    symptoms: list[str],
    chunk_id: Optional[str] = None,
) -> list[ClinicalAlert]:
    """Detect red-flag symptoms requiring urgent attention."""
    prompt = RED_FLAG_PROMPT.format(
        text=chunk_text,
        symptoms=", ".join(symptoms) if symptoms else "None yet",
    )
    result = await call_medgemma_json(prompt)

    alerts: list[ClinicalAlert] = []
    for entry in result.get("red_flags", []):
        finding = entry.get("finding", "")
        if not finding:
            continue
        urgency = entry.get("urgency", "high").lower()
        priority = _URGENCY_TO_PRIORITY.get(urgency, AlertPriority.HIGH)

        reasoning = entry.get("reasoning", "")
        message = f"RED FLAG: {finding}"
        if reasoning:
            message += f" -- {reasoning}"

        alerts.append(
            ClinicalAlert(
                type=AlertType.CRITICAL_VALUE,
                message=message,
                source_chunk_id=chunk_id,
                priority=priority,
            )
        )
    return alerts


# ---------------------------------------------------------------------------
# Mental health signal detection
# ---------------------------------------------------------------------------

async def detect_mental_health_signals(
    chunk_text: str, chunk_id: Optional[str] = None
) -> list[ClinicalAlert]:
    """Detect mental health signals that may warrant screening."""
    prompt = MENTAL_HEALTH_PROMPT.format(text=chunk_text)
    result = await call_medgemma_json(prompt)

    alerts: list[ClinicalAlert] = []
    for entry in result.get("signals", []):
        signal = entry.get("signal", "")
        if not signal:
            continue
        severity = entry.get("severity", "medium").lower()
        priority = _URGENCY_TO_PRIORITY.get(severity, AlertPriority.MEDIUM)
        screen = entry.get("recommended_screen", "")

        message = f"Mental health signal: {signal}"
        if screen:
            message += f" (consider: {screen})"

        alerts.append(
            ClinicalAlert(
                type=AlertType.GUIDELINE,
                message=message,
                source_chunk_id=chunk_id,
                priority=priority,
            )
        )
    return alerts


# ---------------------------------------------------------------------------
# Order / referral extraction
# ---------------------------------------------------------------------------

async def extract_orders(chunk_text: str) -> list[dict]:
    """Extract orders, referrals, and follow-up actions from text."""
    prompt = ORDER_EXTRACTION_PROMPT.format(text=chunk_text)
    result = await call_medgemma_json(prompt)

    orders: list[dict] = []
    for entry in result.get("orders", []):
        details = entry.get("details", "")
        if not details:
            continue
        orders.append(
            {
                "type": entry.get("type", "other"),
                "details": details,
                "urgency": entry.get("urgency", "routine"),
            }
        )
    return orders


# ---------------------------------------------------------------------------
# ICD-10 code extraction
# ---------------------------------------------------------------------------

async def extract_icd10_codes(assessment: str) -> list[DiagnosisCode]:
    """Extract ICD-10 codes from assessment text."""
    if not assessment or not assessment.strip():
        return []

    prompt = ICD10_EXTRACTION_PROMPT.format(assessment=assessment)
    try:
        result = await call_medgemma_json(prompt)
    except Exception:
        logger.exception("ICD-10 extraction failed")
        return []

    codes: list[DiagnosisCode] = []
    for entry in result.get("codes", []):
        code_val = entry.get("code", "")
        if not code_val:
            continue
        confidence = float(entry.get("confidence", 0.0))
        if confidence <= 0.5:
            continue
        codes.append(
            DiagnosisCode(
                code=code_val,
                description=entry.get("description", ""),
                confidence=confidence,
                source_section="assessment",
            )
        )
    return codes


# ---------------------------------------------------------------------------
# CPT code extraction
# ---------------------------------------------------------------------------

async def extract_cpt_codes(
    plan: str, orders: list[dict] | None = None
) -> list[DiagnosisCode]:
    """Extract CPT codes from plan text and pending orders."""
    if not plan or not plan.strip():
        return []

    orders_str = "None"
    if orders:
        orders_str = ", ".join(
            f"{o.get('type', 'other')}: {o.get('details', '')}" for o in orders
        )

    prompt = CPT_EXTRACTION_PROMPT.format(plan=plan, orders=orders_str)
    try:
        result = await call_medgemma_json(prompt)
    except Exception:
        logger.exception("CPT extraction failed")
        return []

    codes: list[DiagnosisCode] = []
    for entry in result.get("codes", []):
        code_val = entry.get("code", "")
        if not code_val:
            continue
        confidence = float(entry.get("confidence", 0.0))
        if confidence <= 0.5:
            continue
        codes.append(
            DiagnosisCode(
                code=code_val,
                description=entry.get("description", ""),
                confidence=confidence,
                source_section="plan",
            )
        )
    return codes


# ---------------------------------------------------------------------------
# Patient summary generation
# ---------------------------------------------------------------------------

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
    except Exception:
        logger.exception("Patient summary generation failed")
        return PatientSummary()

    return PatientSummary(
        visit_summary=result.get("visit_summary", ""),
        new_medications=result.get("new_medications", []),
        follow_up_steps=result.get("follow_up_steps", []),
        when_to_seek_care=result.get("when_to_seek_care", ""),
    )


# ---------------------------------------------------------------------------
# Follow-up extraction
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Lab report formatting for SOAP insertion
# ---------------------------------------------------------------------------


def format_labs_for_soap(lab_report: LabReport) -> str:
    """Format lab results as clinical shorthand for SOAP Objective section."""
    if not lab_report.results:
        return ""
    parts = []
    for r in lab_report.results:
        flag_marker = ""
        if r.flag.value == "high":
            flag_marker = " (H)"
        elif r.flag.value == "low":
            flag_marker = " (L)"
        elif r.flag.value == "critical":
            flag_marker = " (CRITICAL)"
        parts.append(f"{r.test} {r.value} {r.unit}{flag_marker}")

    header = "Labs"
    if lab_report.lab_name:
        header = f"Labs ({lab_report.lab_name})"
    if lab_report.date:
        header += f" {lab_report.date}"

    return f"{header}: {', '.join(parts)}"


# ---------------------------------------------------------------------------
# Lab value extraction (vision)
# ---------------------------------------------------------------------------


async def extract_lab_values(image_base64: str) -> dict:
    """Extract structured lab values from a lab report image using MedGemma-1.5-4b-it vision."""
    from image_tools import (
        VISION_LLM_BASE_URL,
        VISION_LLM_MAX_TOKENS,
        VISION_LLM_MODEL,
        VISION_LLM_TIMEOUT,
    )
    from llm import _extract_json

    messages = [
        {
            "role": "system",
            "content": LAB_EXTRACTION_PROMPT,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                    },
                },
                {
                    "type": "text",
                    "text": "Extract all lab values from this lab report image. Return structured JSON.",
                },
            ],
        },
    ]

    payload = {
        "model": VISION_LLM_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": VISION_LLM_MAX_TOKENS,
    }

    try:
        async with httpx.AsyncClient(timeout=VISION_LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{VISION_LLM_BASE_URL}/chat/completions", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return _extract_json(raw_text)
    except Exception:
        logger.warning(
            "Lab extraction vision call failed — returning error stub.",
            exc_info=True,
        )
        return {
            "error": "Failed to extract lab values. The vision model could not process the image.",
            "lab_name": "",
            "results": [],
        }


# ---------------------------------------------------------------------------
# Lab-aware clinical alerts
# ---------------------------------------------------------------------------


async def check_lab_alerts(
    lab_reports: Sequence[LabReport],
    medications: Sequence[Medication],
    symptoms: list[str],
    transcript_context: str = "",
) -> list[ClinicalAlert]:
    """Cross-reference abnormal lab values with meds and symptoms to generate alerts."""
    abnormal: list[str] = []
    for report in lab_reports:
        for r in report.results:
            if r.flag.value in ("high", "low", "critical"):
                abnormal.append(f"{r.test}: {r.value} {r.unit} ({r.flag.value})")

    if not abnormal:
        return []

    med_names = [m.name for m in medications] if medications else []

    prompt = LAB_ALERT_PROMPT.format(
        abnormal_labs="\n".join(f"- {a}" for a in abnormal),
        medications=", ".join(med_names) if med_names else "None",
        symptoms=", ".join(symptoms) if symptoms else "None",
        transcript_context=transcript_context[:500] if transcript_context else "None",
    )

    try:
        result = await call_medgemma_json(prompt)
    except Exception:
        logger.exception("Lab alert check failed")
        return []

    alerts: list[ClinicalAlert] = []
    for alert_data in result.get("alerts", []):
        msg = alert_data.get("message", "")
        if not msg:
            continue
        priority_str = alert_data.get("priority", "medium").lower()
        try:
            priority = AlertPriority(priority_str)
        except ValueError:
            priority = AlertPriority.MEDIUM
        alerts.append(
            ClinicalAlert(
                type=AlertType.CRITICAL_VALUE,
                message=msg,
                priority=priority,
            )
        )
    return alerts


# ---------------------------------------------------------------------------
# Follow-up extraction
# ---------------------------------------------------------------------------

async def extract_follow_ups(
    plan: str, transcript_text: str = ""
) -> list[FollowUpItem]:
    """Extract follow-up items from plan and transcript."""
    if not plan and not transcript_text:
        return []

    prompt = FOLLOWUP_EXTRACTION_PROMPT.format(
        plan=plan or "None",
        transcript=transcript_text or "None",
    )
    try:
        result = await call_medgemma_json(prompt)
    except Exception:
        logger.exception("Follow-up extraction failed")
        return []

    items: list[FollowUpItem] = []
    for entry in result.get("follow_ups", []):
        action = entry.get("action", "")
        if not action:
            continue
        raw_type = entry.get("type", "other").lower()
        try:
            fu_type = FollowUpType(raw_type)
        except ValueError:
            fu_type = FollowUpType.OTHER
        items.append(
            FollowUpItem(
                action=action,
                type=fu_type,
                timeframe=entry.get("timeframe"),
                details=entry.get("details"),
            )
        )
    return items
