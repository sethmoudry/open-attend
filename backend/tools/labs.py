"""Lab report formatting and lab value extraction (vision)."""

import logging

import httpx

from models import LabReport
from agents import LAB_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def format_labs_for_soap(lab_report: LabReport) -> str:
    """Format lab results as clinical shorthand for SOAP Objective section."""
    if not lab_report.results:
        return ""
    parts = []
    for r in lab_report.results:
        flag_marker = ""
        if r.flag.value == "high":
            flag_marker = " (H)"
        elif r.flag.value == "low":
            flag_marker = " (L)"
        elif r.flag.value == "critical":
            flag_marker = " (CRITICAL)"
        parts.append(f"{r.test} {r.value} {r.unit}{flag_marker}")

    header = "Labs"
    if lab_report.lab_name:
        header = f"Labs ({lab_report.lab_name})"
    if lab_report.date:
        header += f" {lab_report.date}"

    return f"{header}: {', '.join(parts)}"


async def extract_lab_values(image_base64: str) -> dict:
    """Extract structured lab values from a lab report image using MedGemma-1.5-4b-it vision."""
    from image_tools import (
        VISION_LLM_BASE_URL,
        VISION_LLM_MAX_TOKENS,
        VISION_LLM_MODEL,
        VISION_LLM_TIMEOUT,
    )
    from llm import _extract_json

    messages = [
        {
            "role": "system",
            "content": LAB_EXTRACTION_PROMPT,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                    },
                },
                {
                    "type": "text",
                    "text": "Extract all lab values from this lab report image. Return structured JSON.",
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
            raw_text = data["choices"][0]["message"]["content"]
            return _extract_json(raw_text)
    except Exception:
        logger.warning(
            "Lab extraction vision call failed — returning error stub.",
            exc_info=True,
        )
        return {
            "error": "Failed to extract lab values. The vision model could not process the image.",
            "lab_name": "",
            "results": [],
        }
