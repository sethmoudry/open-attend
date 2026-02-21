"""Central orchestrator for real-time transcript chunk processing.

Receives TranscriptChunk objects, runs them through MedGemma for
classification, then dispatches to specialised tool functions and
merges results back into the Session.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from llm import call_medgemma_json
from models import (
    AlertPriority,
    AlertType,
    ClinicalAlert,
    Medication,
    Session,
    SOAPStatus,
    TranscriptChunk,
)
from prompts import CHUNK_ANALYSIS_PROMPT_TEMPLATE, ORCHESTRATOR_SYSTEM_PROMPT
from role_assignment import assign_roles, should_reassign, ROLE_ASSIGNMENT_THRESHOLD
from tools import (
    build_differential,
    check_interactions,
    detect_mental_health_signals,
    detect_red_flags,
    draft_full_soap,
    extract_medications,
    extract_orders,
)

logger = logging.getLogger(__name__)

SOAP_REFRESH_INTERVAL = 3  # refresh SOAP draft every N chunks


def _fib_intervals(start: float) -> list[float]:
    """Generate Fibonacci-increasing intervals starting from *start* seconds.

    Returns [start, start, 2*start, 3*start, 5*start, 8*start, ...] (20 items).
    """
    fibs = [1, 1]
    for _ in range(18):
        fibs.append(fibs[-1] + fibs[-2])
    return [start * f for f in fibs]


# Per-tool throttle schedules (Fibonacci-increasing intervals in seconds)
_ALERT_INTERVALS = _fib_intervals(30.0)       # 30, 30, 60, 90, 150, ...
_MED_INTERVALS = _fib_intervals(30.0)         # 30, 30, 60, 90, 150, ...
_DIFF_INTERVALS = _fib_intervals(60.0)        # 60, 60, 120, 180, 300, ...


class _ToolThrottle:
    """Track per-tool call count and enforce Fibonacci-increasing cooldowns."""

    def __init__(self, intervals: list[float]) -> None:
        self._intervals = intervals
        self._call_count = 0
        self._last_time = 0.0

    def is_due(self) -> bool:
        now = time.monotonic()
        idx = min(self._call_count, len(self._intervals) - 1)
        interval = self._intervals[idx]
        return (now - self._last_time) >= interval

    def record_call(self) -> None:
        self._call_count += 1
        self._last_time = time.monotonic()

    def seconds_until_due(self) -> float:
        """Return seconds until this tool is next due. 0 means ready now."""
        if self._last_time == 0.0:
            return 0.0
        now = time.monotonic()
        idx = min(self._call_count, len(self._intervals) - 1)
        interval = self._intervals[idx]
        remaining = interval - (now - self._last_time)
        return max(0.0, remaining)

    def reset(self) -> None:
        """Reset throttle so next call is immediately due."""
        self._last_time = 0.0


_alert_throttle = _ToolThrottle(_ALERT_INTERVALS)
_med_throttle = _ToolThrottle(_MED_INTERVALS)
_diff_throttle = _ToolThrottle(_DIFF_INTERVALS)


def _dedup_list(items: list) -> list:
    """Remove duplicate strings/values while preserving order."""
    seen: set = set()
    result = []
    for item in items:
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _dedup_alerts(existing: list, new_alerts: list) -> list:
    """Merge new alerts into existing, deduplicating by message."""
    existing_msgs = {a.message if hasattr(a, "message") else str(a) for a in existing}
    for alert in new_alerts:
        msg = alert.message if hasattr(alert, "message") else str(alert)
        if msg not in existing_msgs:
            existing.append(alert)
            existing_msgs.add(msg)
    return existing


@dataclass
class ClinicalContext:
    """Running clinical context built from transcript chunks."""

    symptoms: list[str] = field(default_factory=list)
    medications: list[dict] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    family_history: list[str] = field(default_factory=list)
    exam_findings: list[str] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    differential: list[str] = field(default_factory=list)
    soap: dict = field(
        default_factory=lambda: {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": "",
        }
    )
    alerts: list[dict] = field(default_factory=list)
    chunk_count: int = 0
    speaker_counts: dict[str, int] = field(default_factory=dict)


def _context_from_session(session: Session) -> ClinicalContext:
    """Build a ClinicalContext snapshot from current session state."""
    # Build speaker distribution stats
    speaker_counts: dict[str, int] = {}
    for chunk in session.transcript_chunks:
        role = chunk.speaker.value if chunk.speaker else "unknown"
        speaker_counts[role] = speaker_counts.get(role, 0) + 1

    ctx = ClinicalContext(
        symptoms=[],  # accumulated via orchestrator; not stored on Session directly
        medications=[
            {"name": m.name, "dose": m.dose, "frequency": m.frequency}
            for m in session.medications
        ],
        allergies=[],
        family_history=[],
        exam_findings=[],
        orders=[],
        differential=list(session.differential),
        soap={
            "subjective": session.soap_note.subjective,
            "objective": session.soap_note.objective,
            "assessment": session.soap_note.assessment,
            "plan": session.soap_note.plan,
        },
        alerts=[
            {"type": a.type.value, "message": a.message, "priority": a.priority.value}
            for a in session.clinical_alerts
        ],
        chunk_count=len(session.transcript_chunks),
    )
    ctx.speaker_counts = speaker_counts
    return ctx


async def _classify_chunk(
    chunk: TranscriptChunk, ctx: ClinicalContext
) -> dict:
    """First pass: send chunk + context to MedGemma for classification."""
    # Format speaker stats for context
    speaker_counts: dict[str, int] = getattr(ctx, "speaker_counts", {})
    speaker_stats = (
        ", ".join(f"{role}: {cnt}" for role, cnt in speaker_counts.items())
        if speaker_counts
        else "No prior chunks"
    )

    prompt = CHUNK_ANALYSIS_PROMPT_TEMPLATE.format(
        symptoms=", ".join(ctx.symptoms) if ctx.symptoms else "None yet",
        medications=", ".join(
            m.get("name", "") for m in ctx.medications
        )
        if ctx.medications
        else "None yet",
        allergies=", ".join(ctx.allergies) if ctx.allergies else "None yet",
        family_history=", ".join(ctx.family_history)
        if ctx.family_history
        else "None yet",
        exam_findings=", ".join(ctx.exam_findings)
        if ctx.exam_findings
        else "None yet",
        differential=", ".join(ctx.differential)
        if ctx.differential
        else "None yet",
        chunk_count=ctx.chunk_count + 1,
        speaker_role=chunk.speaker.value if chunk.speaker else "unknown",
        speaker_id=chunk.speaker_id or "unknown",
        speaker_stats=speaker_stats,
        chunk_text=chunk.text,
    )
    return await call_medgemma_json(
        prompt, system_prompt=ORCHESTRATOR_SYSTEM_PROMPT
    )


async def process_chunk(
    chunk: TranscriptChunk, session: Session
) -> dict[str, Any]:
    """Process a transcript chunk through MedGemma and tool functions.

    Returns a dict of updates to apply to the session state via
    ``SessionStore.update_session``.

    Decision points:
      D1: Medication mentioned   -> extract_medications
      D2: Allergy mentioned      -> extract and pin alert
      D3: Family history         -> flag for screening
      D4: Red flag symptoms      -> urgent alert
      D5: Mental health signals  -> screening prompt
      D6: Order/referral         -> pre-fill order
      D7: Exam findings          -> route to Objective
      D8: New symptoms           -> update differential
      D9: Every 3 chunks         -> refresh SOAP draft
    """
    ctx = _context_from_session(session)

    # --- Step 1: Classify the chunk ----------------------------------------
    classification = await _classify_chunk(chunk, ctx)

    # Accumulate extracted data from classification
    new_symptoms: list[str] = classification.get("symptoms", [])
    new_allergies: list[str] = classification.get("allergies", [])
    new_family_hx: list[str] = classification.get("family_history", [])
    new_exam: list[str] = classification.get("exam_findings", [])
    raw_mh_signals: list[str] = classification.get("mental_health_signals", [])
    raw_alerts: list[dict] = classification.get("alerts", [])
    soap_updates: dict = classification.get("soap_updates", {})

    # Update context for downstream tools
    ctx.symptoms.extend(new_symptoms)
    ctx.allergies.extend(new_allergies)
    ctx.family_history.extend(new_family_hx)
    ctx.exam_findings.extend(new_exam)
    ctx.chunk_count += 1

    # --- Step 2: Dispatch to specialised tools concurrently ----------------
    tasks: dict[str, asyncio.Task] = {}

    # D1: Medication extraction — speaker-aware source tagging
    speaker_role = chunk.speaker.value if chunk.speaker else "unknown"
    med_source = classification.get("medication_source", "transcript")
    if med_source not in ("patient_reported", "prescribed", "transcript"):
        # Fallback: infer from speaker role
        if speaker_role == "patient":
            med_source = "patient_reported"
        elif speaker_role in ("doctor", "physician"):
            med_source = "prescribed"
        else:
            med_source = "transcript"
    # D3: Medications — throttled (30s Fibonacci-increasing)
    if _med_throttle.is_due():
        tasks["medications"] = asyncio.create_task(
            extract_medications(chunk.text, chunk_id=chunk.id, source=med_source)
        )
        _med_throttle.record_call()

    # D4: Red flags / alerts — throttled (30s Fibonacci-increasing)
    if _alert_throttle.is_due():
        tasks["red_flags"] = asyncio.create_task(
            detect_red_flags(
                chunk.text,
                symptoms=ctx.symptoms,
                chunk_id=chunk.id,
            )
        )
        _alert_throttle.record_call()

    # D5: Mental health — shares alert throttle
    if raw_mh_signals and "red_flags" in tasks:
        tasks["mental_health"] = asyncio.create_task(
            detect_mental_health_signals(chunk.text, chunk_id=chunk.id)
        )

    # D6: Orders — run if classification found orders (no throttle, rare)
    raw_orders = classification.get("orders", [])
    if raw_orders:
        tasks["orders"] = asyncio.create_task(extract_orders(chunk.text))

    # D8: Differential — throttled (60s Fibonacci-increasing)
    if new_symptoms and _diff_throttle.is_due():
        all_symptoms = list({s for s in ctx.symptoms})
        tasks["differential"] = asyncio.create_task(
            build_differential(all_symptoms, ctx.family_history)
        )
        _diff_throttle.record_call()

    # Await all dispatched tasks
    results: dict[str, Any] = {}
    for key, task in tasks.items():
        try:
            results[key] = await task
        except Exception:
            logger.exception("Tool %s failed", key)
            results[key] = [] if key != "differential" else ctx.differential

    # --- Step 3: Collect extracted medications and check interactions -------
    new_meds: list[Medication] = results.get("medications", [])
    all_session_meds = list(session.medications) + new_meds

    interaction_flags = []
    if new_meds and len(all_session_meds) >= 2:
        try:
            interaction_flags = await check_interactions(all_session_meds)
        except Exception:
            logger.exception("Interaction check failed")

    # --- Step 4: Build alerts list -----------------------------------------
    new_alerts: list[ClinicalAlert] = []

    # Red flag alerts from tool
    new_alerts.extend(results.get("red_flags", []))

    # Mental health alerts from tool
    new_alerts.extend(results.get("mental_health", []))

    # Allergy alerts (D2)
    for allergy in new_allergies:
        new_alerts.append(
            ClinicalAlert(
                type=AlertType.ALLERGY,
                message=f"Allergy reported: {allergy}",
                source_chunk_id=chunk.id,
                priority=AlertPriority.HIGH,
            )
        )

    # Drug interaction alerts
    for flag in interaction_flags:
        new_alerts.append(
            ClinicalAlert(
                type=AlertType.DRUG_INTERACTION,
                message=(
                    f"Interaction: {flag.drug_a} + {flag.drug_b} "
                    f"({flag.severity.value}) -- {flag.recommendation or 'Review'}"
                ),
                source_chunk_id=chunk.id,
                priority=(
                    AlertPriority.CRITICAL
                    if flag.severity.value in ("high", "critical")
                    else AlertPriority.MEDIUM
                ),
            )
        )

    # Classification-level alerts
    for raw in raw_alerts:
        msg = raw.get("message", "")
        if not msg:
            continue
        priority_str = raw.get("priority", "medium").lower()
        try:
            priority = AlertPriority(priority_str)
        except ValueError:
            priority = AlertPriority.MEDIUM

        alert_type_str = raw.get("type", "guideline").lower()
        try:
            alert_type = AlertType(alert_type_str)
        except ValueError:
            alert_type = AlertType.GUIDELINE

        new_alerts.append(
            ClinicalAlert(
                type=alert_type,
                message=msg,
                source_chunk_id=chunk.id,
                priority=priority,
            )
        )

    # --- Step 5: SOAP updates (D7, D9) ------------------------------------
    soap_note = session.soap_note.model_copy()

    # Speaker-aware SOAP routing — constrain which sections each role can update
    if soap_updates:
        if speaker_role == "patient":
            # Patient speech routes primarily to Subjective.
            # Never let patient speech write to Objective (exam findings).
            soap_updates.pop("objective", None)
        elif speaker_role in ("doctor", "physician"):
            # Doctor can contribute to any SOAP section — no filtering needed.
            pass
        else:
            # Other speakers (parent, nurse, interpreter) — only keep updates
            # if the LLM explicitly routed them (i.e., clinically relevant).
            # Drop assessment/plan since those are clinician-authored sections.
            soap_updates.pop("assessment", None)
            soap_updates.pop("plan", None)

    # Apply incremental SOAP updates from classification
    if soap_updates:
        if soap_updates.get("subjective"):
            soap_note.subjective = _append_text(
                soap_note.subjective, soap_updates["subjective"]
            )
        if soap_updates.get("objective"):
            soap_note.objective = _append_text(
                soap_note.objective, soap_updates["objective"]
            )
        if soap_updates.get("assessment"):
            soap_note.assessment = _append_text(
                soap_note.assessment, soap_updates["assessment"]
            )
        if soap_updates.get("plan"):
            soap_note.plan = _append_text(
                soap_note.plan, soap_updates["plan"]
            )
        soap_note.status = SOAPStatus.IN_PROGRESS
        soap_note.last_updated = datetime.now(timezone.utc)

    # D9: Full SOAP refresh every N chunks
    total_chunks = len(session.transcript_chunks) + 1
    if total_chunks % SOAP_REFRESH_INTERVAL == 0 and total_chunks > 0:
        try:
            refreshed = await draft_full_soap(
                symptoms=ctx.symptoms,
                medications=all_session_meds,
                exam_findings=ctx.exam_findings,
                differential=results.get("differential", ctx.differential),
                orders=results.get("orders", []),
                allergies=ctx.allergies,
                family_history=ctx.family_history,
            )
            soap_note = refreshed
            soap_note.status = SOAPStatus.IN_PROGRESS
            soap_note.last_updated = datetime.now(timezone.utc)
        except Exception:
            logger.exception("SOAP refresh failed, keeping incremental updates")

    # --- Step 6: Build session update dict ---------------------------------
    chunk.processed = True

    # Merge orders into pending_orders
    new_orders = results.get("orders", [])
    pending_orders = list(session.pending_orders)
    for order in new_orders:
        order_desc = f"[{order.get('urgency', 'routine').upper()}] {order['details']}"
        if order_desc not in pending_orders:
            pending_orders.append(order_desc)

    updates: dict[str, Any] = {
        "transcript_chunks": session.transcript_chunks + [chunk],
        "medications": all_session_meds,
        "interaction_flags": _dedup_list(list(session.interaction_flags) + interaction_flags),
        "clinical_alerts": _dedup_alerts(list(session.clinical_alerts), new_alerts),
        "soap_note": soap_note,
        "differential": results.get("differential", list(session.differential)),
        "pending_orders": pending_orders,
    }

    # --- Step 7: Speaker role assignment -----------------------------------
    all_chunks = list(session.transcript_chunks) + [chunk]
    labeled_exchanges = [
        {"speaker_id": c.speaker_id, "text": c.text}
        for c in all_chunks
        if c.speaker_id and c.text
    ]

    current_role_map: dict[str, str] = {
        sp.consistent_id: sp.role
        for sp in session.speaker_profiles
        if sp.role is not None
    }
    current_speaker_ids = [
        c.speaker_id for c in all_chunks if c.speaker_id
    ]

    needs_assignment = (
        len(labeled_exchanges) >= ROLE_ASSIGNMENT_THRESHOLD
        and not session.speaker_profiles
    )
    if not needs_assignment and session.speaker_profiles:
        needs_assignment = await should_reassign(
            current_role_map, current_speaker_ids
        )

    if needs_assignment:
        try:
            role_results = await assign_roles(labeled_exchanges)
            if role_results:
                from models import SpeakerProfile

                updates["speaker_profiles"] = [
                    SpeakerProfile(
                        consistent_id=sid,
                        role=info["role"],
                        confidence=info.get("confidence", 0.0),
                        reasoning=info.get("reasoning", ""),
                    )
                    for sid, info in role_results.items()
                ]
        except Exception:
            logger.exception("Speaker role assignment failed")

    return updates


def _append_text(existing: str, addition: str) -> str:
    """Append text to an existing section, avoiding duplication."""
    addition = addition.strip()
    if not addition:
        return existing
    if addition in existing:
        return existing
    if existing:
        return f"{existing} {addition}"
    return addition
