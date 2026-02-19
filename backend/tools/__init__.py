"""Tool functions for the Open Attend orchestrator.

Re-exports all tool functions from domain-specific submodules so consumers
can continue to use ``from tools import extract_medications``.
"""

from tools.medications import extract_medications, check_interactions
from tools.diagnosis import build_differential
from tools.soap import draft_soap_section, draft_full_soap, draft_soap_from_transcript, draft_soap_from_transcript_sectional, verify_soap_note, generate_aci_note
from tools.coding import extract_icd10_codes, extract_cpt_codes, CONFIDENCE_THRESHOLD
from tools.alerts import detect_red_flags, detect_mental_health_signals, generate_alerts, check_lab_alerts
from tools.orders import extract_orders, extract_follow_ups
from tools.patient import generate_patient_summary
from tools.labs import format_labs_for_soap, extract_lab_values

__all__ = [
    "extract_medications",
    "check_interactions",
    "build_differential",
    "draft_soap_section",
    "draft_full_soap",
    "draft_soap_from_transcript",
    "draft_soap_from_transcript_sectional",
    "verify_soap_note",
    "generate_aci_note",
    "extract_icd10_codes",
    "extract_cpt_codes",
    "CONFIDENCE_THRESHOLD",
    "detect_red_flags",
    "detect_mental_health_signals",
    "generate_alerts",
    "check_lab_alerts",
    "extract_orders",
    "extract_follow_ups",
    "generate_patient_summary",
    "format_labs_for_soap",
    "extract_lab_values",
]
