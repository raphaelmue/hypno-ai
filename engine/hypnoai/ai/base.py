"""LLM provider protocol and shared data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol, runtime_checkable


@dataclass
class ScriptGenerationRequest:
    """Parameters for AI script generation."""

    template_id: str
    language: str = "en"
    duration_minutes: int = 20
    theme: str = "relaxation"
    variables: dict[str, str] = field(default_factory=dict)
    session_type: str = "relaxation"


@dataclass
class GenerationResult:
    """Result of AI script generation after post-processing."""

    script: str
    warnings: list[str] = field(default_factory=list)
    estimated_duration_minutes: float = 0.0
    fast_pace_paragraphs: list[int] = field(default_factory=list)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that all LLM provider adapters must satisfy."""

    @property
    def name(self) -> str:
        """Provider name, e.g. 'ollama', 'openai', 'anthropic'."""
        ...

    def is_available(self) -> bool:
        """Return True if the provider is reachable and configured."""
        ...

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a complete response synchronously."""
        ...

    def stream_generate(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Yield response tokens/chunks as they arrive."""
        ...
