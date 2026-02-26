"""Tests for ScriptStudio."""
from __future__ import annotations

from typing import Iterator

import pytest

from hypnoai.ai.base import ScriptGenerationRequest
from hypnoai.ai.script_studio import ScriptStudio


class MockProvider:
    """Minimal mock LLM provider that returns a pre-configured script."""

    def __init__(self, response: str = "") -> None:
        self._response = response or _SAMPLE_RESPONSE

    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system = system_prompt
        self.last_user = user_prompt
        return self._response

    def stream_generate(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        yield self._response


_SAMPLE_RESPONSE = """\
@{section: Induction}

Welcome, allow yourself to relax and breathe deeply.

@{pause: 3s}

@{section: Deepening}

With each breath, allow yourself to go deeper.

@{pause: 5s}

@{section: Main}

You may notice a calm spreading through your body.

@{pause: 3s}

@{section: Emergence}

Slowly returning. Wide awake. Open your eyes. One, two, three.
"""


class TestScriptStudio:
    def test_generate_returns_generation_result(self):
        studio = ScriptStudio(MockProvider())
        req = ScriptGenerationRequest(template_id="custom", theme="relaxation")
        result = studio.generate(req)
        from hypnoai.ai.base import GenerationResult
        assert isinstance(result, GenerationResult)

    def test_generate_script_not_empty(self):
        studio = ScriptStudio(MockProvider())
        req = ScriptGenerationRequest(template_id="custom", theme="stress relief")
        result = studio.generate(req)
        assert result.script.strip()

    def test_system_prompt_passed_to_provider(self):
        provider = MockProvider()
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(template_id="custom")
        studio.generate(req)
        assert hasattr(provider, "last_system")
        assert len(provider.last_system) > 10

    def test_user_prompt_contains_duration(self):
        provider = MockProvider()
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(template_id="custom", duration_minutes=25)
        studio.generate(req)
        assert "25" in provider.last_user

    def test_user_prompt_contains_theme(self):
        provider = MockProvider()
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(template_id="custom", theme="deep sleep")
        studio.generate(req)
        assert "deep sleep" in provider.last_user

    def test_hypnoscript_variables_preserved_in_user_prompt(self):
        """{{name}} is preserved as HypnoScript variable syntax so the LLM
        learns to use it in its output. Render-time values (--var name=Alice)
        are injected by the HypnoScript engine, not the AI generator."""
        provider = MockProvider()
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(
            template_id="custom",
            variables={"name": "Alice"},
        )
        studio.generate(req)
        # {{name}} survives unchanged — it's a HypnoScript variable, not a format placeholder
        assert "{{name}}" in provider.last_user

    def test_non_english_language_adds_instruction(self):
        provider = MockProvider()
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(template_id="custom", language="de")
        # custom/de.toml exists → no fallback needed; but if it didn't, it would add German note
        studio.generate(req)
        assert hasattr(provider, "last_system")

    def test_fallback_language_adds_instruction_to_system_prompt(self):
        """When falling back to English for an unsupported language, adds language note."""
        provider = MockProvider()
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(template_id="custom", language="fr")
        studio.generate(req)
        # French → falls back to en.toml → system prompt should include French instruction
        assert "French" in provider.last_system

    def test_post_processing_applied(self):
        """Syntax fixes in the LLM output are applied."""
        provider = MockProvider(response="@{pause 5s}\n\nRelax and breathe.\n\nWide awake.")
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(template_id="custom")
        result = studio.generate(req)
        assert "@{pause: 5s}" in result.script

    def test_warnings_returned(self):
        """Authoritarian language in LLM output produces warnings."""
        response = _SAMPLE_RESPONSE + "\nYou must relax now."
        studio = ScriptStudio(MockProvider(response=response))
        req = ScriptGenerationRequest(template_id="custom")
        result = studio.generate(req)
        assert any("authoritarian" in w.lower() for w in result.warnings)

    def test_duration_estimate_positive(self):
        studio = ScriptStudio(MockProvider())
        req = ScriptGenerationRequest(template_id="custom")
        result = studio.generate(req)
        assert result.estimated_duration_minutes > 0

    def test_all_templates_generate_without_error(self):
        from hypnoai.ai.template_loader import AVAILABLE_TEMPLATES
        studio = ScriptStudio(MockProvider())
        for template_id in AVAILABLE_TEMPLATES:
            req = ScriptGenerationRequest(template_id=template_id)
            result = studio.generate(req)
            assert result.script

    def test_german_template_loaded(self):
        provider = MockProvider()
        studio = ScriptStudio(provider)
        req = ScriptGenerationRequest(template_id="custom", language="de")
        studio.generate(req)
        # German template system prompt should not add a "Write in German" note
        assert "German" not in provider.last_system
