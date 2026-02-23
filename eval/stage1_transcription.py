"""Stage 1: Transcription evaluation — audio → backend → score WER/MEER.

Feeds Fareez OSCE audio through the backend's /eval/transcribe endpoint,
then scores MedASR, Whisper, and Merged outputs against reference transcripts.

Features:
- Incremental CSV writes (resume on restart — skips completed IDs)
- Entity extraction with disk cache for determinism
- Collects top-5 divergent examples
"""

import asyncio
import csv
import json
import logging
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from config import BACKEND_URL, DATA_DIR, RESULTS_DIR, ASR_TIMEOUT
from scoring import compute_wer, compute_meer, extract_medical_entities

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

FAREEZ_DIR = os.path.join(DATA_DIR, "fareez")
RESULTS_CSV = os.path.join(RESULTS_DIR, "stage1_results.csv")
SUMMARY_JSON = os.path.join(RESULTS_DIR, "stage1_summary.json")
EXAMPLES_JSON = os.path.join(RESULTS_DIR, "stage1_examples.json")

CSV_FIELDS = [
    "id", "specialty",
    "medasr_wer", "whisper_wer", "merged_wer",
    "medasr_meer", "whisper_meer", "merged_meer",
    "medasr_meer_missed", "medasr_meer_novel",
    "whisper_meer_missed", "whisper_meer_novel",
    "merged_meer_missed", "merged_meer_novel",
    "ref_entity_count", "medasr_entity_count", "whisper_entity_count", "merged_entity_count",
    "n_diarization_segments",
    "ref_len", "medasr_len", "whisper_len", "merged_len",
    "error",
]


def _load_completed_ids() -> set[str]:
    """Load IDs already processed from the results CSV."""
    completed = set()
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add(row["id"])
    return completed


async def run_stage1():
    """Run stage 1 evaluation."""
    # Load manifest
    manifest_path = os.path.join(FAREEZ_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        logger.error("Fareez manifest not found. Run download_data.py first.")
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    logger.info("[Stage 1] %d audio files in manifest", len(manifest))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    completed = _load_completed_ids()
    logger.info("[Stage 1] %d already completed, %d remaining", len(completed), len(manifest) - len(completed))

    # Open CSV for incremental writes
    write_header = not os.path.exists(RESULTS_CSV) or len(completed) == 0
    csv_file = open(RESULTS_CSV, "a", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    if write_header:
        writer.writeheader()

    all_rows = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(ASR_TIMEOUT, connect=30.0)) as client:
        for i, entry in enumerate(manifest):
            if entry["id"] in completed:
                continue

            logger.info("[Stage 1] [%d/%d] Processing %s (%s)...", i + 1, len(manifest), entry["id"], entry.get("specialty", "?"))

            row = {"id": entry["id"], "specialty": entry.get("specialty", ""), "error": ""}

            try:
                # Read audio file
                audio_path = entry["audio_path"]
                with open(audio_path, "rb") as af:
                    audio_bytes = af.read()

                # Send to backend
                files = {"audio": (os.path.basename(audio_path), audio_bytes, "audio/wav")}
                resp = await client.post(f"{BACKEND_URL}/eval/transcribe", files=files)
                resp.raise_for_status()
                result = resp.json()

                medasr_text = result.get("medasr_text", "")
                whisper_text = result.get("whisper_text", "")
                merged_text = result.get("merged_text", "")
                ref_text = entry.get("reference_text", "")

                row["ref_len"] = len(ref_text)
                row["medasr_len"] = len(medasr_text)
                row["whisper_len"] = len(whisper_text)
                row["merged_len"] = len(merged_text)
                row["n_diarization_segments"] = result.get("n_diarization_segments", 0)

                # Compute WER
                if ref_text:
                    row["medasr_wer"] = round(compute_wer(ref_text, medasr_text), 4)
                    row["whisper_wer"] = round(compute_wer(ref_text, whisper_text), 4)
                    row["merged_wer"] = round(compute_wer(ref_text, merged_text), 4)
                else:
                    row["medasr_wer"] = ""
                    row["whisper_wer"] = ""
                    row["merged_wer"] = ""

                # Extract entities (cached after first run)
                ref_entities = await extract_medical_entities(client, BACKEND_URL, ref_text) if ref_text else []
                medasr_entities = await extract_medical_entities(client, BACKEND_URL, medasr_text)
                whisper_entities = await extract_medical_entities(client, BACKEND_URL, whisper_text)
                merged_entities = await extract_medical_entities(client, BACKEND_URL, merged_text)

                row["ref_entity_count"] = len(ref_entities)
                row["medasr_entity_count"] = len(medasr_entities)
                row["whisper_entity_count"] = len(whisper_entities)
                row["merged_entity_count"] = len(merged_entities)

                # Compute MEER
                if ref_entities:
                    medasr_meer = compute_meer(ref_entities, medasr_entities)
                    whisper_meer = compute_meer(ref_entities, whisper_entities)
                    merged_meer = compute_meer(ref_entities, merged_entities)

                    row["medasr_meer"] = round(medasr_meer["meer"], 4)
                    row["medasr_meer_missed"] = medasr_meer["missed"]
                    row["medasr_meer_novel"] = medasr_meer["novel"]

                    row["whisper_meer"] = round(whisper_meer["meer"], 4)
                    row["whisper_meer_missed"] = whisper_meer["missed"]
                    row["whisper_meer_novel"] = whisper_meer["novel"]

                    row["merged_meer"] = round(merged_meer["meer"], 4)
                    row["merged_meer_missed"] = merged_meer["missed"]
                    row["merged_meer_novel"] = merged_meer["novel"]

            except Exception as exc:
                logger.error("[Stage 1] Error processing %s: %s", entry["id"], exc)
                row["error"] = str(exc)

            writer.writerow(row)
            csv_file.flush()
            all_rows.append(row)

    csv_file.close()

    # Reload all rows for summary
    all_rows_full = []
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV) as f:
            all_rows_full = list(csv.DictReader(f))

    # Compute aggregates
    _compute_summary(all_rows_full)
    _collect_examples(all_rows_full)

    logger.info("[Stage 1] Done. Results in %s", RESULTS_DIR)


def _safe_float(val) -> float | None:
    """Convert to float or return None."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _compute_summary(rows: list[dict]):
    """Compute and save aggregate summary."""
    metrics = ["medasr_wer", "whisper_wer", "merged_wer", "medasr_meer", "whisper_meer", "merged_meer"]
    summary = {"n_total": len(rows), "n_errors": sum(1 for r in rows if r.get("error"))}

    for metric in metrics:
        values = [_safe_float(r.get(metric)) for r in rows]
        values = [v for v in values if v is not None]
        if values:
            summary[f"{metric}_mean"] = round(sum(values) / len(values), 4)
            summary[f"{metric}_min"] = round(min(values), 4)
            summary[f"{metric}_max"] = round(max(values), 4)
            summary[f"{metric}_n"] = len(values)

    # Per-specialty breakdown
    specialties = set(r.get("specialty", "") for r in rows if r.get("specialty"))
    summary["by_specialty"] = {}
    for spec in sorted(specialties):
        spec_rows = [r for r in rows if r.get("specialty") == spec]
        spec_summary = {"n": len(spec_rows)}
        for metric in ["merged_wer", "merged_meer"]:
            values = [_safe_float(r.get(metric)) for r in spec_rows]
            values = [v for v in values if v is not None]
            if values:
                spec_summary[f"{metric}_mean"] = round(sum(values) / len(values), 4)
        summary["by_specialty"][spec] = spec_summary

    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("[Stage 1] Summary: merged WER=%.4f, merged MEER=%.4f",
                summary.get("merged_wer_mean", -1), summary.get("merged_meer_mean", -1))


def _collect_examples(rows: list[dict]):
    """Collect top-5 most divergent examples (highest merged WER)."""
    scored = []
    for r in rows:
        wer = _safe_float(r.get("merged_wer"))
        if wer is not None:
            scored.append({"id": r["id"], "specialty": r.get("specialty", ""), "merged_wer": wer})

    scored.sort(key=lambda x: x["merged_wer"], reverse=True)
    examples = scored[:5]

    with open(EXAMPLES_JSON, "w") as f:
        json.dump(examples, f, indent=2)


if __name__ == "__main__":
    asyncio.run(run_stage1())
