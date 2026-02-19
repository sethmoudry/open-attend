"""ICD-10-CM lookup table and code validation.

Lazy-loads 98K+ ICD-10-CM codes from a TSV file (downloaded via
scripts/download_icd10.py). Provides validation, canonical description
replacement, and fuzzy matching for near-miss codes.

CPT codes are AMA-copyrighted — we only validate format (5-char pattern).
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).resolve().parent / "data" / "icd10cm_codes.tsv"

# Lazy singleton
_icd10_codes: dict[str, str] | None = None


def load_icd10_codes() -> dict[str, str]:
    """Load ICD-10-CM codes from TSV. Returns code→description dict.

    Thread-safe for reads after initial load. Logs warning and returns
    empty dict if file not found (graceful degradation).
    """
    global _icd10_codes
    if _icd10_codes is not None:
        return _icd10_codes

    if not _DATA_FILE.exists():
        logger.warning(
            "ICD-10-CM lookup table not found at %s. "
            "Run 'python scripts/download_icd10.py' to download. "
            "Code validation will be skipped.",
            _DATA_FILE,
        )
        _icd10_codes = {}
        return _icd10_codes

    codes: dict[str, str] = {}
    with open(_DATA_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            code, description = line.split("\t", 1)
            codes[code.strip().upper()] = description.strip()

    _icd10_codes = codes
    logger.info("Loaded %d ICD-10-CM codes from %s", len(codes), _DATA_FILE.name)
    return _icd10_codes


def _normalize_icd10(code: str) -> str:
    """Normalize an ICD-10-CM code: uppercase, insert dot if missing."""
    code = code.strip().upper().replace(" ", "")
    # Remove dot for uniform processing, then re-insert
    raw = code.replace(".", "")
    if len(raw) > 3:
        return f"{raw[:3]}.{raw[3:]}"
    return raw


def validate_icd10(code: str) -> tuple[bool, str | None]:
    """Check if an ICD-10-CM code exists in the lookup table.

    Returns (is_valid, canonical_description).
    If lookup table isn't loaded, returns (True, None) — skip validation.
    """
    codes = load_icd10_codes()
    if not codes:
        return True, None  # no table = skip validation

    normalized = _normalize_icd10(code)
    if normalized in codes:
        return True, codes[normalized]
    return False, None


def fuzzy_match_icd10(code: str) -> tuple[str, str] | None:
    """Try common corrections for near-miss ICD-10-CM codes.

    Attempts:
    1. Normalize (add/fix dot)
    2. Strip trailing zero (e.g., J06.90 → J06.9)
    3. Try parent code (e.g., J06.9 → J06)
    4. Add trailing 9 for unspecified (e.g., J06 → J06.9)

    Returns (corrected_code, description) or None.
    """
    codes = load_icd10_codes()
    if not codes:
        return None

    normalized = _normalize_icd10(code)

    # Already valid
    if normalized in codes:
        return normalized, codes[normalized]

    # Strip trailing zero: J06.90 → J06.9
    if normalized.endswith("0") and len(normalized) > 4:
        trimmed = normalized[:-1]
        if trimmed in codes:
            return trimmed, codes[trimmed]

    # Try parent code: J06.9 → J06
    if "." in normalized:
        parent = normalized.split(".")[0]
        if parent in codes:
            return parent, codes[parent]

    # Add unspecified suffix: J06 → J06.9
    unspec = f"{normalized}.9"
    if unspec in codes:
        return unspec, codes[unspec]

    # Try adding trailing 9 to subcategory: J06.1 → J06.19
    with_nine = f"{normalized}9"
    if with_nine in codes:
        return with_nine, codes[with_nine]

    return None


# CPT format: 5 digits (e.g., 99214), or 4 digits + letter (e.g., 0213T)
_CPT_PATTERN = re.compile(r"^\d{4}[\dA-Z]$|^\d{5}$", re.IGNORECASE)


def validate_cpt_format(code: str) -> bool:
    """Validate CPT code format (5-char alphanumeric).

    CPT is AMA-copyrighted so we can't validate against a lookup table.
    We only check the format matches known CPT patterns.
    """
    return bool(_CPT_PATTERN.match(code.strip()))
