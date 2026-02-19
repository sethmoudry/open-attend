"""Clinical alert detection: red flags, mental health, drug interactions, lab alerts."""

import logging
from typing import Optional, Sequence

import httpx

from llm import call_medgemma_json
from models import (
    AlertPriority,
    AlertType,
    ClinicalAlert,
    LabReport,
    Medication,
)
from agents import (
    ALERT_AGENT_PROMPT,
    LAB_ALERT_PROMPT,
    MENTAL_HEALTH_PROMPT,
    RED_FLAG_PROMPT,
)

logger = logging.getLogger(__name__)

_URGENCY_TO_PRIORITY = {
    "critical": AlertPriority.CRITICAL,
    "high": AlertPriority.HIGH,
    "medium": AlertPriority.MEDIUM,
    "low": AlertPriority.LOW,
}

_ALERT_TYPE_MAP = {
    "red_flag": AlertType.CRITICAL_VALUE,
    "mental_health": AlertType.GUIDELINE,
    "allergy": AlertType.ALLERGY,
    "drug_interaction": AlertType.DRUG_INTERACTION,
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


async def generate_alerts(
    chunk_text: str,
    symptoms: list[str],
    medications: list[Medication],
    allergies: list[str],
    chunk_id: Optional[str] = None,
) -> list[ClinicalAlert]:
    """Detect all alert types in a single LLM call."""
    med_names = ", ".join(m.name for m in medications) if medications else "None"
    prompt = ALERT_AGENT_PROMPT.format(
        text=chunk_text,
        symptoms=", ".join(symptoms) if symptoms else "None",
        medications=med_names,
        allergies=", ".join(allergies) if allergies else "None",
    )
    result = await call_medgemma_json(prompt)

    alerts: list[ClinicalAlert] = []
    for entry in result.get("alerts", []):
        msg = entry.get("message", "")
        if not msg:
            continue
        priority_str = entry.get("priority", "medium").lower()
        try:
            priority = AlertPriority(priority_str)
        except ValueError:
            priority = AlertPriority.MEDIUM

        alert_type_str = entry.get("type", "red_flag").lower()
        alert_type = _ALERT_TYPE_MAP.get(alert_type_str, AlertType.GUIDELINE)

        alerts.append(
            ClinicalAlert(
                type=alert_type,
                message=msg,
                source_chunk_id=chunk_id,
                priority=priority,
            )
        )
    return alerts


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
    except (httpx.HTTPError, KeyError, ValueError):
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
