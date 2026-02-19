"""ICD-10 and CPT code extraction with lookup table validation."""

import logging

import httpx

from agents import CPT_EXTRACTION_PROMPT, ICD10_EXTRACTION_PROMPT
from code_lookup import fuzzy_match_icd10, validate_cpt_format, validate_icd10
from llm import call_coding_llm_json
from models import DiagnosisCode

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.5  # minimum confidence for ICD-10/CPT codes


async def extract_icd10_codes(assessment: str) -> list[DiagnosisCode]:
    """Extract ICD-10 codes from assessment text, validated against CMS lookup."""
    if not assessment or not assessment.strip():
        return []

    prompt = ICD10_EXTRACTION_PROMPT.format(assessment=assessment)
    try:
        result = await call_coding_llm_json(prompt)
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("ICD-10 extraction failed")
        return []

    codes: list[DiagnosisCode] = []
    for entry in result.get("codes", []):
        code_val = entry.get("code", "")
        if not code_val:
            continue
        confidence = float(entry.get("confidence", 0.0))
        if confidence <= CONFIDENCE_THRESHOLD:
            continue

        # Validate against ICD-10-CM lookup table
        valid, canonical_desc = validate_icd10(code_val)
        if valid:
            codes.append(
                DiagnosisCode(
                    code=code_val,
                    description=canonical_desc or entry.get("description", ""),
                    confidence=confidence,
                    source_section="assessment",
                )
            )
            continue

        # Try fuzzy matching for near-miss codes
        match = fuzzy_match_icd10(code_val)
        if match:
            corrected_code, corrected_desc = match
            logger.info("ICD-10 fuzzy match: %s → %s", code_val, corrected_code)
            codes.append(
                DiagnosisCode(
                    code=corrected_code,
                    description=corrected_desc,
                    confidence=round(confidence * 0.9, 4),  # slight penalty
                    source_section="assessment",
                )
            )
        else:
            logger.warning("Dropping hallucinated ICD-10 code: %s", code_val)

    return codes


async def extract_cpt_codes(
    plan: str, orders: list[dict] | None = None
) -> list[DiagnosisCode]:
    """Extract CPT codes from plan text, with format validation."""
    if not plan or not plan.strip():
        return []

    orders_str = "None"
    if orders:
        orders_str = ", ".join(
            f"{o.get('type', 'other')}: {o.get('details', '')}" for o in orders
        )

    prompt = CPT_EXTRACTION_PROMPT.format(plan=plan, orders=orders_str)
    try:
        result = await call_coding_llm_json(prompt)
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("CPT extraction failed")
        return []

    codes: list[DiagnosisCode] = []
    for entry in result.get("codes", []):
        code_val = entry.get("code", "")
        if not code_val:
            continue
        confidence = float(entry.get("confidence", 0.0))
        if confidence <= CONFIDENCE_THRESHOLD:
            continue

        # Validate CPT format (5-char alphanumeric)
        if not validate_cpt_format(code_val):
            logger.warning("Dropping invalid CPT format: %s", code_val)
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
