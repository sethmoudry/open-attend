"""Pluggable classifier registry for audio and image classifiers.

Drop-in ready: add any trained classifier that maps HeAR audio embeddings
or medical images to diagnostic labels. The LLM interprets structured
predictions in clinical context.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

BUILTIN_CATALOG: list[dict[str, Any]] = [
    {
        "id": "torchxrayvision-densenet121",
        "name": "TorchXRayVision DenseNet121",
        "type": "image",
        "model_id": "torchxrayvision/densenet121-res224-all",
        "labels": [
            "Atelectasis", "Cardiomegaly", "Consolidation", "Edema",
            "Effusion", "Emphysema", "Fibrosis", "Hernia",
            "Infiltration", "Mass", "Nodule", "Pleural_Thickening",
            "Pneumonia", "Pneumothorax",
        ],
        "enabled": False,
        "installed": False,
        "description": "14-pathology chest X-ray classifier (DenseNet121, pretrained on CheXpert+MIMIC+NIH+PadChest)",
    },
    {
        "id": "respiratory-cough-cnn",
        "name": "Respiratory Cough Detector",
        "type": "audio",
        "model_id": "custom/respiratory-cough-cnn",
        "labels": ["cough", "wheeze", "stridor", "normal_breathing"],
        "enabled": False,
        "installed": False,
        "description": "CNN classifier for respiratory sounds from HeAR embeddings (requires trained weights)",
    },
    {
        "id": "skin-lesion-classifier",
        "name": "Skin Lesion Classifier",
        "type": "image",
        "model_id": "custom/skin-lesion-classifier",
        "labels": [
            "melanoma", "basal_cell_carcinoma", "squamous_cell_carcinoma",
            "actinic_keratosis", "benign_nevus", "dermatofibroma", "seborrheic_keratosis",
        ],
        "enabled": False,
        "installed": False,
        "description": "Skin lesion classification from dermoscopic images (requires trained weights)",
    },
]

_enabled_classifiers: dict[str, bool] = {}
_loaded_models: dict[str, Any] = {}


def get_catalog() -> list[dict[str, Any]]:
    catalog = []
    for entry in BUILTIN_CATALOG:
        item = {**entry}
        item["enabled"] = _enabled_classifiers.get(entry["id"], entry["enabled"])
        item["loaded"] = entry["id"] in _loaded_models
        catalog.append(item)
    return catalog


def get_enabled_classifiers(classifier_type: str) -> list[dict[str, Any]]:
    return [c for c in get_catalog() if c["type"] == classifier_type and c["enabled"]]


def set_enabled_classifiers(classifiers: list[dict[str, Any]]) -> None:
    for clf in classifiers:
        if "id" in clf and "enabled" in clf:
            _enabled_classifiers[clf["id"]] = clf["enabled"]
            if not clf["enabled"] and clf["id"] in _loaded_models:
                del _loaded_models[clf["id"]]
                logger.info("Unloaded classifier: %s", clf["id"])


def predict_image(classifier_id: str, image: Any) -> dict[str, float] | None:
    if classifier_id not in _loaded_models:
        return None
    return None


def predict_audio(classifier_id: str, embeddings: Any) -> dict[str, float] | None:
    if classifier_id not in _loaded_models:
        return None
    return None
