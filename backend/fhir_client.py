"""FHIR R4 client for patient data import/export.

Targets the SMART Health IT public sandbox (https://r4.smarthealthit.org)
by default. All functions degrade gracefully — errors return empty results,
never raise.
"""

import asyncio
import base64
import logging
from datetime import date, datetime, timezone

import httpx

from models import FHIRAllergy, FHIRImportResult, FHIRPatient, Medication

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://r4.smarthealthit.org"
_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _age_from_birthdate(birth_date_str: str | None) -> int | None:
    """Calculate age in years from an ISO date string (YYYY-MM-DD)."""
    if not birth_date_str:
        return None
    try:
        birth = date.fromisoformat(birth_date_str)
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except (ValueError, TypeError):
        return None


def _parse_patient_resource(resource: dict) -> FHIRPatient:
    """Map a FHIR Patient resource dict to FHIRPatient."""
    names = resource.get("name", [])
    full_name = ""
    if names:
        first_name_entry = names[0]
        given = first_name_entry.get("given", [])
        family = first_name_entry.get("family", "")
        given_str = " ".join(given) if given else ""
        full_name = f"{given_str} {family}".strip()

    birth_date_str = resource.get("birthDate")
    return FHIRPatient(
        id=resource.get("id", ""),
        name=full_name or "Unknown",
        birth_date=birth_date_str,
        age=_age_from_birthdate(birth_date_str),
        gender=resource.get("gender"),
    )


def _entries_from_bundle(bundle: dict) -> list[dict]:
    """Extract resource dicts from a FHIR Bundle response."""
    return [e["resource"] for e in bundle.get("entry", []) if "resource" in e]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def search_patients(
    query: str,
    base_url: str = DEFAULT_BASE_URL,
) -> list[FHIRPatient]:
    """Search patients by name. Returns up to 20 matches."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/Patient",
                params={"name": query, "_count": 20},
            )
            resp.raise_for_status()
            bundle = resp.json()
            return [_parse_patient_resource(r) for r in _entries_from_bundle(bundle)]
    except Exception:
        logger.exception("search_patients failed for query=%s", query)
        return []


async def get_patient(
    patient_id: str,
    base_url: str = DEFAULT_BASE_URL,
) -> FHIRPatient:
    """Fetch a single Patient resource by ID."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{base_url}/Patient/{patient_id}")
            resp.raise_for_status()
            return _parse_patient_resource(resp.json())
    except Exception:
        logger.exception("get_patient failed for id=%s", patient_id)
        return FHIRPatient(id=patient_id, name="Unknown")


async def get_medications(
    patient_id: str,
    base_url: str = DEFAULT_BASE_URL,
) -> list[Medication]:
    """Fetch active MedicationRequest resources for a patient."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/MedicationRequest",
                params={"patient": patient_id, "status": "active", "_count": 50},
            )
            resp.raise_for_status()
            bundle = resp.json()

        meds: list[Medication] = []
        for resource in _entries_from_bundle(bundle):
            # Medication name: prefer text, fall back to first coding display
            med_concept = resource.get("medicationCodeableConcept", {})
            name = med_concept.get("text")
            if not name:
                codings = med_concept.get("coding", [])
                name = codings[0].get("display", "Unknown") if codings else "Unknown"

            # Dosage instruction text
            dosage_instructions = resource.get("dosageInstruction", [])
            dose = dosage_instructions[0].get("text") if dosage_instructions else None

            meds.append(Medication(name=name, dose=dose, source="fhir_import"))
        return meds
    except Exception:
        logger.exception("get_medications failed for patient=%s", patient_id)
        return []


async def get_allergies(
    patient_id: str,
    base_url: str = DEFAULT_BASE_URL,
) -> list[FHIRAllergy]:
    """Fetch AllergyIntolerance resources for a patient."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/AllergyIntolerance",
                params={"patient": patient_id, "_count": 50},
            )
            resp.raise_for_status()
            bundle = resp.json()

        allergies: list[FHIRAllergy] = []
        for resource in _entries_from_bundle(bundle):
            code = resource.get("code", {})
            codings = code.get("coding", [])
            substance = codings[0].get("display") if codings else None
            if not substance:
                substance = code.get("text", "Unknown")

            criticality = resource.get("criticality")

            # First reaction manifestation display, if present
            reaction: str | None = None
            reactions = resource.get("reaction", [])
            if reactions:
                manifestations = reactions[0].get("manifestation", [])
                if manifestations:
                    m_codings = manifestations[0].get("coding", [])
                    if m_codings:
                        reaction = m_codings[0].get("display")

            allergies.append(FHIRAllergy(
                substance=substance,
                criticality=criticality,
                reaction=reaction,
            ))
        return allergies
    except Exception:
        logger.exception("get_allergies failed for patient=%s", patient_id)
        return []


async def get_conditions(
    patient_id: str,
    base_url: str = DEFAULT_BASE_URL,
) -> list[str]:
    """Fetch active Condition display names for a patient."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{base_url}/Condition",
                params={"patient": patient_id, "clinical-status": "active", "_count": 50},
            )
            resp.raise_for_status()
            bundle = resp.json()

        conditions: list[str] = []
        for resource in _entries_from_bundle(bundle):
            code = resource.get("code", {})
            codings = code.get("coding", [])
            display = codings[0].get("display") if codings else None
            if not display:
                display = code.get("text")
            if display:
                conditions.append(display)
        return conditions
    except Exception:
        logger.exception("get_conditions failed for patient=%s", patient_id)
        return []


async def import_patient_context(
    patient_id: str,
    base_url: str = DEFAULT_BASE_URL,
) -> FHIRImportResult:
    """Fetch patient demographics, meds, allergies, and conditions in parallel."""
    patient, meds, allergies, conditions = await asyncio.gather(
        get_patient(patient_id, base_url),
        get_medications(patient_id, base_url),
        get_allergies(patient_id, base_url),
        get_conditions(patient_id, base_url),
    )
    return FHIRImportResult(
        patient=patient,
        medications=meds,
        allergies=allergies,
        conditions=conditions,
    )


async def export_note(
    patient_id: str,
    soap_text: str,
    session_id: str,
    base_url: str = DEFAULT_BASE_URL,
) -> dict:
    """Export a SOAP note as a FHIR DocumentReference (Progress note)."""
    encoded = base64.b64encode(soap_text.encode("utf-8")).decode("ascii")
    document_reference = {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Progress note",
                }
            ]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": datetime.now(timezone.utc).isoformat(),
        "description": f"SOAP note from session {session_id}",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": encoded,
                }
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{base_url}/DocumentReference",
                json=document_reference,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        logger.exception("export_note failed for patient=%s session=%s", patient_id, session_id)
        return {"error": "Failed to export note", "patient_id": patient_id, "session_id": session_id}
