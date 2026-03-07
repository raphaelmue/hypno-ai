"""Ollama local LLM provider."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator


class OllamaProvider:
    """Calls a local Ollama instance via its HTTP REST API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self._base_url}/api/tags", timeout=3):
                return True
        except Exception:
            return False

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a complete response (non-streaming)."""
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        return data["message"]["content"]

    def stream_generate(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Yield response tokens as they stream from Ollama."""
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": True,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if line.strip():
                        chunk = json.loads(line)
                        if token := chunk.get("message", {}).get("content", ""):
                            yield token
                        if chunk.get("done"):
                            break
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama stream failed: {exc}") from exc
