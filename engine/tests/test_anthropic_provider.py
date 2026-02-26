"""Tests for the Anthropic Claude LLM provider."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from hypnoai.ai.anthropic_provider import AnthropicProvider


def _mock_response(body: bytes) -> MagicMock:
    resp = MagicMock()
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


class TestAnthropicProvider:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="API key"):
            AnthropicProvider(api_key="")

    def test_name(self):
        p = AnthropicProvider(api_key="sk-ant-test")
        assert p.name == "anthropic"

    def test_default_model(self):
        p = AnthropicProvider(api_key="sk-ant-test")
        assert "claude" in p._model

    def test_is_available_true_when_key_set(self):
        p = AnthropicProvider(api_key="sk-ant-test")
        assert p.is_available() is True

    def test_headers_contain_api_key_and_version(self):
        p = AnthropicProvider(api_key="my-key")
        headers = p._headers()
        assert headers["X-API-Key"] == "my-key"
        assert "anthropic-version" in headers

    def test_generate_returns_content(self):
        p = AnthropicProvider(api_key="sk-ant-test")
        body = json.dumps({
            "content": [{"type": "text", "text": "Generated hypno script"}]
        }).encode()
        resp = _mock_response(body)
        with patch("urllib.request.urlopen", return_value=resp):
            result = p.generate("sys", "user")
        assert result == "Generated hypno script"

    def test_generate_raises_on_network_error(self):
        import urllib.error
        p = AnthropicProvider(api_key="sk-ant-test")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("bad")):
            with pytest.raises(RuntimeError, match="Anthropic request failed"):
                p.generate("sys", "user")

    def test_stream_generate_yields_text_deltas(self):
        p = AnthropicProvider(api_key="sk-ant-test")
        lines = [
            'data: ' + json.dumps({"type": "content_block_delta", "delta": {"text": "Hello "}}) + "\n",
            'data: ' + json.dumps({"type": "content_block_delta", "delta": {"text": "world"}}) + "\n",
            'data: ' + json.dumps({"type": "message_stop"}) + "\n",
        ]
        resp = _mock_streaming_response(lines)
        with patch("urllib.request.urlopen", return_value=resp):
            tokens = list(p.stream_generate("sys", "user"))
        assert tokens == ["Hello ", "world"]

    def test_stream_generate_skips_non_delta_events(self):
        p = AnthropicProvider(api_key="sk-ant-test")
        lines = [
            'data: ' + json.dumps({"type": "message_start", "message": {}}) + "\n",
            'data: ' + json.dumps({"type": "content_block_delta", "delta": {"text": "Token"}}) + "\n",
            'data: ' + json.dumps({"type": "message_stop"}) + "\n",
        ]
        resp = _mock_streaming_response(lines)
        with patch("urllib.request.urlopen", return_value=resp):
            tokens = list(p.stream_generate("sys", "user"))
        assert tokens == ["Token"]

    def test_stream_generate_raises_on_network_error(self):
        import urllib.error
        p = AnthropicProvider(api_key="sk-ant-test")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("gone")):
            with pytest.raises(RuntimeError, match="Anthropic stream failed"):
                list(p.stream_generate("sys", "user"))

    def test_custom_model(self):
        p = AnthropicProvider(api_key="sk-ant-test", model="claude-opus-4-6")
        assert p._model == "claude-opus-4-6"
