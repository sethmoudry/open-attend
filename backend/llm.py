"""Async LLM client — talks to local vLLM (OpenAI-compatible endpoint)."""

import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "google/medgemma-27b-text-it")
_LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY")

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Secondary LLM for coding (ICD-10/CPT) — 4B model outperforms 27B on structured code extraction
CODING_LLM_BASE_URL = os.getenv("CODING_LLM_BASE_URL", "http://localhost:8081/v1")
CODING_LLM_MODEL = os.getenv("CODING_LLM_MODEL", "google/medgemma-1.5-4b-it")
CODING_LLM_MAX_TOKENS = int(os.getenv("CODING_LLM_MAX_TOKENS", "2048"))

# Cost per million tokens (USD) — update for your provider
_COST_PER_M_INPUT = float(os.getenv("LLM_COST_PER_M_INPUT", "0.075"))   # gemini flash lite
_COST_PER_M_OUTPUT = float(os.getenv("LLM_COST_PER_M_OUTPUT", "0.30"))

logger.info("LLM provider: %s model=%s", LLM_BASE_URL, LLM_MODEL)

# ---- Token usage tracking ----
_total_prompt_tokens: int = 0
_total_completion_tokens: int = 0
_total_calls: int = 0

# Per-session tracking: session_id → {prompt_tokens, completion_tokens, calls}
_session_usage: dict[str, dict[str, int]] = {}
_active_session_id: Optional[str] = None


def set_active_session(session_id: Optional[str]) -> None:
    """Set the active session for per-session usage tracking."""
    global _active_session_id
    _active_session_id = session_id
    if session_id and session_id not in _session_usage:
        _session_usage[session_id] = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}


def get_session_usage(session_id: str) -> dict:
    """Return usage stats for a specific session."""
    usage = _session_usage.get(session_id, {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0})
    total = usage["prompt_tokens"] + usage["completion_tokens"]
    cost = (
        usage["prompt_tokens"] * _COST_PER_M_INPUT / 1_000_000
        + usage["completion_tokens"] * _COST_PER_M_OUTPUT / 1_000_000
    )
    return {
        "total_calls": usage["calls"],
        "prompt_tokens": usage["prompt_tokens"],
        "completion_tokens": usage["completion_tokens"],
        "total_tokens": total,
        "estimated_cost_usd": round(cost, 4),
        "model": LLM_MODEL,
        "provider": LLM_BASE_URL,
    }


def get_usage_stats() -> dict:
    """Return cumulative token usage and estimated cost (all sessions)."""
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


_coding_client: Optional[httpx.AsyncClient] = None


def _get_coding_client() -> httpx.AsyncClient:
    """Return a reusable async HTTP client for the coding LLM."""
    global _coding_client
    if _coding_client is None or _coding_client.is_closed:
        headers = {}
        if _LLM_API_KEY:
            headers["Authorization"] = f"Bearer {_LLM_API_KEY}"
        _coding_client = httpx.AsyncClient(timeout=LLM_TIMEOUT, headers=headers)
    return _coding_client


async def shutdown() -> None:
    """Close the HTTP clients. Call during application shutdown."""
    global _client, _coding_client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
    if _coding_client is not None and not _coding_client.is_closed:
        await _coding_client.aclose()
        _coding_client = None


def get_llm_config() -> dict:
    """Return current LLM configuration."""
    return {
        "provider": _detect_provider(),
        "base_url": LLM_BASE_URL,
        "model": LLM_MODEL,
        "api_key": "***" if _LLM_API_KEY else "",
    }


def _detect_provider() -> str:
    """Best-effort provider detection from base URL."""
    if "openrouter.ai" in LLM_BASE_URL:
        return "openrouter"
    if "11434" in LLM_BASE_URL:
        return "ollama"
    if "aiplatform.googleapis.com" in LLM_BASE_URL:
        return "vertex_ai"
    return "vllm_local"


def update_llm_config(provider: str, base_url: str, model: str, api_key: str = "") -> None:
    """Hot-swap LLM provider at runtime. Recreates the HTTP client."""
    global LLM_BASE_URL, LLM_MODEL, _LLM_API_KEY, _client
    LLM_BASE_URL = base_url
    LLM_MODEL = model
    _LLM_API_KEY = api_key if api_key else None
    # Force client recreation with new auth headers
    if _client is not None and not _client.is_closed:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_client.aclose())
            else:
                loop.run_until_complete(_client.aclose())
        except Exception:
            pass
    _client = None
    logger.info("LLM config updated: provider=%s base_url=%s model=%s", provider, base_url, model)


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

        # Track token usage (global + per-session)
        usage = data.get("usage", {})
        p_tok = usage.get("prompt_tokens", 0)
        c_tok = usage.get("completion_tokens", 0)
        _total_prompt_tokens += p_tok
        _total_completion_tokens += c_tok
        _total_calls += 1
        if _active_session_id and _active_session_id in _session_usage:
            s = _session_usage[_active_session_id]
            s["prompt_tokens"] += p_tok
            s["completion_tokens"] += c_tok
            s["calls"] += 1

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

    # Try to find a JSON array [ ... ]
    bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
    if bracket_match:
        try:
            parsed = json.loads(bracket_match.group())
            if isinstance(parsed, list):
                return parsed
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
    logger.warning("Could not parse JSON from LLM response (len=%d, first 200: %s), returning raw text", len(text), repr(text[:200]))
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


async def call_coding_llm_json(
    prompt: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict:
    """Send a coding prompt to the 4B model and parse response as JSON.

    MedGemma-1.5-4b-it outperforms 27B on structured ICD-10/CPT extraction.
    Falls back to primary LLM if coding LLM is unavailable.
    """
    payload = {
        "model": CODING_LLM_MODEL,
        "messages": _build_messages(prompt),
        "temperature": temperature if temperature is not None else 0.0,
        "max_tokens": max_tokens or CODING_LLM_MAX_TOKENS,
    }

    try:
        client = _get_coding_client()
        resp = await client.post(
            f"{CODING_LLM_BASE_URL}/chat/completions", json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]

        # Track usage
        usage = data.get("usage", {})
        global _total_prompt_tokens, _total_completion_tokens, _total_calls
        _total_prompt_tokens += usage.get("prompt_tokens", 0)
        _total_completion_tokens += usage.get("completion_tokens", 0)
        _total_calls += 1

        return _extract_json(raw)
    except Exception as exc:
        logger.warning("Coding LLM (%s) failed, falling back to primary: %s", CODING_LLM_MODEL, exc)
        return await call_medgemma_json(prompt, temperature=temperature, max_tokens=max_tokens)
