"""Download and prepare evaluation datasets: Fareez OSCE + ACI-Bench.

Usage:
    python eval/download_data.py
"""

import csv as csv_mod
import glob
import io
import json
import logging
import os
import random
import re
import sys
import zipfile

import requests

# Allow running as script from project root
sys.path.insert(0, os.path.dirname(__file__))
from config import (
    ACI_BENCH_FIGSHARE_ARTICLE_ID,
    DATA_DIR,
    FAREEZ_ARTICLE_ID,
    FAREEZ_COLLECTION_ID,
    FAREEZ_SPECIALTIES,
    FAREEZ_SUBSET_SIZE,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

FAREEZ_DIR = os.path.join(DATA_DIR, "fareez")
ACI_DIR = os.path.join(DATA_DIR, "aci_bench")


# ---------------------------------------------------------------------------
# Fareez OSCE dataset
# ---------------------------------------------------------------------------


def _resolve_fareez_article_id() -> int:
    """Try known article ID first. If 404, enumerate collection to find it."""
    url = f"https://api.figshare.com/v2/articles/{FAREEZ_ARTICLE_ID}/files"
    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
        return FAREEZ_ARTICLE_ID

    logger.info(
        "  Article %d not found, enumerating collection %d...",
        FAREEZ_ARTICLE_ID,
        FAREEZ_COLLECTION_ID,
    )
    resp = requests.get(
        f"https://api.figshare.com/v2/collections/{FAREEZ_COLLECTION_ID}/articles",
        timeout=30,
    )
    resp.raise_for_status()
    articles = resp.json()
    for art in articles:
        art_id = art["id"]
        files_resp = requests.get(
            f"https://api.figshare.com/v2/articles/{art_id}/files", timeout=30
        )
        files = files_resp.json()
        if any("Data.zip" in f.get("name", "") for f in files):
            logger.info("  Found Data.zip in article %d", art_id)
            return art_id

    raise RuntimeError("Could not find Fareez Data.zip in Figshare collection")


def _classify_specialty(filename: str) -> str | None:
    """Extract specialty code from Fareez filename like 'RES_001.wav'."""
    for spec in FAREEZ_SPECIALTIES:
        if filename.upper().startswith(spec):
            return spec
    return None


def download_fareez():
    """Download Fareez OSCE dataset and select a specialty-balanced subset."""
    manifest_path = os.path.join(FAREEZ_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        logger.info("[Fareez] Already downloaded, loading manifest...")
        with open(manifest_path) as f:
            return json.load(f)

    os.makedirs(FAREEZ_DIR, exist_ok=True)

    logger.info("[Fareez] Resolving article ID...")
    article_id = _resolve_fareez_article_id()

    logger.info("[Fareez] Fetching file list from article %d...", article_id)
    resp = requests.get(
        f"https://api.figshare.com/v2/articles/{article_id}/files", timeout=30
    )
    resp.raise_for_status()
    files = resp.json()

    # Find the Data.zip file
    zip_file = None
    for f in files:
        if "Data.zip" in f.get("name", ""):
            zip_file = f
            break

    if zip_file is None:
        raise RuntimeError(f"Data.zip not found in article {article_id}")

    download_url = zip_file["download_url"]
    logger.info("[Fareez] Downloading %s (%.1f MB)...", zip_file["name"], zip_file.get("size", 0) / 1e6)
    resp = requests.get(download_url, timeout=300)
    resp.raise_for_status()

    logger.info("[Fareez] Extracting...")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))

    # Find audio files and transcripts
    audio_files = []
    transcript_files = {}

    for name in zf.namelist():
        basename = os.path.basename(name)
        if not basename:
            continue
        if basename.lower().endswith((".wav", ".mp3", ".flac")):
            audio_files.append(name)
        elif basename.lower().endswith(".txt"):
            # Map base name (without extension) to transcript path
            key = os.path.splitext(basename)[0]
            transcript_files[key] = name

    logger.info("[Fareez] Found %d audio files, %d transcripts", len(audio_files), len(transcript_files))

    # Group by specialty
    by_specialty: dict[str, list[dict]] = {}
    for audio_path in audio_files:
        basename = os.path.basename(audio_path)
        file_id = os.path.splitext(basename)[0]
        spec = _classify_specialty(basename)
        if spec is None:
            spec = "OTHER"

        entry = {
            "id": file_id,
            "audio_zip_path": audio_path,
            "specialty": spec,
        }

        # Look for matching transcript
        if file_id in transcript_files:
            entry["transcript_zip_path"] = transcript_files[file_id]

        by_specialty.setdefault(spec, []).append(entry)

    logger.info("[Fareez] Specialty distribution: %s", {k: len(v) for k, v in by_specialty.items()})

    # Proportional sampling: use all of small specialties, fill rest from RES
    random.seed(42)
    selected = []
    for spec in ["DER", "CAR", "GAS", "MSK"]:  # smallest first
        available = by_specialty.get(spec, [])
        take = min(5, len(available))
        selected.extend(random.sample(available, take))

    remaining = FAREEZ_SUBSET_SIZE - len(selected)
    if remaining > 0 and "RES" in by_specialty:
        selected.extend(random.sample(by_specialty["RES"], min(remaining, len(by_specialty["RES"]))))

    logger.info(
        "[Fareez] Selected %d files: %s",
        len(selected),
        {s: sum(1 for e in selected if e["specialty"] == s) for s in FAREEZ_SPECIALTIES},
    )

    # Extract selected files to disk
    manifest = []
    for entry in selected:
        # Extract audio
        audio_out = os.path.join(FAREEZ_DIR, "audio", f"{entry['id']}.wav")
        os.makedirs(os.path.dirname(audio_out), exist_ok=True)
        with open(audio_out, "wb") as f:
            f.write(zf.read(entry["audio_zip_path"]))

        item = {
            "id": entry["id"],
            "audio_path": audio_out,
            "specialty": entry["specialty"],
        }

        # Extract transcript if available
        if "transcript_zip_path" in entry:
            transcript_text = zf.read(entry["transcript_zip_path"]).decode("utf-8", errors="replace")
            transcript_out = os.path.join(FAREEZ_DIR, "transcripts", f"{entry['id']}.txt")
            os.makedirs(os.path.dirname(transcript_out), exist_ok=True)
            with open(transcript_out, "w") as f:
                f.write(transcript_text)
            item["transcript_path"] = transcript_out
            item["reference_text"] = transcript_text

        manifest.append(item)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("[Fareez] Manifest saved: %s (%d entries)", manifest_path, len(manifest))
    return manifest


# ---------------------------------------------------------------------------
# ACI-Bench dataset
# ---------------------------------------------------------------------------

SECTION_HEADERS = [
    r"HISTORY OF PRESENT ILLNESS",
    r"PHYSICAL EXAM(?:INATION)?",
    r"RESULTS",
    r"ASSESSMENT AND PLAN",
]
SECTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(" + "|".join(SECTION_HEADERS) + r")\s*:?\s*\n",
    re.IGNORECASE,
)


def _parse_aci_sections(note_text: str, note_id: str = "") -> dict[str, str]:
    """Parse an ACI-Bench note into 4 sections."""
    sections: dict[str, str] = {}

    # Split on section headers
    parts = SECTION_PATTERN.split(note_text)

    # parts alternates: [preamble, header1, content1, header2, content2, ...]
    i = 1  # skip preamble
    while i < len(parts) - 1:
        header = parts[i].strip().upper()
        content = parts[i + 1].strip()

        if "HISTORY" in header:
            sections["history_of_present_illness"] = content
        elif "PHYSICAL" in header:
            sections["physical_examination"] = content
        elif "RESULTS" in header:
            sections["results"] = content
        elif "ASSESSMENT" in header:
            sections["assessment_and_plan"] = content

        i += 2

    if len(sections) != 4:
        logger.warning(
            "Note %s parsed into %d sections (expected 4): %s",
            note_id,
            len(sections),
            list(sections.keys()),
        )

    return sections


def download_aci_bench():
    """Download ACI-Bench dataset from Figshare."""
    manifest_path = os.path.join(ACI_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        logger.info("[ACI-Bench] Already downloaded, loading manifest...")
        with open(manifest_path) as f:
            return json.load(f)

    os.makedirs(ACI_DIR, exist_ok=True)

    logger.info("[ACI-Bench] Fetching file list from article %d...", ACI_BENCH_FIGSHARE_ARTICLE_ID)
    resp = requests.get(
        f"https://api.figshare.com/v2/articles/{ACI_BENCH_FIGSHARE_ARTICLE_ID}/files",
        timeout=30,
    )
    resp.raise_for_status()
    files = resp.json()

    # Download all JSON/CSV files
    manifest = []
    encounter_id = 0

    # Download and extract the zip archive
    zip_file = None
    for file_info in files:
        fname = file_info.get("name", "")
        if fname.endswith(".zip"):
            zip_file = file_info
            break

    if zip_file is None:
        raise RuntimeError(
            f"No .zip file found in Figshare article {ACI_BENCH_FIGSHARE_ARTICLE_ID}"
        )

    logger.info(
        "[ACI-Bench] Downloading %s (%.1f MB)...",
        zip_file["name"],
        zip_file.get("size", 0) / 1e6,
    )
    dl_resp = requests.get(zip_file["download_url"], timeout=300)
    dl_resp.raise_for_status()

    logger.info("[ACI-Bench] Extracting to %s...", ACI_DIR)
    zf = zipfile.ZipFile(io.BytesIO(dl_resp.content))
    zf.extractall(ACI_DIR)

    # Iterate over all extracted CSV and JSON files
    for fpath in sorted(glob.glob(os.path.join(ACI_DIR, "**/*"), recursive=True)):
        if not os.path.isfile(fpath):
            continue

        fname = os.path.basename(fpath)
        ext = os.path.splitext(fname)[1].lower()

        if ext == ".csv":
            logger.info("[ACI-Bench] Parsing CSV %s...", fname)
            try:
                with open(fpath, newline="", encoding="utf-8") as csvf:
                    reader = csv_mod.DictReader(csvf)
                    for row in reader:
                        dialogue = row.get("dialogue", row.get("input", row.get("src", "")))
                        note = row.get("note", row.get("output", row.get("tgt", "")))

                        if not dialogue or not note:
                            continue

                        enc_id = f"aci_{encounter_id:04d}"
                        gold_sections = _parse_aci_sections(note, enc_id)

                        manifest.append({
                            "id": enc_id,
                            "source_file": fname,
                            "dialogue": dialogue,
                            "gold_note": note,
                            "gold_sections": gold_sections,
                        })
                        encounter_id += 1
            except Exception:
                logger.warning("[ACI-Bench] Could not parse %s as CSV, skipping", fname)
                continue

        elif ext == ".json":
            logger.info("[ACI-Bench] Parsing JSON %s...", fname)
            try:
                with open(fpath, encoding="utf-8") as jf:
                    data = json.load(jf)

                if isinstance(data, list):
                    entries = data
                elif isinstance(data, dict) and "data" in data:
                    entries = data["data"]
                else:
                    entries = [data]

                for entry in entries:
                    dialogue = entry.get("dialogue", entry.get("input", entry.get("src", "")))
                    note = entry.get("note", entry.get("output", entry.get("tgt", "")))

                    if not dialogue or not note:
                        continue

                    enc_id = f"aci_{encounter_id:04d}"
                    gold_sections = _parse_aci_sections(note, enc_id)

                    manifest.append({
                        "id": enc_id,
                        "source_file": fname,
                        "dialogue": dialogue,
                        "gold_note": note,
                        "gold_sections": gold_sections,
                    })
                    encounter_id += 1
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning("[ACI-Bench] Could not parse %s as JSON, skipping", fname)
                continue

    n_valid = sum(1 for m in manifest if len(m.get("gold_sections", {})) == 4)
    logger.info(
        "[ACI-Bench] Manifest saved: %s (%d encounters, %d with valid 4-section split)",
        manifest_path,
        len(manifest),
        n_valid,
    )

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Downloading evaluation datasets...")
    logger.info("=" * 60)

    fareez = download_fareez()
    logger.info("")
    aci = download_aci_bench()

    logger.info("")
    logger.info("Done. Stage 1: %d audio files, Stage 2: %d encounters", len(fareez), len(aci))
