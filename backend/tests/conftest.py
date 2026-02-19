"""Shared fixtures for Scribe backend tests."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import (
    Medication,
    Session,
    Speaker,
    TranscriptChunk,
    VisitType,
)
from session import SessionStore


# ---------------------------------------------------------------------------
# Mock LLM responses (keyword-dispatched)
# ---------------------------------------------------------------------------

MOCK_RESPONSES = {
    "medications": {
        "medications": [
            {"name": "lisinopril", "dose": "10mg", "frequency": "daily"},
            {"name": "metformin", "dose": "500mg", "frequency": "twice daily"},
        ]
    },
    "interactions": {
        "interactions": [
            {
                "drug_a": "lisinopril",
                "drug_b": "ibuprofen",
                "severity": "moderate",
                "mechanism": "NSAIDs may reduce antihypertensive effect",
                "recommendation": "Monitor blood pressure closely",
            }
        ]
    },
    "differential": {
        "differential": [
            "Tension-type headache",
            "Hypertensive headache",
            "Medication overuse headache",
        ]
    },
    "red_flags": {"red_flags": []},
    "red_flags_found": {
        "red_flags": [
            {
                "finding": "Sudden severe headache",
                "urgency": "critical",
                "reasoning": "Could indicate subarachnoid hemorrhage",
            }
        ]
    },
    "mental_health": {
        "signals": [
            {
                "signal": "Depressed mood",
                "severity": "medium",
                "recommended_screen": "PHQ-9",
            }
        ]
    },
    "soap_section": {"text": "Patient presents with persistent headache for 3 days."},
    "chunk_analysis": {
        "symptoms": ["headache", "dizziness"],
        "allergies": [],
        "family_history": ["hypertension"],
        "exam_findings": [],
        "mental_health_signals": [],
        "alerts": [],
        "orders": [],
        "medications": [],
        "medication_source": "patient_reported",
        "soap_routing": "subjective",
        "soap_updates": {
            "subjective": "Headache x3 days, dizziness on standing.",
        },
    },
    "chunk_analysis_doctor": {
        "symptoms": [],
        "allergies": [],
        "family_history": [],
        "exam_findings": ["BP 148/92"],
        "mental_health_signals": [],
        "alerts": [],
        "orders": [],
        "medications": [],
        "medication_source": "prescribed",
        "soap_routing": "objective",
        "soap_updates": {
            "objective": "BP 148/92, HR 78.",
        },
    },
    "icd10": {
        "codes": [
            {"code": "G43.1", "description": "Migraine with aura", "confidence": 0.92},
            {"code": "I10", "description": "Essential hypertension", "confidence": 0.3},
        ]
    },
    "cpt": {
        "codes": [
            {"code": "99214", "description": "Office visit, established", "confidence": 0.85},
        ]
    },
    "follow_ups": {
        "follow_ups": [
            {
                "action": "Neurology follow-up",
                "type": "referral",
                "timeframe": "4 weeks",
                "details": "For migraine with new aura",
            }
        ]
    },
    "patient_summary": {
        "visit_summary": "You came in for a headache.",
        "new_medications": ["Sumatriptan 50mg as needed"],
        "follow_up_steps": ["See neurologist in 4 weeks"],
        "when_to_seek_care": "If headache is the worst of your life",
    },
    "orders": {
        "orders": [
            {"type": "lab", "details": "CBC with differential", "urgency": "routine"}
        ]
    },
    "role_assignment": {
        "assignments": [
            {"speaker_id": "spk_0", "role": "doctor", "confidence": 0.95, "reasoning": "Uses medical terminology"},
            {"speaker_id": "spk_1", "role": "patient", "confidence": 0.92, "reasoning": "Describes symptoms"},
        ]
    },
    "default": {"_raw": "mock response"},
}


def _dispatch_mock(prompt: str, **kwargs) -> dict:
    """Match prompt keywords to canned responses.

    Order matters — more specific patterns first to avoid false matches
    (e.g. "following" matching "follow").
    """
    p = prompt.lower()
    # Chunk analysis prompt has "=== CURRENT CONTEXT ===" — match first
    if "current context" in p:
        return MOCK_RESPONSES["chunk_analysis"]
    # SOAP section drafts contain data with other keywords — match early
    if "medical scribe" in p or "draft the" in p:
        return MOCK_RESPONSES["soap_section"]
    if "icd" in p:
        return MOCK_RESPONSES["icd10"]
    if "cpt" in p:
        return MOCK_RESPONSES["cpt"]
    if "interaction" in p:
        return MOCK_RESPONSES["interactions"]
    if "clinical pharmacist" in p:
        return MOCK_RESPONSES["medications"]
    if "differential" in p:
        return MOCK_RESPONSES["differential"]
    if "red flag" in p:
        return MOCK_RESPONSES["red_flags"]
    if "mental" in p:
        return MOCK_RESPONSES["mental_health"]
    if "follow-up" in p or "follow up" in p:
        return MOCK_RESPONSES["follow_ups"]
    if "summary" in p and "patient" in p:
        return MOCK_RESPONSES["patient_summary"]
    if "order" in p:
        return MOCK_RESPONSES["orders"]
    if "role" in p or "speaker" in p:
        return MOCK_RESPONSES["role_assignment"]
    if "medication" in p:
        return MOCK_RESPONSES["medications"]
    if "chunk" in p or "transcript" in p:
        return MOCK_RESPONSES["chunk_analysis"]
    return MOCK_RESPONSES["default"]


@pytest.fixture
def mock_llm():
    """Patch LLM calls with keyword-dispatched mock responses.

    We patch at every import site since modules use
    ``from llm import call_medgemma_json`` which creates local bindings.
    """
    mock_json = AsyncMock(side_effect=_dispatch_mock)
    mock_raw = AsyncMock(return_value='{"_raw": "mock"}')
    with (
        patch("llm.call_medgemma_json", mock_json),
        patch("llm.call_medgemma", mock_raw),
        patch("tools.call_medgemma_json", mock_json),
        patch("orchestrator.call_medgemma_json", mock_json),
        patch("role_assignment.call_medgemma_json", mock_json),
    ):
        yield mock_json


@pytest_asyncio.fixture
async def session_store():
    """Fresh session store for each test."""
    s = SessionStore()
    await s.start()
    yield s
    await s.stop()


@pytest.fixture
def sample_chunk():
    """A single patient transcript chunk."""
    return TranscriptChunk(
        timestamp_start=0.0,
        timestamp_end=12.0,
        speaker=Speaker.PATIENT,
        text=(
            "I've been having a persistent headache for the past three days. "
            "It's about a 7 out of 10. I've been taking ibuprofen 400mg every "
            "6 hours but it's not helping much. I also feel dizzy when I stand up."
        ),
    )


@pytest.fixture
def sample_session(sample_chunk):
    """A session with a few transcript chunks pre-loaded."""
    chunks = [
        TranscriptChunk(
            timestamp_start=0.0,
            timestamp_end=10.0,
            speaker=Speaker.DOCTOR,
            text="Good afternoon. Can you tell me what brings you in today?",
        ),
        sample_chunk,
        TranscriptChunk(
            timestamp_start=12.0,
            timestamp_end=24.0,
            speaker=Speaker.DOCTOR,
            text="I see. Any history of migraines? Are you on any medications?",
        ),
    ]
    return Session(
        visit_type=VisitType.URGENT,
        transcript_chunks=chunks,
        medications=[
            Medication(name="lisinopril", dose="10mg", frequency="daily"),
        ],
    )
