"""Tests for the `hypnoai generate` CLI command."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from hypnoai.cli import app

runner = CliRunner()

_SAMPLE_SCRIPT = """\
@{section: Induction}

Allow yourself to relax and breathe deeply.

@{pause: 3s}

@{section: Emergence}

Slowly returning. Wide awake. Open your eyes.
"""


class _MockProvider:
    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return _SAMPLE_SCRIPT

    def stream_generate(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        yield _SAMPLE_SCRIPT


class _UnavailableProvider:
    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return False

    def generate(self, *a) -> str:
        return ""

    def stream_generate(self, *a) -> Iterator[str]:
        yield ""


class TestGenerateListTemplates:
    def test_list_templates_exits_0(self):
        result = runner.invoke(app, ["generate", "--list-templates"])
        assert result.exit_code == 0

    def test_list_templates_shows_custom(self):
        result = runner.invoke(app, ["generate", "--list-templates"])
        assert "custom" in result.output

    def test_list_templates_shows_all_categories(self):
        result = runner.invoke(app, ["generate", "--list-templates"])
        for name in ("relaxation", "sleep", "focus", "habit", "anxiety"):
            assert name in result.output


class TestGenerateCommand:
    def _invoke_generate(self, extra_args=None, config_path=None, tmp_path=None):
        args = ["generate", "--template", "custom", "--theme", "test theme"]
        if config_path:
            args += ["--config", str(config_path)]
        if extra_args:
            args += extra_args
        return runner.invoke(app, args)

    def _make_config(self, tmp_path: Path) -> Path:
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()
        cfg = tmp_path / "hypnoai.toml"
        cfg.write_text(
            f'voices_dir = "{voices_dir.as_posix()}"\n'
            'llm_provider = "ollama"\n',
            encoding="utf-8",
        )
        return cfg

    def test_generates_with_mock_provider(self, tmp_path):
        cfg = self._make_config(tmp_path)
        with patch("hypnoai.cli._build_llm_provider", return_value=_MockProvider()):
            result = runner.invoke(
                app,
                ["generate", "--template", "custom", "--theme", "relaxation",
                 "--config", str(cfg)],
            )
        assert result.exit_code == 0
        assert "Induction" in result.output or "relax" in result.output.lower()

    def test_unknown_template_exits_1(self, tmp_path):
        cfg = self._make_config(tmp_path)
        result = runner.invoke(
            app,
            ["generate", "--template", "nonexistent", "--config", str(cfg)],
        )
        assert result.exit_code == 1

    def test_unavailable_provider_exits_1(self, tmp_path):
        cfg = self._make_config(tmp_path)
        with patch("hypnoai.cli._build_llm_provider", return_value=_UnavailableProvider()):
            result = runner.invoke(
                app,
                ["generate", "--template", "custom", "--theme", "test",
                 "--config", str(cfg)],
            )
        assert result.exit_code == 1

    def test_invalid_var_format_exits_1(self, tmp_path):
        cfg = self._make_config(tmp_path)
        result = runner.invoke(
            app,
            ["generate", "--template", "custom", "--var", "NOEQUALS",
             "--config", str(cfg)],
        )
        assert result.exit_code == 1

    def test_output_file_written(self, tmp_path):
        cfg = self._make_config(tmp_path)
        out = tmp_path / "generated.hypno"
        with patch("hypnoai.cli._build_llm_provider", return_value=_MockProvider()):
            result = runner.invoke(
                app,
                ["generate", "--template", "custom", "--theme", "relaxation",
                 "--output", str(out), "--config", str(cfg)],
            )
        assert result.exit_code == 0
        assert out.exists()
        assert "relax" in out.read_text(encoding="utf-8").lower()

    def test_output_file_shows_saved_message(self, tmp_path):
        cfg = self._make_config(tmp_path)
        out = tmp_path / "out.hypno"
        with patch("hypnoai.cli._build_llm_provider", return_value=_MockProvider()):
            result = runner.invoke(
                app,
                ["generate", "--template", "custom", "--theme", "test",
                 "--output", str(out), "--config", str(cfg)],
            )
        assert "Saved" in result.output or str(out.name) in result.output

    def test_missing_openai_key_exits_1(self, tmp_path):
        cfg = tmp_path / "hypnoai.toml"
        cfg.write_text("openai_api_key = \"\"\n", encoding="utf-8")
        result = runner.invoke(
            app,
            ["generate", "--template", "custom", "--provider", "openai",
             "--config", str(cfg)],
        )
        assert result.exit_code == 1

    def test_missing_anthropic_key_exits_1(self, tmp_path):
        cfg = tmp_path / "hypnoai.toml"
        cfg.write_text("anthropic_api_key = \"\"\n", encoding="utf-8")
        result = runner.invoke(
            app,
            ["generate", "--template", "custom", "--provider", "anthropic",
             "--config", str(cfg)],
        )
        assert result.exit_code == 1

    def test_unknown_provider_exits_1(self, tmp_path):
        cfg = self._make_config(tmp_path)
        result = runner.invoke(
            app,
            ["generate", "--template", "custom", "--provider", "nonexistent",
             "--config", str(cfg)],
        )
        assert result.exit_code == 1

    def test_var_name_passed_as_hypnoscript_variable(self, tmp_path):
        """{{name}} is preserved as a HypnoScript variable in the prompt;
        --var name=Bob is for render-time injection, not generation-time substitution."""
        cfg = self._make_config(tmp_path)
        captured = {}

        class CapturingProvider(_MockProvider):
            def generate(self, system_prompt, user_prompt):
                captured["user"] = user_prompt
                return _SAMPLE_SCRIPT

        with patch("hypnoai.cli._build_llm_provider", return_value=CapturingProvider()):
            runner.invoke(
                app,
                ["generate", "--template", "custom", "--theme", "test",
                 "--var", "name=Bob", "--config", str(cfg)],
            )
        # {{name}} is preserved as-is in the prompt so the LLM learns the variable syntax
        assert "{{name}}" in captured.get("user", "")

    def test_duration_passed_to_provider(self, tmp_path):
        cfg = self._make_config(tmp_path)
        captured = {}

        class CapturingProvider(_MockProvider):
            def generate(self, system_prompt, user_prompt):
                captured["user"] = user_prompt
                return _SAMPLE_SCRIPT

        with patch("hypnoai.cli._build_llm_provider", return_value=CapturingProvider()):
            runner.invoke(
                app,
                ["generate", "--template", "custom", "--duration", "35",
                 "--config", str(cfg)],
            )
        assert "35" in captured.get("user", "")


class TestBuildLlmProvider:
    def test_ollama_provider_returned(self, tmp_path):
        from hypnoai.ai.ollama_provider import OllamaProvider
        from hypnoai.cli import _build_llm_provider
        from hypnoai.config import Config

        cfg = Config()
        provider = _build_llm_provider("ollama", cfg)
        assert isinstance(provider, OllamaProvider)

    def test_openai_provider_returned_with_key(self, tmp_path):
        from hypnoai.ai.openai_provider import OpenAIProvider
        from hypnoai.cli import _build_llm_provider
        from hypnoai.config import Config

        cfg = Config()
        cfg.openai_api_key = "sk-test"
        provider = _build_llm_provider("openai", cfg)
        assert isinstance(provider, OpenAIProvider)

    def test_anthropic_provider_returned_with_key(self, tmp_path):
        from hypnoai.ai.anthropic_provider import AnthropicProvider
        from hypnoai.cli import _build_llm_provider
        from hypnoai.config import Config

        cfg = Config()
        cfg.anthropic_api_key = "sk-ant-test"
        provider = _build_llm_provider("anthropic", cfg)
        assert isinstance(provider, AnthropicProvider)

    def test_raises_for_unknown_provider(self):
        from hypnoai.cli import _build_llm_provider
        from hypnoai.config import Config

        cfg = Config()
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            _build_llm_provider("unknown_llm", cfg)
