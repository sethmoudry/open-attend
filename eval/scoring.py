"""Scoring functions for the evaluation pipeline.

Provides: WER, MEER, ROUGE, entity metrics, LLM-judge scoring.
All LLM-dependent functions use try/except with graceful fallbacks.
"""

import logging
import os
import re
import sys

import httpx

sys.path.insert(0, os.path.dirname(__file__))
import entity_cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

_SPEAKER_PREFIX = re.compile(r"^(D|P|Doctor|Patient|Dr|Pt)\s*:\s*", re.MULTILINE | re.IGNORECASE)
_PUNCT = re.compile(r"[^\w\s]")


def normalize_transcript(text: str) -> str:
    """Normalize transcript for WER comparison: strip speaker labels, lowercase, remove punctuation."""
    text = _SPEAKER_PREFIX.sub("", text)
    text = _PUNCT.sub("", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


# ---------------------------------------------------------------------------
# WER (Word Error Rate)
# ---------------------------------------------------------------------------


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate using jiwer."""
    from jiwer import wer

    ref = normalize_transcript(reference)
    hyp = normalize_transcript(hypothesis)

    if not ref:
        return 0.0 if not hyp else 1.0

    return wer(ref, hyp)


# ---------------------------------------------------------------------------
# Medical Entity Error Rate (MEER)
# ---------------------------------------------------------------------------


def compute_meer(ref_entities: list[str], hyp_entities: list[str], threshold: float = 0.85) -> dict:
    """Compute Medical Entity Error Rate.

    MEER = (missed + novel) / total_ref

    Uses rapidfuzz for O(n) fuzzy matching instead of SequenceMatcher.
    """
    from rapidfuzz import fuzz

    if not ref_entities:
        return {
            "meer": 0.0,
            "missed": 0,
            "novel": len(hyp_entities),
            "matched": 0,
            "total_ref": 0,
            "total_hyp": len(hyp_entities),
        }

    ref_lower = [e.lower() for e in ref_entities]
    hyp_lower = [e.lower() for e in hyp_entities]

    matched_ref = set()
    matched_hyp = set()

    for i, ref_e in enumerate(ref_lower):
        for j, hyp_e in enumerate(hyp_lower):
            if j in matched_hyp:
                continue
            score = fuzz.ratio(ref_e, hyp_e) / 100.0
            if score >= threshold:
                matched_ref.add(i)
                matched_hyp.add(j)
                break

    missed = len(ref_lower) - len(matched_ref)
    novel = len(hyp_lower) - len(matched_hyp)
    total_ref = len(ref_lower)
    meer = (missed + novel) / total_ref if total_ref > 0 else 0.0

    return {
        "meer": meer,
        "missed": missed,
        "novel": novel,
        "matched": len(matched_ref),
        "total_ref": total_ref,
        "total_hyp": len(hyp_lower),
    }


# ---------------------------------------------------------------------------
# ROUGE scores
# ---------------------------------------------------------------------------


def compute_rouge(reference: str, hypothesis: str) -> dict:
    """Compute ROUGE-1/2/L F1 scores."""
    from rouge_score import rouge_scorer

    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = scorer.score(reference, hypothesis)

    return {
        "rouge1": scores["rouge1"].fmeasure,
        "rouge2": scores["rouge2"].fmeasure,
        "rougeL": scores["rougeL"].fmeasure,
    }


# ---------------------------------------------------------------------------
# Entity extraction (LLM-based, cached)
# ---------------------------------------------------------------------------


async def extract_medical_entities(
    client: httpx.AsyncClient,
    backend_url: str,
    text: str,
) -> list[str]:
    """Extract medical entities via backend, with disk cache for determinism."""
    if not text or not text.strip():
        return []

    # Check cache first
    cached = entity_cache.get(text)
    if cached is not None:
        return cached

    try:
        resp = await client.post(
            f"{backend_url}/eval/extract-entities",
            json={"text": text},
            timeout=120.0,
        )
        resp.raise_for_status()
        entities = resp.json().get("entities", [])
    except Exception as exc:
        logger.warning("Entity extraction failed: %s", exc)
        entities = []

    # Cache for next run
    entity_cache.put(text, entities)
    return entities


# ---------------------------------------------------------------------------
# Entity metrics (completeness, faithfulness, unsupported, omission)
# ---------------------------------------------------------------------------


def compute_entity_metrics(
    dialogue_entities: list[str],
    generated_entities: list[str],
    gold_entities: list[str],
    threshold: float = 0.85,
) -> dict:
    """Compute entity-level clinical metrics.

    Args:
        dialogue_entities: Entities from the source dialogue/transcript.
        generated_entities: Entities from the generated note.
        gold_entities: Entities from the gold-standard note.

    Returns:
        Dict with completeness, faithfulness, unsupported_rate, omission_rate, etc.
    """
    from rapidfuzz import fuzz

    def _fuzzy_contains(entity: str, entity_list: list[str]) -> bool:
        for e in entity_list:
            if fuzz.ratio(entity.lower(), e.lower()) / 100.0 >= threshold:
                return True
        return False

    if not gold_entities:
        return {
            "completeness": 1.0,
            "faithfulness": 1.0,
            "unsupported_rate": 0.0,
            "omission_rate": 0.0,
            "n_unsupported": 0,
            "n_omissions": 0,
            "n_generated": len(generated_entities),
            "n_gold": 0,
            "n_dialogue": len(dialogue_entities),
        }

    # Completeness: what fraction of gold entities appear in generated?
    gold_found = sum(1 for e in gold_entities if _fuzzy_contains(e, generated_entities))
    completeness = gold_found / len(gold_entities)

    # Omissions: gold entities NOT in generated
    n_omissions = len(gold_entities) - gold_found
    omission_rate = n_omissions / len(gold_entities)

    # Faithfulness: what fraction of generated entities are grounded in dialogue?
    if generated_entities:
        grounded = sum(1 for e in generated_entities if _fuzzy_contains(e, dialogue_entities))
        faithfulness = grounded / len(generated_entities)

        # Unsupported: generated entities NOT grounded in dialogue
        n_unsupported = len(generated_entities) - grounded
        unsupported_rate = n_unsupported / len(generated_entities)
    else:
        faithfulness = 1.0
        n_unsupported = 0
        unsupported_rate = 0.0

    # Entity F1 vs gold standard (precision = generated in gold, recall = gold in generated)
    if generated_entities:
        entity_precision = sum(1 for e in generated_entities if _fuzzy_contains(e, gold_entities)) / len(generated_entities)
    else:
        entity_precision = 0.0
    entity_recall = completeness  # gold_found / len(gold_entities)
    entity_f1 = (2 * entity_precision * entity_recall / (entity_precision + entity_recall)
                 if (entity_precision + entity_recall) > 0 else 0.0)

    return {
        "completeness": completeness,
        "faithfulness": faithfulness,
        "entity_precision": entity_precision,
        "entity_recall": entity_recall,
        "entity_f1": entity_f1,
        "unsupported_rate": unsupported_rate,
        "omission_rate": omission_rate,
        "n_unsupported": n_unsupported,
        "n_omissions": n_omissions,
        "n_generated": len(generated_entities),
        "n_gold": len(gold_entities),
        "n_dialogue": len(dialogue_entities),
    }


# ---------------------------------------------------------------------------
# LLM-as-judge
# ---------------------------------------------------------------------------


def parse_soap_section(soap_text: str, section: str) -> str:
    """Extract a named section from a SOAP note string.

    Handles headers like 'Assessment:', 'ASSESSMENT:', 'A:', 'Assessment and Plan:', etc.
    """
    if not soap_text:
        return ""

    patterns = {
        "assessment": r"(?:^|\n)\s*(?:assessment(?:\s+and\s+plan)?|A)\s*[:\-]\s*(.*?)(?=\n\s*(?:plan|P)\s*[:\-]|\Z)",
        "plan": r"(?:^|\n)\s*(?:plan|P)\s*[:\-]\s*(.*?)(?=\Z)",
        "subjective": r"(?:^|\n)\s*(?:subjective|S)\s*[:\-]\s*(.*?)(?=\n\s*(?:objective|O)\s*[:\-]|\Z)",
        "objective": r"(?:^|\n)\s*(?:objective|O)\s*[:\-]\s*(.*?)(?=\n\s*(?:assessment|A)\s*[:\-]|\Z)",
    }
    pattern = patterns.get(section)
    if not pattern:
        return ""
    match = re.search(pattern, soap_text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


async def extract_codes_from_text(
    backend_url: str,
    text: str,
    section: str,
) -> set[str]:
    """Extract ICD-10 or CPT codes from a SOAP section via the backend eval endpoint.

    Args:
        backend_url: e.g. "http://localhost:8000"
        text: The SOAP section text
        section: "assessment" for ICD-10, "plan" for CPT

    Returns set of code strings (e.g. {"J06.9", "R50.9"}).
    """
    if not text or not text.strip():
        return set()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{backend_url}/api/eval/extract-codes",
                json={"text": text, "section": section},
            )
            resp.raise_for_status()
            codes = resp.json().get("codes", [])
            return {c["code"] for c in codes if c.get("code")}
    except Exception as exc:
        logger.warning("Code extraction for eval failed: %s", exc)
        return set()


def compute_code_f1(gold_codes: set[str], pred_codes: set[str]) -> dict:
    """Compute precision, recall, F1 on code sets.

    Matching is case-insensitive, period-insensitive (J06.9 == j069).
    """
    def _normalize(codes: set[str]) -> set[str]:
        return {c.strip().upper().replace(".", "") for c in codes if c.strip()}

    gold = _normalize(gold_codes)
    pred = _normalize(pred_codes)

    if not gold and not pred:
        return {"code_precision": 1.0, "code_recall": 1.0, "code_f1": 1.0,
                "n_gold_codes": 0, "n_pred_codes": 0}
    if not pred:
        return {"code_precision": 0.0, "code_recall": 0.0, "code_f1": 0.0,
                "n_gold_codes": len(gold), "n_pred_codes": 0}
    if not gold:
        return {"code_precision": 0.0, "code_recall": 0.0, "code_f1": 0.0,
                "n_gold_codes": 0, "n_pred_codes": len(pred)}

    tp = len(gold & pred)
    precision = tp / len(pred)
    recall = tp / len(gold)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"code_precision": round(precision, 4), "code_recall": round(recall, 4),
            "code_f1": round(f1, 4), "n_gold_codes": len(gold), "n_pred_codes": len(pred)}


# ---------------------------------------------------------------------------
# LLM-as-judge
# ---------------------------------------------------------------------------


async def llm_judge_note(
    client: httpx.AsyncClient,
    backend_url: str,
    dialogue: str,
    soap_note: str,
) -> dict:
    """Score a SOAP note using the LLM-as-judge endpoint.

    Returns dict with completeness, accuracy, organization, clinical_language,
    actionability, total, reasoning. On failure, returns zeroed scores.
    """
    try:
        resp = await client.post(
            f"{backend_url}/eval/llm-judge",
            json={"dialogue": dialogue, "soap_note": soap_note},
            timeout=120.0,
        )
        resp.raise_for_status()
        result = resp.json()

        return {
            "completeness": result.get("completeness", 0),
            "accuracy": result.get("accuracy", 0),
            "organization": result.get("organization", 0),
            "clinical_language": result.get("clinical_language", 0),
            "actionability": result.get("actionability", 0),
            "total": result.get("total", 0),
            "reasoning": result.get("reasoning", ""),
            "parse_error": False,
        }
    except Exception as exc:
        logger.warning("LLM judge failed: %s", exc)
        return {
            "completeness": 0,
            "accuracy": 0,
            "organization": 0,
            "clinical_language": 0,
            "actionability": 0,
            "total": 0,
            "reasoning": f"Error: {exc}",
            "parse_error": True,
        }
