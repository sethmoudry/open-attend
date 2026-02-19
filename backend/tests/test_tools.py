"""Tests for individual tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from models import (
    DiagnosisCode,
    FollowUpItem,
    InteractionFlag,
    LabFlag,
    LabReport,
    LabResult,
    Medication,
    PatientSummary,
    SOAPNote,
    Severity,
)
from tests.conftest import MOCK_RESPONSES


# ---------------------------------------------------------------------------
# extract_medications
# ---------------------------------------------------------------------------


class TestExtractMedications:
    @pytest.mark.asyncio
    async def test_basic(self, mock_llm):
        from tools import extract_medications

        result = await extract_medications("patient takes lisinopril 10mg daily")
        assert len(result) == 2
        assert all(isinstance(m, Medication) for m in result)
        assert result[0].name == "lisinopril"

    @pytest.mark.asyncio
    async def test_empty_text(self, mock_llm):
        from tools import extract_medications

        mock_llm.side_effect = None
        mock_llm.return_value = {"medications": []}
        result = await extract_medications("")
        assert result == []

    @pytest.mark.asyncio
    async def test_skips_nameless(self, mock_llm):
        from tools import extract_medications

        mock_llm.side_effect = None
        mock_llm.return_value = {
            "medications": [
                {"name": "aspirin", "dose": "81mg"},
                {"name": "", "dose": "10mg"},
                {"name": None},
            ]
        }
        result = await extract_medications("some text")
        assert len(result) == 1
        assert result[0].name == "aspirin"

    @pytest.mark.asyncio
    async def test_source_tagging(self, mock_llm):
        from tools import extract_medications

        result = await extract_medications("text", source="prescribed", chunk_id="c1")
        assert all(m.source == "prescribed" for m in result)
        assert all(m.chunk_id == "c1" for m in result)


# ---------------------------------------------------------------------------
# check_interactions
# ---------------------------------------------------------------------------


class TestCheckInteractions:
    @pytest.mark.asyncio
    async def test_single_med_returns_empty(self, mock_llm):
        from tools import check_interactions

        result = await check_interactions([Medication(name="aspirin")])
        assert result == []
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_found(self, mock_llm):
        from tools import check_interactions

        meds = [
            Medication(name="lisinopril", dose="10mg"),
            Medication(name="ibuprofen", dose="400mg"),
        ]
        result = await check_interactions(meds)
        assert len(result) == 1
        assert isinstance(result[0], InteractionFlag)
        assert result[0].severity == Severity.MODERATE

    @pytest.mark.asyncio
    async def test_invalid_severity_fallback(self, mock_llm):
        from tools import check_interactions

        mock_llm.side_effect = None
        mock_llm.return_value = {
            "interactions": [
                {
                    "drug_a": "a",
                    "drug_b": "b",
                    "severity": "bogus",
                    "mechanism": "test",
                }
            ]
        }
        meds = [Medication(name="a"), Medication(name="b")]
        result = await check_interactions(meds)
        assert result[0].severity == Severity.LOW


# ---------------------------------------------------------------------------
# build_differential
# ---------------------------------------------------------------------------


class TestBuildDifferential:
    @pytest.mark.asyncio
    async def test_empty_symptoms(self, mock_llm):
        from tools import build_differential

        result = await build_differential([], ["family history"])
        assert result == []
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_list(self, mock_llm):
        from tools import build_differential

        result = await build_differential(["headache"], ["hypertension"])
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(d, str) for d in result)


# ---------------------------------------------------------------------------
# SOAP drafting
# ---------------------------------------------------------------------------


class TestSOAPDrafting:
    @pytest.mark.asyncio
    async def test_draft_soap_section(self, mock_llm):
        from tools import draft_soap_section

        result = await draft_soap_section("Subjective", {"symptoms": ["headache"]})
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_draft_full_soap(self, mock_llm):
        from tools import draft_full_soap

        result = await draft_full_soap(
            symptoms=["headache"],
            medications=[Medication(name="ibuprofen")],
            exam_findings=["BP 148/92"],
            differential=["tension headache"],
            orders=[],
            allergies=[],
            family_history=[],
        )
        assert isinstance(result, SOAPNote)
        assert result.subjective
        assert result.objective
        assert result.assessment
        assert result.plan


# ---------------------------------------------------------------------------
# Red flag detection
# ---------------------------------------------------------------------------


class TestDetectRedFlags:
    @pytest.mark.asyncio
    async def test_none_found(self, mock_llm):
        from tools import detect_red_flags

        result = await detect_red_flags("mild headache", symptoms=["headache"])
        assert result == []

    @pytest.mark.asyncio
    async def test_found(self, mock_llm):
        from tools import detect_red_flags

        mock_llm.side_effect = None
        mock_llm.return_value = MOCK_RESPONSES["red_flags_found"]
        result = await detect_red_flags(
            "worst headache of my life", symptoms=["severe headache"]
        )
        assert len(result) == 1
        assert "RED FLAG" in result[0].message


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------


class TestCodeExtraction:
    @pytest.mark.asyncio
    async def test_icd10_empty_assessment(self, mock_llm):
        from tools import extract_icd10_codes

        result = await extract_icd10_codes("")
        assert result == []
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_icd10_filters_low_confidence(self, mock_llm):
        from tools import extract_icd10_codes

        result = await extract_icd10_codes("Migraine with aura, hypertension")
        # G43.1 (0.92) should pass, I10 (0.3) should be filtered
        assert len(result) == 1
        assert result[0].code == "G43.1"

    @pytest.mark.asyncio
    async def test_cpt_codes(self, mock_llm):
        from tools import extract_cpt_codes

        result = await extract_cpt_codes("Follow up in 4 weeks")
        assert len(result) == 1
        assert isinstance(result[0], DiagnosisCode)


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------


class TestFollowUps:
    @pytest.mark.asyncio
    async def test_extract_follow_ups(self, mock_llm):
        from tools import extract_follow_ups

        result = await extract_follow_ups(plan="See neurology in 4 weeks")
        assert len(result) == 1
        assert isinstance(result[0], FollowUpItem)
        assert result[0].action == "Neurology follow-up"


# ---------------------------------------------------------------------------
# format_labs_for_soap (pure function, no mock needed)
# ---------------------------------------------------------------------------


class TestFormatLabs:
    def test_empty_results(self):
        from tools import format_labs_for_soap

        report = LabReport(lab_name="CBC", results=[])
        assert format_labs_for_soap(report) == ""

    def test_normal_results(self):
        from tools import format_labs_for_soap

        report = LabReport(
            lab_name="CBC",
            date="2024-01-15",
            results=[
                LabResult(test="WBC", value=7.5, unit="K/uL", flag=LabFlag.NORMAL),
            ],
        )
        result = format_labs_for_soap(report)
        assert "WBC" in result
        assert "7.5" in result
        assert "CBC" in result

    def test_abnormal_flags(self):
        from tools import format_labs_for_soap

        report = LabReport(
            lab_name="BMP",
            results=[
                LabResult(test="Glucose", value=250.0, unit="mg/dL", flag=LabFlag.HIGH),
                LabResult(test="K", value=2.8, unit="mEq/L", flag=LabFlag.LOW),
                LabResult(test="Na", value=110.0, unit="mEq/L", flag=LabFlag.CRITICAL),
            ],
        )
        result = format_labs_for_soap(report)
        assert "(H)" in result
        assert "(L)" in result
        assert "(CRITICAL)" in result
