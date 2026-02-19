"""Download and parse ICD-10-CM code descriptions from CMS/CDC.

Downloads the official ICD-10-CM Code Descriptions zip from the CDC FTP,
extracts the order file, and writes a clean TSV (code\tdescription) to
backend/data/icd10cm_codes.tsv.

The order file is fixed-width:
  Cols 1-5:   Order number (right-justified, zero-filled)
  Col 6:      Blank
  Cols 7-13:  ICD-10-CM code (no periods)
  Col 14:     Blank
  Col 15:     Header flag (0=category header, 1=valid for coding)
  Col 16:     Blank
  Cols 17-76: Short description (60 chars)
  Col 77:     Blank
  Cols 78+:   Long description

Usage:
    python scripts/download_icd10.py
"""

import re
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

# CDC FTP URL for FY2026 ICD-10-CM code descriptions
CDC_URL = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026/icd10cm-Code%20Descriptions-2026.zip"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "backend" / "data"
OUTPUT_FILE = OUTPUT_DIR / "icd10cm_codes.tsv"


def _format_code(raw_code: str) -> str:
    """Insert dot after 3rd character: 'J069' → 'J06.9', 'A00' stays 'A00'."""
    raw_code = raw_code.strip().upper()
    if len(raw_code) > 3:
        return f"{raw_code[:3]}.{raw_code[3:]}"
    return raw_code


def _is_valid_icd10_raw(code: str) -> bool:
    """Check if raw code (no dots) looks like a valid ICD-10-CM code."""
    return bool(re.match(r"^[A-Z]\d[0-9A-Z]{0,5}$", code, re.IGNORECASE))


def _parse_order_file(text: str) -> dict[str, str]:
    """Parse the fixed-width ICD-10-CM order file."""
    codes: dict[str, str] = {}
    for line in text.splitlines():
        if len(line) < 17:
            continue
        raw_code = line[6:13].strip()
        if not raw_code or not _is_valid_icd10_raw(raw_code):
            continue
        # Long description starts at col 78
        long_desc = line[77:].strip() if len(line) > 77 else ""
        # Short description cols 17-76
        short_desc = line[16:76].strip()
        description = long_desc or short_desc
        if not description:
            continue
        code = _format_code(raw_code)
        codes[code] = description
    return codes


def _parse_flat_file(text: str) -> dict[str, str]:
    """Fallback parser for simpler 'CODE DESCRIPTION' format."""
    codes: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Try tab-separated first
        if "\t" in line:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                codes[_format_code(parts[0])] = parts[1].strip()
                continue
        # Space-separated: first token is code
        match = re.match(r"^([A-Z]\d[\dA-Z.]{1,6})\s+(.+)$", line, re.IGNORECASE)
        if match:
            codes[_format_code(match.group(1))] = match.group(2).strip()
    return codes


def download_and_parse() -> int:
    """Download ICD-10-CM zip, parse, write TSV. Returns code count."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading ICD-10-CM codes from CDC...")
    zip_path = OUTPUT_DIR / "icd10cm_codes.zip"
    try:
        urlretrieve(CDC_URL, zip_path)
    except Exception as exc:
        print(f"ERROR: Download failed: {exc}")
        print("You can manually download from:")
        print(f"  {CDC_URL}")
        print(f"  Extract and place the order file at: {OUTPUT_FILE}")
        return 0

    print(f"Extracting and parsing...")
    codes: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith(".txt"):
                with zf.open(name) as f:
                    text = f.read().decode("utf-8", errors="replace")
                # Try fixed-width order file format first
                parsed = _parse_order_file(text)
                if len(parsed) > 1000:  # order file has ~70K entries
                    codes.update(parsed)
                    print(f"  Parsed order file: {name} ({len(parsed)} codes)")
                else:
                    # Fallback to flat file
                    parsed = _parse_flat_file(text)
                    if parsed:
                        codes.update(parsed)
                        print(f"  Parsed flat file: {name} ({len(parsed)} codes)")

    if not codes:
        print("ERROR: No codes parsed from zip contents.")
        print(f"  Zip contents: {zf.namelist()}")
        return 0

    # Write TSV
    with open(OUTPUT_FILE, "w") as f:
        for code in sorted(codes):
            f.write(f"{code}\t{codes[code]}\n")

    # Clean up zip
    zip_path.unlink(missing_ok=True)

    print(f"Wrote {len(codes)} codes to {OUTPUT_FILE}")
    return len(codes)


if __name__ == "__main__":
    count = download_and_parse()
    if count == 0:
        sys.exit(1)
    print(f"Done. {count} ICD-10-CM codes ready.")
