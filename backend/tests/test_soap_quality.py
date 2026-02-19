"""SOAP output quality validation tests.

These integration-level tests feed realistic transcript chunks through
the orchestrator and validate the accumulated SOAP note quality.
"""

from unittest.mock import AsyncMock, patch

import pytest

from models import (
    Medication,
    Session,
    SOAPNote,
    Speaker,
    TranscriptChunk,
    VisitType,
)
from orchestrator import SOAP_REFRESH_INTERVAL, process_chunk
from tests.conftest import MOCK_RESPONSES


# Realistic visit transcript (migraine case)
VISIT_CHUNKS = [
    TranscriptChunk(
        timestamp_start=0.0,
        timestamp_end=12.5,
        speaker=Speaker.DOCTOR,
        text="Good afternoon, Maria. I understand you're having a severe headache. Can you describe what you're experiencing?",
    ),
    TranscriptChunk(
        timestamp_start=12.5,
        timestamp_end=28.0,
        speaker=Speaker.PATIENT,
        text="It started about four hours ago on the left side of my head. I saw zigzag lines before it started, and now the pain is throbbing. Light and sound make it worse. I also feel nauseous.",
    ),
    TranscriptChunk(
        timestamp_start=28.0,
        timestamp_end=42.0,
        speaker=Speaker.DOCTOR,
        text="Have you had migraines like this before? Any history of aura?",
    ),
    TranscriptChunk(
        timestamp_start=42.0,
        timestamp_end=55.0,
        speaker=Speaker.PATIENT,
        text="Yes, I get them maybe once or twice a month, but this one is the worst I've had in a while. The aura is new though, started about six months ago.",
    ),
    TranscriptChunk(
        timestamp_start=55.0,
        timestamp_end=72.0,
        speaker=Speaker.DOCTOR,
        text="I'm going to prescribe sumatriptan for acute relief and start you on topiramate for prevention. We should also discuss getting a neurology referral.",
    ),
]


def _make_mock_dispatch():
    """Create a mock that returns realistic responses for each chunk type."""
    call_count = 0

    async def _dispatch(prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        p = prompt.lower()

        # Chunk classification prompt has "=== CURRENT CONTEXT ===" — match first
        if "current context" in p:
            return {
                "symptoms": ["headache", "nausea", "photophobia"],
                "allergies": [],
                "family_history": [],
                "exam_findings": [],
                "mental_health_signals": [],
                "alerts": [],
                "orders": [],
                "medications": [],
                "medication_source": "transcript",
                "soap_routing": "subjective",
                "soap_updates": {
                    "subjective": "Severe throbbing headache with aura, nausea.",
                },
            }
        # SOAP section drafts
        if "medical openattend" in p or "draft the" in p:
            return {"text": "Patient with migraine and aura symptoms."}
        if "clinical pharmacist" in p:
            return {
                "medications": [
                    {"name": "sumatriptan", "dose": "50mg", "frequency": "PRN"},
                    {"name": "topiramate", "dose": "25mg", "frequency": "daily"},
                ]
            }
        if "interaction" in p:
            return {"interactions": []}
        if "differential" in p:
            return {"differential": ["Migraine with aura", "Tension headache"]}
        if "red flag" in p:
            return {"red_flags": []}
        if "order" in p:
            return {"orders": [{"type": "referral", "details": "Neurology", "urgency": "routine"}]}

        # Fallback chunk classification
        return {
            "symptoms": ["headache", "nausea", "photophobia"],
            "allergies": [],
            "family_history": [],
            "exam_findings": [],
            "mental_health_signals": [],
            "alerts": [],
            "orders": [],
            "medications": [],
            "medication_source": "transcript",
            "soap_routing": "subjective",
            "soap_updates": {
                "subjective": "Severe throbbing headache with aura, nausea.",
            },
        }

    return _dispatch


@pytest.mark.asyncio
async def test_full_visit_soap_generation():
    """Feed 5 transcript chunks and validate the final SOAP state."""
    mock_fn = _make_mock_dispatch()

    with (
        patch("llm.call_medgemma_json", new=mock_fn),
        patch("tools.medications.call_medgemma_json", new=mock_fn),
        patch("tools.diagnosis.call_medgemma_json", new=mock_fn),
        patch("tools.soap.call_medgemma_json", new=mock_fn),
        patch("tools.coding.call_medgemma_json", new=mock_fn),
        patch("tools.alerts.call_medgemma_json", new=mock_fn),
        patch("tools.orders.call_medgemma_json", new=mock_fn),
        patch("tools.patient.call_medgemma_json", new=mock_fn),
        patch("orchestrator.call_medgemma_json", new=mock_fn),
        patch("orchestrator.assign_roles", new_callable=AsyncMock, return_value={}),
        patch("orchestrator.should_reassign", new_callable=AsyncMock, return_value=False),
    ):
        session = Session(visit_type=VisitType.URGENT)

        for chunk in VISIT_CHUNKS:
            updates = await process_chunk(chunk, session)
            session = session.model_copy(update=updates)

        # Validate final state
        assert len(session.transcript_chunks) == 5
        assert session.soap_note.subjective  # should have patient content
        assert isinstance(session.medications, list)
        assert isinstance(session.differential, list)
        assert isinstance(session.clinical_alerts, list)


@pytest.mark.asyncio
async def test_soap_sections_non_empty_after_refresh():
    """After SOAP_REFRESH_INTERVAL chunks, all 4 sections should be populated."""
    mock_fn = _make_mock_dispatch()

    with (
        patch("llm.call_medgemma_json", new=mock_fn),
        patch("tools.medications.call_medgemma_json", new=mock_fn),
        patch("tools.diagnosis.call_medgemma_json", new=mock_fn),
        patch("tools.soap.call_medgemma_json", new=mock_fn),
        patch("tools.coding.call_medgemma_json", new=mock_fn),
        patch("tools.alerts.call_medgemma_json", new=mock_fn),
        patch("tools.orders.call_medgemma_json", new=mock_fn),
        patch("tools.patient.call_medgemma_json", new=mock_fn),
        patch("orchestrator.call_medgemma_json", new=mock_fn),
        patch("orchestrator.assign_roles", new_callable=AsyncMock, return_value={}),
        patch("orchestrator.should_reassign", new_callable=AsyncMock, return_value=False),
    ):
        session = Session(visit_type=VisitType.URGENT)

        # Feed exactly SOAP_REFRESH_INTERVAL chunks
        for chunk in VISIT_CHUNKS[:SOAP_REFRESH_INTERVAL]:
            updates = await process_chunk(chunk, session)
            session = session.model_copy(update=updates)

        soap = session.soap_note
        # After refresh, all sections should have content
        assert soap.subjective, "Subjective should be non-empty after refresh"
        assert soap.objective, "Objective should be non-empty after refresh"
        assert soap.assessment, "Assessment should be non-empty after refresh"
        assert soap.plan, "Plan should be non-empty after refresh"


@pytest.mark.asyncio
async def test_patient_speech_never_in_objective():
    """Patient-only content must not appear in the Objective section."""
    patient_symptom = "UNIQUE_PATIENT_SYMPTOM_MARKER"

    async def _dispatch(prompt, **kwargs):
        p = prompt.lower()
        if "medication" in p and "interaction" not in p:
            return {"medications": []}
        if "interaction" in p:
            return {"interactions": []}
        if "red flag" in p:
            return {"red_flags": []}
        if "differential" in p:
            return {"differential": []}
        if "soap" in p or "section" in p:
            return {"text": "Section content."}
        return {
            "symptoms": [patient_symptom],
            "allergies": [],
            "family_history": [],
            "exam_findings": [],
            "mental_health_signals": [],
            "alerts": [],
            "orders": [],
            "medications": [],
            "medication_source": "patient_reported",
            "soap_routing": "subjective",
            "soap_updates": {
                "subjective": f"Patient reports {patient_symptom}.",
                "objective": f"Should NOT appear: {patient_symptom}",
            },
        }

    chunks = [
        TranscriptChunk(
            timestamp_start=0.0,
            timestamp_end=10.0,
            speaker=Speaker.PATIENT,
            text=f"I have this {patient_symptom}.",
        ),
    ]

    with (
        patch("llm.call_medgemma_json", new=_dispatch),
        patch("tools.medications.call_medgemma_json", new=_dispatch),
        patch("tools.diagnosis.call_medgemma_json", new=_dispatch),
        patch("tools.soap.call_medgemma_json", new=_dispatch),
        patch("tools.coding.call_medgemma_json", new=_dispatch),
        patch("tools.alerts.call_medgemma_json", new=_dispatch),
        patch("tools.orders.call_medgemma_json", new=_dispatch),
        patch("tools.patient.call_medgemma_json", new=_dispatch),
        patch("orchestrator.call_medgemma_json", new=_dispatch),
        patch("orchestrator.assign_roles", new_callable=AsyncMock, return_value={}),
        patch("orchestrator.should_reassign", new_callable=AsyncMock, return_value=False),
    ):
        session = Session()
        for chunk in chunks:
            updates = await process_chunk(chunk, session)
            session = session.model_copy(update=updates)

        # Patient speech objective update should have been stripped
        assert patient_symptom not in session.soap_note.objective
