"""Tests for the OpenAI-compatible LLM provider."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from hypnoai.ai.openai_provider import OpenAIProvider


def _mock_response(body: bytes, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_streaming_response(lines: list[str]) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.__iter__ = MagicMock(return_value=iter(ln.encode() for ln in lines))
    return resp


class TestOpenAIProvider:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="API key"):
            OpenAIProvider(api_key="")

    def test_name(self):
        p = OpenAIProvider(api_key="sk-test")
        assert p.name == "openai"

    def test_default_model_and_url(self):
        p = OpenAIProvider(api_key="sk-test")
        assert p._model == "gpt-4o-mini"
        assert "openai.com" in p._base_url

    def test_custom_base_url(self):
        p = OpenAIProvider(api_key="sk-test", base_url="http://localhost:1234/v1")
        assert "localhost" in p._base_url

    def test_trailing_slash_stripped(self):
        p = OpenAIProvider(api_key="sk-test", base_url="http://localhost:1234/v1/")
        assert not p._base_url.endswith("/")

    def test_is_available_true(self):
        p = OpenAIProvider(api_key="sk-test")
        resp = _mock_response(b'{"object":"list","data":[]}')
        with patch("urllib.request.urlopen", return_value=resp):
            assert p.is_available() is True

    def test_is_available_false_on_error(self):
        p = OpenAIProvider(api_key="sk-test")
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            assert p.is_available() is False

    def test_generate_returns_content(self):
        p = OpenAIProvider(api_key="sk-test")
        body = json.dumps({
            "choices": [{"message": {"content": "Generated script"}}]
        }).encode()
        resp = _mock_response(body)
        with patch("urllib.request.urlopen", return_value=resp):
            result = p.generate("sys", "user")
        assert result == "Generated script"

    def test_generate_raises_on_network_error(self):
        import urllib.error
        p = OpenAIProvider(api_key="sk-test")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("bad")):
            with pytest.raises(RuntimeError, match="OpenAI request failed"):
                p.generate("sys", "user")

    def test_stream_generate_yields_tokens(self):
        p = OpenAIProvider(api_key="sk-test")
        lines = [
            'data: ' + json.dumps({"choices": [{"delta": {"content": "Hello "}}]}) + "\n",
            'data: ' + json.dumps({"choices": [{"delta": {"content": "world"}}]}) + "\n",
            "data: [DONE]\n",
        ]
        resp = _mock_streaming_response(lines)
        with patch("urllib.request.urlopen", return_value=resp):
            tokens = list(p.stream_generate("sys", "user"))
        assert tokens == ["Hello ", "world"]

    def test_stream_generate_skips_non_data_lines(self):
        p = OpenAIProvider(api_key="sk-test")
        lines = [
            ": keep-alive\n",
            'data: ' + json.dumps({"choices": [{"delta": {"content": "Token"}}]}) + "\n",
            "data: [DONE]\n",
        ]
        resp = _mock_streaming_response(lines)
        with patch("urllib.request.urlopen", return_value=resp):
            tokens = list(p.stream_generate("sys", "user"))
        assert tokens == ["Token"]

    def test_stream_generate_raises_on_network_error(self):
        import urllib.error
        p = OpenAIProvider(api_key="sk-test")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("gone")):
            with pytest.raises(RuntimeError, match="OpenAI stream failed"):
                list(p.stream_generate("sys", "user"))

    def test_openai_compat_uses_custom_url(self):
        """Verifies that a custom base_url is actually used in requests."""
        p = OpenAIProvider(
            api_key="local-key",
            model="local-model",
            base_url="http://localhost:1234/v1",
        )
        req = p._build_request("sys", "user", stream=False)
        assert "localhost:1234" in req.full_url
