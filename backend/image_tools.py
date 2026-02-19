"""Image analysis tools: MedGemma vision + MedSigLIP similarity search."""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------- Vision LLM config ----------

VISION_LLM_BASE_URL = os.getenv("VISION_LLM_BASE_URL", "http://localhost:8080/v1")
VISION_LLM_MODEL = os.getenv("VISION_LLM_MODEL", "google/medgemma-1.5-4b-it")
VISION_LLM_TIMEOUT = int(os.getenv("VISION_LLM_TIMEOUT", "60"))
VISION_LLM_MAX_TOKENS = int(os.getenv("VISION_LLM_MAX_TOKENS", "1024"))

# ---------- FAISS / MedSigLIP config ----------

FAISS_INDEX_PATH = os.getenv(
    "FAISS_INDEX_PATH",
    str(Path(__file__).resolve().parent / "data" / "faiss_index.bin"),
)
MEDSIG_MODEL_NAME = os.getenv("MEDSIG_MODEL_NAME", "google/siglip-base-patch16-256")

# Lazy-loaded singletons
_siglip_model = None
_siglip_processor = None
_faiss_index = None
_faiss_labels: list[str] = []


def _load_siglip():
    """Lazy-load the SigLIP model and processor (singleton)."""
    global _siglip_model, _siglip_processor
    if _siglip_model is not None:
        return _siglip_model, _siglip_processor

    try:
        from transformers import AutoModel, AutoProcessor

        logger.info("Loading MedSigLIP model: %s", MEDSIG_MODEL_NAME)
        _siglip_processor = AutoProcessor.from_pretrained(MEDSIG_MODEL_NAME)
        _siglip_model = AutoModel.from_pretrained(MEDSIG_MODEL_NAME)
        _siglip_model.eval()
        logger.info("MedSigLIP model loaded successfully")
    except Exception:
        logger.warning(
            "Could not load MedSigLIP model '%s'. "
            "Similar-image search will be unavailable.",
            MEDSIG_MODEL_NAME,
            exc_info=True,
        )
        _siglip_model = None
        _siglip_processor = None

    return _siglip_model, _siglip_processor


def _load_faiss_index():
    """Lazy-load the FAISS index from disk (singleton)."""
    global _faiss_index, _faiss_labels
    if _faiss_index is not None:
        return _faiss_index, _faiss_labels

    index_path = Path(FAISS_INDEX_PATH)
    labels_path = index_path.with_suffix(".labels.txt")

    if not index_path.exists():
        logger.warning(
            "FAISS index not found at %s. Similar-image search will return empty results.",
            index_path,
        )
        return None, []

    try:
        import faiss

        logger.info("Loading FAISS index from %s", index_path)
        _faiss_index = faiss.read_index(str(index_path))

        if labels_path.exists():
            _faiss_labels = labels_path.read_text().strip().splitlines()
        else:
            _faiss_labels = [
                f"condition_{i}" for i in range(_faiss_index.ntotal)
            ]

        logger.info(
            "FAISS index loaded: %d vectors, %d labels",
            _faiss_index.ntotal,
            len(_faiss_labels),
        )
    except Exception:
        logger.warning("Failed to load FAISS index", exc_info=True)
        _faiss_index = None
        _faiss_labels = []

    return _faiss_index, _faiss_labels


def get_vision_config() -> dict:
    """Return current vision LLM configuration."""
    return {
        "base_url": VISION_LLM_BASE_URL,
        "model": VISION_LLM_MODEL,
    }


def update_vision_config(base_url: str, model: str) -> None:
    """Hot-swap vision LLM provider at runtime."""
    global VISION_LLM_BASE_URL, VISION_LLM_MODEL
    VISION_LLM_BASE_URL = base_url
    VISION_LLM_MODEL = model
    logger.info("Vision LLM config updated: base_url=%s model=%s", base_url, model)


# ---------- Public API ----------


async def analyze_image(
    image_bytes: bytes, clinical_context: str = ""
) -> str:
    """Analyze a medical image using MedGemma-1.5-4b-it (multimodal).

    Sends the image as base64-encoded data via an OpenAI-compatible
    vision API. Returns a clinical description string.

    Gracefully degrades to placeholder text if the vision model is
    unreachable.
    """
    from agents import IMAGE_ANALYSIS_PROMPT

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    context_addendum = ""
    if clinical_context:
        context_addendum = f"\n\nAdditional clinical context: {clinical_context}"

    messages = [
        {
            "role": "system",
            "content": IMAGE_ANALYSIS_PROMPT,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64_image}",
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Describe the clinical findings in this medical image."
                        + context_addendum
                    ),
                },
            ],
        },
    ]

    payload = {
        "model": VISION_LLM_MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": VISION_LLM_MAX_TOKENS,
    }

    try:
        async with httpx.AsyncClient(timeout=VISION_LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{VISION_LLM_BASE_URL}/chat/completions", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            vision_result = data["choices"][0]["message"]["content"]
    except Exception:
        logger.warning(
            "Vision LLM call failed — returning placeholder description.",
            exc_info=True,
        )
        vision_result = (
            "Image analysis unavailable. The vision model could not be reached. "
            "Please review the image manually and add findings to the Objective section."
        )

    # Run enabled image classifiers
    classifier_results: dict[str, dict] = {}
    try:
        import classifier_registry

        for clf in classifier_registry.get_enabled_classifiers("image"):
            preds = await classifier_registry.predict_image(clf["id"], image_bytes)
            if preds:
                classifier_results[clf["id"]] = {
                    "name": clf.get("name", clf["id"]),
                    "predictions": preds,
                }
    except Exception as exc:
        logger.warning("Image classifier pipeline error: %s", exc)

    if classifier_results:
        clf_summary = "\n\n--- Classifier Predictions ---\n"
        for clf_id, clf_data in classifier_results.items():
            clf_summary += f"{clf_data['name']}:\n"
            for label, score in clf_data["predictions"].items():
                clf_summary += f"  - {label}: {score:.1%}\n"
        clf_summary += "\nNote: These are from trained diagnostic classifiers and should be considered alongside the vision model analysis."
        vision_result += clf_summary

    return vision_result


async def search_similar(
    image_bytes: bytes, top_k: int = 3
) -> list[dict]:
    """Search for similar cases using SigLIP embeddings + FAISS.

    Returns a list of ``{"condition_label": str, "similarity_score": float}``
    dicts, sorted by descending similarity.

    Gracefully degrades to an empty list if the model or index is unavailable.
    """
    model, processor = _load_siglip()
    if model is None or processor is None:
        logger.warning("SigLIP model not available; skipping similarity search.")
        return []

    index, labels = _load_faiss_index()
    if index is None:
        logger.warning("FAISS index not available; skipping similarity search.")
        return []

    try:
        import io

        import numpy as np
        import torch
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = processor(images=image, return_tensors="pt")

        with torch.no_grad():
            image_features = model.get_image_features(**inputs)

        # Normalize for cosine similarity
        embedding = image_features / image_features.norm(dim=-1, keepdim=True)
        query_vec = embedding.cpu().numpy().astype("float32")

        distances, indices = index.search(query_vec, min(top_k, index.ntotal))

        results: list[dict] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            label = labels[idx] if idx < len(labels) else f"condition_{idx}"
            # FAISS inner-product distance is cosine similarity for normalized vecs
            score = float(dist)
            # Clamp to [0, 1] for display
            score = max(0.0, min(1.0, score))
            results.append(
                {"condition_label": label, "similarity_score": round(score, 4)}
            )

        return results

    except Exception:
        logger.warning("Similarity search failed", exc_info=True)
        return []
