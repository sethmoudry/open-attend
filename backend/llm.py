"""Async LLM client — auto-selects provider based on environment.

CUDA available → local MedGemma via vLLM/Ollama (OpenAI-compatible).
No CUDA (Mac)  → OpenRouter API with Gemini Flash Lite.
"""

import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


# Auto-select provider
if os.getenv("LLM_BASE_URL"):
    # Explicit override always wins
    LLM_BASE_URL = os.environ["LLM_BASE_URL"]
    LLM_MODEL = os.getenv("LLM_MODEL", "google/medgemma-27b-text-it")
    _LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY")
elif _has_cuda():
    # GPU box — use local MedGemma 1.5 4B IT (AWQ) via vLLM
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "MedGemmaImpact/medgemma-1.5-4b-it-awq")
    _LLM_API_KEY = os.getenv("LLM_API_KEY", "none")
else:
    # Mac / CPU — use OpenRouter with Flash Lite for dev
    LLM_BASE_URL = "https://openrouter.ai/api/v1"
    LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025")
    _LLM_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_TOKEN")

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# Cost per million tokens (USD) — update for your provider
_COST_PER_M_INPUT = float(os.getenv("LLM_COST_PER_M_INPUT", "0.075"))   # gemini flash lite
_COST_PER_M_OUTPUT = float(os.getenv("LLM_COST_PER_M_OUTPUT", "0.30"))

logger.info("LLM provider: %s model=%s", LLM_BASE_URL, LLM_MODEL)

# ---- Token usage tracking ----
_total_prompt_tokens: int = 0
_total_completion_tokens: int = 0
_total_calls: int = 0


def get_usage_stats() -> dict:
    """Return cumulative token usage and estimated cost."""
    total = _total_prompt_tokens + _total_completion_tokens
    cost = (
        _total_prompt_tokens * _COST_PER_M_INPUT / 1_000_000
        + _total_completion_tokens * _COST_PER_M_OUTPUT / 1_000_000
    )
    return {
        "total_calls": _total_calls,
        "prompt_tokens": _total_prompt_tokens,
        "completion_tokens": _total_completion_tokens,
        "total_tokens": total,
        "estimated_cost_usd": round(cost, 4),
        "model": LLM_MODEL,
        "provider": LLM_BASE_URL,
    }

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """Return a reusable async HTTP client (lazy singleton)."""
    global _client
    if _client is None or _client.is_closed:
        headers = {}
        if _LLM_API_KEY:
            headers["Authorization"] = f"Bearer {_LLM_API_KEY}"
        _client = httpx.AsyncClient(timeout=LLM_TIMEOUT, headers=headers)
    return _client


async def shutdown() -> None:
    """Close the HTTP client. Call during application shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


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

    global _total_prompt_tokens, _total_completion_tokens, _total_calls

    client = _get_client()
    try:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions", json=payload
        )
        resp.raise_for_status()
        data = resp.json()

        # Track token usage
        usage = data.get("usage", {})
        _total_prompt_tokens += usage.get("prompt_tokens", 0)
        _total_completion_tokens += usage.get("completion_tokens", 0)
        _total_calls += 1

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
