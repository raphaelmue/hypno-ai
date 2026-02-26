"""Tests for the Ollama LLM provider."""
from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from hypnoai.ai.ollama_provider import OllamaProvider


def _mock_response(body: bytes, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_streaming_response(lines: list[bytes]) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.__iter__ = MagicMock(return_value=iter(lines))
    return resp


class TestOllamaProvider:
    def test_name(self):
        p = OllamaProvider()
        assert p.name == "ollama"

    def test_default_url_and_model(self):
        p = OllamaProvider()
        assert "11434" in p._base_url
        assert p._model == "llama3.1"

    def test_custom_url_and_model(self):
        p = OllamaProvider(base_url="http://myhost:9999", model="mistral")
        assert "9999" in p._base_url
        assert p._model == "mistral"

    def test_trailing_slash_stripped(self):
        p = OllamaProvider(base_url="http://localhost:11434/")
        assert not p._base_url.endswith("/")

    def test_is_available_true(self):
        p = OllamaProvider()
        resp = _mock_response(b'{"models":[]}')
        with patch("urllib.request.urlopen", return_value=resp):
            assert p.is_available() is True

    def test_is_available_false_on_error(self):
        p = OllamaProvider()
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            assert p.is_available() is False

    def test_generate_returns_content(self):
        p = OllamaProvider()
        body = json.dumps({"message": {"content": "Hello script!"}, "done": True}).encode()
        resp = _mock_response(body)
        with patch("urllib.request.urlopen", return_value=resp):
            result = p.generate("sys", "user")
        assert result == "Hello script!"

    def test_generate_raises_on_network_error(self):
        import urllib.error
        p = OllamaProvider()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("unreachable")):
            with pytest.raises(RuntimeError, match="Ollama request failed"):
                p.generate("sys", "user")

    def test_stream_generate_yields_tokens(self):
        p = OllamaProvider()
        lines = [
            json.dumps({"message": {"content": "Hello "}, "done": False}).encode(),
            json.dumps({"message": {"content": "world"}, "done": False}).encode(),
            json.dumps({"message": {"content": ""}, "done": True}).encode(),
        ]
        resp = _mock_streaming_response(lines)
        with patch("urllib.request.urlopen", return_value=resp):
            tokens = list(p.stream_generate("sys", "user"))
        assert tokens == ["Hello ", "world"]

    def test_stream_generate_raises_on_network_error(self):
        import urllib.error
        p = OllamaProvider()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("gone")):
            with pytest.raises(RuntimeError, match="Ollama stream failed"):
                list(p.stream_generate("sys", "user"))

    def test_stream_generate_stops_at_done(self):
        p = OllamaProvider()
        lines = [
            json.dumps({"message": {"content": "Token1"}, "done": True}).encode(),
            # This line should never be reached
            json.dumps({"message": {"content": "Token2"}, "done": False}).encode(),
        ]
        resp = _mock_streaming_response(lines)
        with patch("urllib.request.urlopen", return_value=resp):
            tokens = list(p.stream_generate("sys", "user"))
        assert tokens == ["Token1"]
