"""Stage 2: Note generation evaluation — transcript → backend → score ROUGE/entity/LLM-judge.

Feeds ACI-Bench dialogues through the backend's /eval/generate-notes endpoint,
then scores with ROUGE, entity metrics, and LLM-as-judge.

Features:
- Incremental CSV writes (resume on restart — skips completed IDs)
- Entity extraction with disk cache for determinism
- LLM judge with try/except fallback
"""

import asyncio
import csv
import json
import logging
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from config import BACKEND_URL, DATA_DIR, RESULTS_DIR, LLM_TIMEOUT, LLM_JUDGE_ENABLED, LLM_JUDGE_SAMPLE_SIZE
from scoring import (
    compute_rouge,
    compute_entity_metrics,
    extract_medical_entities,
    llm_judge_note,
    parse_soap_section,
    extract_codes_from_text,
    compute_code_f1,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

CONCURRENCY = int(os.getenv("EVAL_CONCURRENCY", "8"))

ACI_DIR = os.path.join(DATA_DIR, "aci_bench")
NOTES_CSV = os.path.join(RESULTS_DIR, "stage2_notes.csv")
ENTITY_CSV = os.path.join(RESULTS_DIR, "stage2_entities.csv")
JUDGE_CSV = os.path.join(RESULTS_DIR, "stage2_judge.csv")
SUMMARY_JSON = os.path.join(RESULTS_DIR, "stage2_summary.json")
FULL_SUMMARY_JSON = os.path.join(RESULTS_DIR, "summary.json")
EXAMPLES_JSON = os.path.join(RESULTS_DIR, "stage2_examples.json")

TEXT_CSV = os.path.join(RESULTS_DIR, "stage2_text.csv")
TEXT_FIELDS = [
    "id",
    "dialogue", "gold_note", "soap_note", "aci_note",
]

NOTES_FIELDS = [
    "id",
    "rouge1", "rouge2", "rougeL",
    "aci_rouge1", "aci_rouge2", "aci_rougeL",
    "soap_generated", "aci_generated",
    "error",
]

ENTITY_FIELDS = [
    "id",
    "entity_precision", "entity_recall", "entity_f1",
    "completeness", "faithfulness",
    "unsupported_rate", "omission_rate",
    "n_unsupported", "n_omissions",
    "n_generated", "n_gold", "n_dialogue",
    "error",
]

JUDGE_FIELDS = [
    "id",
    "completeness", "accuracy", "organization",
    "clinical_language", "actionability", "total",
    "reasoning", "parse_error",
]

CODES_CSV = os.path.join(RESULTS_DIR, "stage2_codes.csv")
CODES_FIELDS = [
    "id",
    "icd10_precision", "icd10_recall", "icd10_f1",
    "cpt_precision", "cpt_recall", "cpt_f1",
    "n_gold_icd10", "n_pred_icd10",
    "n_gold_cpt", "n_pred_cpt",
    "error",
]


def _load_completed_ids(csv_path: str) -> set[str]:
    """Load IDs already processed from a CSV."""
    completed = set()
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add(row["id"])
    return completed


async def run_stage2():
    """Run stage 2 evaluation."""
    manifest_path = os.path.join(ACI_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        logger.error("ACI-Bench manifest not found. Run download_data.py first.")
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Limit to configured sample size
    manifest = manifest[:LLM_JUDGE_SAMPLE_SIZE]
    logger.info("[Stage 2] %d encounters to evaluate", len(manifest))

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Load completed IDs for each CSV
    notes_done = _load_completed_ids(NOTES_CSV)
    entity_done = _load_completed_ids(ENTITY_CSV)
    judge_done = _load_completed_ids(JUDGE_CSV)
    codes_done = _load_completed_ids(CODES_CSV)

    already_done = notes_done & entity_done & codes_done
    if LLM_JUDGE_ENABLED:
        already_done = already_done & judge_done

    logger.info("[Stage 2] %d already completed, %d remaining", len(already_done), len(manifest) - len(already_done))

    # Open CSVs for incremental writes
    def _open_csv(path, fields, done_set):
        write_header = not os.path.exists(path) or len(done_set) == 0
        f = open(path, "a", newline="")
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        return f, w

    text_done = _load_completed_ids(TEXT_CSV)
    notes_f, notes_w = _open_csv(NOTES_CSV, NOTES_FIELDS, notes_done)
    entity_f, entity_w = _open_csv(ENTITY_CSV, ENTITY_FIELDS, entity_done)
    judge_f, judge_w = _open_csv(JUDGE_CSV, JUDGE_FIELDS, judge_done)
    codes_f, codes_w = _open_csv(CODES_CSV, CODES_FIELDS, codes_done)
    text_f, text_w = _open_csv(TEXT_CSV, TEXT_FIELDS, text_done)

    sem = asyncio.Semaphore(CONCURRENCY)
    csv_lock = asyncio.Lock()

    async def _process_encounter(client, entry, idx, total):
        async with sem:
            enc_id = entry["id"]
            logger.info("[Stage 2] [%d/%d] Processing %s...", idx, total, enc_id)

            dialogue = entry.get("dialogue", "")
            gold_note = entry.get("gold_note", "")

            # --- Generate notes ---
            notes_row = {"id": enc_id, "error": ""}
            try:
                resp = await client.post(
                    f"{BACKEND_URL}/eval/generate-notes",
                    json={"transcript": dialogue, "format": "both"},
                    timeout=LLM_TIMEOUT,
                )
                resp.raise_for_status()
                gen_result = resp.json()

                soap_note = gen_result.get("soap_note", "")
                aci_note = gen_result.get("aci_note", "")
                notes_row["soap_generated"] = bool(soap_note)
                notes_row["aci_generated"] = bool(aci_note)

                # ROUGE: SOAP note vs gold
                if soap_note and gold_note:
                    rouge = compute_rouge(gold_note, soap_note)
                    notes_row["rouge1"] = round(rouge["rouge1"], 4)
                    notes_row["rouge2"] = round(rouge["rouge2"], 4)
                    notes_row["rougeL"] = round(rouge["rougeL"], 4)

                # ROUGE: ACI note vs gold
                if aci_note and gold_note:
                    aci_rouge = compute_rouge(gold_note, aci_note)
                    notes_row["aci_rouge1"] = round(aci_rouge["rouge1"], 4)
                    notes_row["aci_rouge2"] = round(aci_rouge["rouge2"], 4)
                    notes_row["aci_rougeL"] = round(aci_rouge["rougeL"], 4)

            except Exception as exc:
                logger.error("[Stage 2] Note generation failed for %s: %s", enc_id, exc)
                notes_row["error"] = str(exc)
                soap_note = ""
                aci_note = ""

            # --- Entity + Code metrics (parallelized) ---
            entity_row = {"id": enc_id, "error": ""}
            codes_row = {"id": enc_id, "error": ""}
            judge_row = None

            if soap_note and gold_note:
                gold_assessment = parse_soap_section(gold_note, "assessment")
                gold_plan = parse_soap_section(gold_note, "plan")
                gen_assessment = parse_soap_section(soap_note, "assessment")
                gen_plan = parse_soap_section(soap_note, "plan")

                # Fire all 7 LLM calls in parallel: 3 entity + 4 code extractions
                results = await asyncio.gather(
                    extract_medical_entities(client, BACKEND_URL, dialogue),
                    extract_medical_entities(client, BACKEND_URL, soap_note),
                    extract_medical_entities(client, BACKEND_URL, gold_note),
                    extract_codes_from_text(BACKEND_URL, gold_assessment, "assessment"),
                    extract_codes_from_text(BACKEND_URL, gen_assessment, "assessment"),
                    extract_codes_from_text(BACKEND_URL, gold_plan, "plan"),
                    extract_codes_from_text(BACKEND_URL, gen_plan, "plan"),
                    return_exceptions=True,
                )

                # Entity metrics
                try:
                    dialogue_ents, soap_ents, gold_ents = results[0], results[1], results[2]
                    for r in (dialogue_ents, soap_ents, gold_ents):
                        if isinstance(r, Exception):
                            raise r
                    metrics = compute_entity_metrics(dialogue_ents, soap_ents, gold_ents)
                    for k, v in metrics.items():
                        if isinstance(v, float):
                            entity_row[k] = round(v, 4)
                        else:
                            entity_row[k] = v
                except Exception as exc:
                    logger.error("[Stage 2] Entity metrics failed for %s: %s", enc_id, exc)
                    entity_row["error"] = str(exc)

                # Code metrics
                try:
                    gold_icd10, pred_icd10, gold_cpt, pred_cpt = results[3], results[4], results[5], results[6]
                    for r in (gold_icd10, pred_icd10, gold_cpt, pred_cpt):
                        if isinstance(r, Exception):
                            raise r

                    icd10_metrics = compute_code_f1(gold_icd10, pred_icd10)
                    cpt_metrics = compute_code_f1(gold_cpt, pred_cpt)

                    codes_row.update({
                        "icd10_precision": icd10_metrics["code_precision"],
                        "icd10_recall": icd10_metrics["code_recall"],
                        "icd10_f1": icd10_metrics["code_f1"],
                        "n_gold_icd10": icd10_metrics["n_gold_codes"],
                        "n_pred_icd10": icd10_metrics["n_pred_codes"],
                        "cpt_precision": cpt_metrics["code_precision"],
                        "cpt_recall": cpt_metrics["code_recall"],
                        "cpt_f1": cpt_metrics["code_f1"],
                        "n_gold_cpt": cpt_metrics["n_gold_codes"],
                        "n_pred_cpt": cpt_metrics["n_pred_codes"],
                    })
                except Exception as exc:
                    logger.error("[Stage 2] Code metrics failed for %s: %s", enc_id, exc)
                    codes_row["error"] = str(exc)

            # --- LLM judge ---
            if LLM_JUDGE_ENABLED and soap_note:
                judge_row = await llm_judge_note(client, BACKEND_URL, dialogue, soap_note)
                judge_row["id"] = enc_id

            # --- Text row ---
            text_row = {
                "id": enc_id,
                "dialogue": dialogue,
                "gold_note": gold_note,
                "soap_note": soap_note,
                "aci_note": aci_note,
            }

            # --- Serialized CSV writes ---
            async with csv_lock:
                notes_w.writerow(notes_row)
                notes_f.flush()
                entity_w.writerow(entity_row)
                entity_f.flush()
                if judge_row:
                    judge_w.writerow(judge_row)
                    judge_f.flush()
                codes_w.writerow(codes_row)
                codes_f.flush()
                text_w.writerow(text_row)
                text_f.flush()

    async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT, connect=30.0)) as client:
        tasks = []
        for i, entry in enumerate(manifest):
            if entry["id"] in already_done:
                continue
            tasks.append(_process_encounter(client, entry, i + 1, len(manifest)))
        await asyncio.gather(*tasks)

    notes_f.close()
    entity_f.close()
    judge_f.close()
    codes_f.close()
    text_f.close()

    # Compute summary
    _compute_summary()
    _collect_examples()

    logger.info("[Stage 2] Done. Results in %s", RESULTS_DIR)


def _safe_float(val) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _compute_summary():
    """Compute stage 2 summary and merge with stage 1 if available."""
    summary = {}

    # Notes metrics
    if os.path.exists(NOTES_CSV):
        with open(NOTES_CSV) as f:
            rows = list(csv.DictReader(f))
        summary["n_encounters"] = len(rows)
        summary["n_errors"] = sum(1 for r in rows if r.get("error"))

        for metric in ["rouge1", "rouge2", "rougeL", "aci_rouge1", "aci_rouge2", "aci_rougeL"]:
            values = [_safe_float(r.get(metric)) for r in rows]
            values = [v for v in values if v is not None]
            if values:
                summary[f"{metric}_mean"] = round(_mean(values), 4)

    # Entity metrics
    if os.path.exists(ENTITY_CSV):
        with open(ENTITY_CSV) as f:
            rows = list(csv.DictReader(f))
        for metric in ["completeness", "faithfulness", "unsupported_rate", "omission_rate",
                        "entity_precision", "entity_recall", "entity_f1"]:
            values = [_safe_float(r.get(metric)) for r in rows]
            values = [v for v in values if v is not None]
            if values:
                prefix = "" if metric.startswith("entity_") else "entity_"
                summary[f"{prefix}{metric}_mean"] = round(_mean(values), 4)

    # Judge metrics
    if os.path.exists(JUDGE_CSV):
        with open(JUDGE_CSV) as f:
            rows = list(csv.DictReader(f))
        n_parse_errors = sum(1 for r in rows if r.get("parse_error") == "True")
        summary["judge_n_scored"] = len(rows)
        summary["judge_n_parse_errors"] = n_parse_errors
        for metric in ["completeness", "accuracy", "organization", "clinical_language", "actionability", "total"]:
            values = [_safe_float(r.get(metric)) for r in rows]
            values = [v for v in values if v is not None]
            if values:
                summary[f"judge_{metric}_mean"] = round(_mean(values), 4)

    # Code metrics
    if os.path.exists(CODES_CSV):
        with open(CODES_CSV) as f:
            code_rows = list(csv.DictReader(f))
        for metric in ["icd10_precision", "icd10_recall", "icd10_f1",
                        "cpt_precision", "cpt_recall", "cpt_f1"]:
            values = [_safe_float(r.get(metric)) for r in code_rows if not r.get("error")]
            values = [v for v in values if v is not None]
            if values:
                summary[f"{metric}_mean"] = round(_mean(values), 4)

    with open(SUMMARY_JSON, "w") as f:
        json.dump(summary, f, indent=2)

    # Merge with stage 1 summary
    full_summary = {}
    stage1_path = os.path.join(RESULTS_DIR, "stage1_summary.json")
    if os.path.exists(stage1_path):
        with open(stage1_path) as f:
            full_summary["stage1"] = json.load(f)
    full_summary["stage2"] = summary

    with open(FULL_SUMMARY_JSON, "w") as f:
        json.dump(full_summary, f, indent=2)


def _collect_examples():
    """Collect top-5 lowest ROUGE examples."""
    if not os.path.exists(NOTES_CSV):
        return

    with open(NOTES_CSV) as f:
        rows = list(csv.DictReader(f))

    scored = []
    for r in rows:
        rouge1 = _safe_float(r.get("rouge1"))
        if rouge1 is not None:
            scored.append({"id": r["id"], "rouge1": rouge1})

    scored.sort(key=lambda x: x["rouge1"])
    examples = scored[:5]

    with open(EXAMPLES_JSON, "w") as f:
        json.dump(examples, f, indent=2)


if __name__ == "__main__":
    asyncio.run(run_stage2())
