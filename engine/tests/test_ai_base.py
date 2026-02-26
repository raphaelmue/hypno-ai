"""Tests for the AI base protocol and dataclasses."""
from __future__ import annotations

from hypnoai.ai.base import GenerationResult, LLMProvider, ScriptGenerationRequest


class TestScriptGenerationRequest:
    def test_defaults(self):
        req = ScriptGenerationRequest(template_id="custom")
        assert req.language == "en"
        assert req.duration_minutes == 20
        assert req.theme == "relaxation"
        assert req.variables == {}
        assert req.session_type == "relaxation"

    def test_custom_values(self):
        req = ScriptGenerationRequest(
            template_id="sleep_induction",
            language="de",
            duration_minutes=30,
            theme="stress relief",
            variables={"name": "Alice"},
        )
        assert req.template_id == "sleep_induction"
        assert req.language == "de"
        assert req.duration_minutes == 30
        assert req.variables == {"name": "Alice"}


class TestGenerationResult:
    def test_defaults(self):
        result = GenerationResult(script="Hello world.")
        assert result.warnings == []
        assert result.estimated_duration_minutes == 0.0
        assert result.fast_pace_paragraphs == []

    def test_with_warnings(self):
        result = GenerationResult(
            script="Test script.",
            warnings=["Warning 1", "Warning 2"],
            estimated_duration_minutes=5.0,
        )
        assert len(result.warnings) == 2
        assert result.estimated_duration_minutes == 5.0


class TestLLMProviderProtocol:
    def test_protocol_satisfied_by_mock(self):
        """A minimal mock should satisfy the LLMProvider runtime-checkable Protocol."""

        class MockProvider:
            @property
            def name(self) -> str:
                return "mock"

            def is_available(self) -> bool:
                return True

            def generate(self, system_prompt: str, user_prompt: str) -> str:
                return "generated script"

            def stream_generate(self, system_prompt: str, user_prompt: str):
                yield "chunk"

        provider = MockProvider()
        assert isinstance(provider, LLMProvider)

    def test_protocol_not_satisfied_by_incomplete_class(self):
        """A class missing required methods should not satisfy the Protocol."""

        class Incomplete:
            @property
            def name(self) -> str:
                return "incomplete"
            # Missing is_available, generate, stream_generate

        assert not isinstance(Incomplete(), LLMProvider)
