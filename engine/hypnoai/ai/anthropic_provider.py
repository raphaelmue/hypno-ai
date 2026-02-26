"""Anthropic Claude LLM provider."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicProvider:
    """Calls the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        if not api_key:
            raise ValueError("Anthropic API key is required")
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "anthropic"

    def is_available(self) -> bool:
        # The Anthropic API has no cheap ping endpoint; availability means the key is set.
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-Key": self._api_key,
            "anthropic-version": _API_VERSION,
        }

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self._model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }
        ).encode()
        req = urllib.request.Request(_API_URL, data=payload, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Anthropic request failed: {exc}") from exc
        return data["content"][0]["text"]

    def stream_generate(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        payload = json.dumps(
            {
                "model": self._model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "stream": True,
            }
        ).encode()
        req = urllib.request.Request(_API_URL, data=payload, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode().strip()
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    if event.get("type") == "content_block_delta":
                        if text := event.get("delta", {}).get("text", ""):
                            yield text
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Anthropic stream failed: {exc}") from exc
