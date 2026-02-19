"""Async LLM client for MedGemma-27b-text-it via OpenAI-compatible API."""

import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "google/medgemma-27b-text-it")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))


def _build_messages(
    prompt: str, system_prompt: Optional[str] = None
) -> list[dict]:
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


async def call_medgemma(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """Send a prompt to MedGemma and return the raw text response.

    Uses the OpenAI-compatible /chat/completions endpoint so it works
    with vLLM, Ollama, LM Studio, etc.
    """
    payload = {
        "model": LLM_MODEL,
        "messages": _build_messages(prompt, system_prompt),
        "temperature": temperature if temperature is not None else LLM_TEMPERATURE,
        "max_tokens": max_tokens or LLM_MAX_TOKENS,
    }

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        try:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException:
            logger.error("LLM request timed out after %ds", LLM_TIMEOUT)
            raise
        except httpx.HTTPStatusError as exc:
            logger.error(
                "LLM returned %d: %s", exc.response.status_code, exc.response.text
            )
            raise
        except (KeyError, IndexError) as exc:
            logger.error("Unexpected LLM response shape: %s", exc)
            raise


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction from LLM text.

    Handles:
    1. Clean JSON responses
    2. JSON wrapped in ```json ... ``` fences
    3. JSON embedded in surrounding prose
    """
    # Strip markdown fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find the first { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    # Last resort: return the text wrapped in a dict
    logger.warning("Could not parse JSON from LLM response, returning raw text")
    return {"_raw": text}


async def call_medgemma_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict:
    """Send a prompt to MedGemma and parse the response as JSON.

    Falls back to best-effort extraction if the model doesn't return
    clean JSON.
    """
    raw = await call_medgemma(
        prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return _extract_json(raw)
