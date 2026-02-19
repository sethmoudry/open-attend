"""Tests for the LLM client module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from llm import _build_messages, _extract_json, call_medgemma


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_clean_json(self):
        result = _extract_json('{"key": "value", "n": 42}')
        assert result == {"key": "value", "n": 42}

    def test_fenced_json(self):
        text = '```json\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_fenced_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_embedded_in_prose(self):
        text = 'Here is the result: {"key": "value"} as requested.'
        result = _extract_json(text)
        assert result == {"key": "value"}

    def test_fallback_raw(self):
        result = _extract_json("not json at all")
        assert "_raw" in result
        assert result["_raw"] == "not json at all"

    def test_nested_json(self):
        data = {"outer": {"inner": [1, 2, 3]}}
        result = _extract_json(json.dumps(data))
        assert result == data


# ---------------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_user_only(self):
        msgs = _build_messages("hello")
        assert len(msgs) == 1
        assert msgs[0] == {"role": "user", "content": "hello"}

    def test_with_system(self):
        msgs = _build_messages("hello", system_prompt="you are helpful")
        assert len(msgs) == 2
        assert msgs[0] == {"role": "system", "content": "you are helpful"}
        assert msgs[1] == {"role": "user", "content": "hello"}

    def test_no_system_when_none(self):
        msgs = _build_messages("hello", system_prompt=None)
        assert len(msgs) == 1


# ---------------------------------------------------------------------------
# call_medgemma
# ---------------------------------------------------------------------------


class TestCallMedgemma:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test response"}}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch("llm._client", mock_client):
            result = await call_medgemma("test prompt")
            assert result == "test response"

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.is_closed = False

        with patch("llm._client", mock_client):
            with pytest.raises(httpx.TimeoutException):
                await call_medgemma("test prompt")
