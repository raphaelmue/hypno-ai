"""OpenAI and OpenAI-compatible LLM provider."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator

_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
    """Calls the OpenAI Chat Completions API or any OpenAI-compatible endpoint.

    Passing a custom ``base_url`` covers LM Studio, vLLM, llama.cpp server, etc.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            return False

    def _build_request(
        self, system_prompt: str, user_prompt: str, stream: bool
    ) -> urllib.request.Request:
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": stream,
            }
        ).encode()
        return urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        req = self._build_request(system_prompt, user_prompt, stream=False)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc
        return data["choices"][0]["message"]["content"]

    def stream_generate(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        req = self._build_request(system_prompt, user_prompt, stream=True)
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode().strip()
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    if content := delta.get("content", ""):
                        yield content
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI stream failed: {exc}") from exc
