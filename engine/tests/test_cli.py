"""Tests for the HypnoAI CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypnoai.cli import app
from typer.testing import CliRunner

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_script(tmp_path: Path) -> Path:
    script = tmp_path / "test.hypno"
    script.write_text("Hello world.\n\nGoodbye world.", encoding="utf-8")
    return script


@pytest.fixture
def script_with_directives(tmp_path: Path) -> Path:
    script = tmp_path / "test.hypno"
    script.write_text(
        "@{comment: Test}\n"
        "@{voice: calm}\n"
        "@{speed: 0.85}\n"
        "@{section: Intro}\n"
        "\n"
        "Hello.\n"
        "\n"
        "@{pause: 2s}\n"
        "\n"
        "Goodbye.",
        encoding="utf-8",
    )
    return script


def _toml_path(p: Path) -> str:
    """Return a TOML-safe path string (forward slashes, no escaping issues)."""
    return p.as_posix()


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    cfg = tmp_path / "hypnoai.toml"
    cfg.write_text(f'voices_dir = "{_toml_path(voices_dir)}"\n', encoding="utf-8")
    return cfg


@pytest.fixture
def config_with_voice(tmp_path: Path) -> tuple[Path, Path]:
    """Returns (config_path, voices_dir) with a fake voice installed."""
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "en_US-amy-medium.onnx").write_bytes(b"\x00")
    (voices_dir / "en_US-amy-medium.onnx.json").write_text(
        json.dumps({"audio": {"sample_rate": 22050}})
    )
    cfg = tmp_path / "hypnoai.toml"
    cfg.write_text(f'voices_dir = "{_toml_path(voices_dir)}"\n', encoding="utf-8")
    return cfg, voices_dir


# ---------------------------------------------------------------------------
# lint command
# ---------------------------------------------------------------------------


class TestLintCommand:
    def test_lint_valid_script(self, simple_script):
        result = runner.invoke(app, ["lint", str(simple_script)])
        assert result.exit_code == 0
        assert "Paragraphs" in result.output

    def test_lint_shows_paragraph_count(self, simple_script):
        result = runner.invoke(app, ["lint", str(simple_script)])
        assert "2" in result.output  # two paragraphs

    def test_lint_full_script(self, script_with_directives):
        result = runner.invoke(app, ["lint", str(script_with_directives)])
        assert result.exit_code == 0
        assert "Pauses" in result.output
        assert "Sections" in result.output

    def test_lint_missing_file_exits_1(self, tmp_path):
        result = runner.invoke(app, ["lint", str(tmp_path / "nonexistent.hypno")])
        assert result.exit_code == 1

    def test_lint_shows_variables(self, tmp_path):
        script = tmp_path / "test.hypno"
        script.write_text("Hello {{name}}, welcome to {{place}}.", encoding="utf-8")
        result = runner.invoke(app, ["lint", str(script)])
        assert result.exit_code == 0
        assert "name" in result.output
        assert "place" in result.output

    def test_lint_duration_estimate_includes_pause(self, tmp_path):
        script = tmp_path / "test.hypno"
        script.write_text("@{pause: 120s}\n\nHello.", encoding="utf-8")
        result = runner.invoke(app, ["lint", str(script)])
        assert result.exit_code == 0
        # 120s pause → at least 2m shown
        assert "2m" in result.output

    def test_lint_no_issues_message(self, simple_script):
        result = runner.invoke(app, ["lint", str(simple_script)])
        assert "No issues" in result.output

    def test_lint_warns_on_unknown_directive(self, tmp_path):
        script = tmp_path / "test.hypno"
        script.write_text("@{unknowndirective: value}\n\nHello.", encoding="utf-8")
        result = runner.invoke(app, ["lint", str(script)])
        assert result.exit_code == 0
        assert "Warning" in result.output or "warning" in result.output.lower()

    def test_lint_with_config(self, simple_script, config_file):
        result = runner.invoke(
            app, ["lint", str(simple_script), "--config", str(config_file)]
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# voices command
# ---------------------------------------------------------------------------


class TestVoicesCommand:
    def test_voices_no_models_installed(self, config_file):
        result = runner.invoke(app, ["voices", "list", "--config", str(config_file)])
        assert result.exit_code == 0
        # Should say no voices found
        assert "No voices" in result.output or "no voices" in result.output.lower()

    def test_voices_shows_installed_model(self, config_with_voice):
        config_path, _ = config_with_voice
        result = runner.invoke(app, ["voices", "list", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.output

    def test_voices_shows_engine_filter(self, config_with_voice):
        config_path, _ = config_with_voice
        result = runner.invoke(
            app, ["voices", "list", "--engine", "piper", "--config", str(config_path)]
        )
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.output

    def test_voices_empty_for_unknown_engine(self, config_with_voice):
        config_path, _ = config_with_voice
        result = runner.invoke(
            app, ["voices", "list", "--engine", "coqui", "--config", str(config_path)]
        )
        assert result.exit_code == 0
        assert "No voices" in result.output or "en_US-amy-medium" not in result.output


class TestVoicesAdd:
    def test_add_coqui_voice_with_reference(self, tmp_path, config_file):
        """Copying a reference wav into voices_dir for coqui engine."""
        ref = tmp_path / "speaker.wav"
        ref.write_bytes(b"\x00" * 100)
        result = runner.invoke(
            app,
            [
                "voices", "add", "my_speaker", str(ref),
                "--engine", "coqui",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 0
        assert "my_speaker" in result.output

    def test_add_coqui_voice_without_reference_exits_1(self, config_file):
        """Cloning engines require a reference wav."""
        result = runner.invoke(
            app,
            [
                "voices", "add", "my_speaker",
                "--engine", "coqui",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 1

    def test_add_unknown_engine_exits_1(self, config_file):
        result = runner.invoke(
            app,
            ["voices", "add", "test", "--engine", "unknownengine", "--config", str(config_file)],
        )
        assert result.exit_code == 1

    def test_add_piper_voice_calls_download(self, tmp_path, config_file):
        """voices add for piper should call PiperVoiceManager.add_voice (download)."""
        from unittest.mock import patch
        from hypnoai.resources.voice_manager import PiperVoiceManager
        from hypnoai.tts.base import VoiceInfo

        mock_voice = VoiceInfo(
            id="en_US-ryan-medium", name="Ryan", language="en_US",
            quality="medium", engine="piper",
        )
        with patch.object(PiperVoiceManager, "add_voice", return_value=mock_voice) as mock_add:
            result = runner.invoke(
                app,
                [
                    "voices", "add", "en_US-ryan-medium",
                    "--engine", "piper",
                    "--config", str(config_file),
                ],
            )
        assert result.exit_code == 0
        mock_add.assert_called_once_with("en_US-ryan-medium", None)

    def test_add_kokoro_voice_exits_1(self, config_file):
        """Preset engines (kokoro, bark) do not support custom voices."""
        result = runner.invoke(
            app,
            ["voices", "add", "af_bella", "--engine", "kokoro", "--config", str(config_file)],
        )
        assert result.exit_code == 1
        assert "no custom voice support" in result.output.lower() or "Error" in result.output


class TestVoicesRemove:
    def test_remove_piper_voice_found(self, tmp_path, config_with_voice):
        config_path, voices_dir = config_with_voice
        # en_US-amy-medium is already installed by config_with_voice fixture
        result = runner.invoke(
            app,
            [
                "voices", "remove", "en_US-amy-medium",
                "--engine", "piper",
                "--config", str(config_path),
            ],
        )
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_remove_piper_voice_not_found_exits_1(self, config_file):
        result = runner.invoke(
            app,
            [
                "voices", "remove", "en_US-nobody-medium",
                "--engine", "piper",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 1

    def test_remove_coqui_voice(self, tmp_path, config_file):
        """Remove a .wav reference clip from coqui voices."""
        # Write a wav into the voices dir (which config_file creates)
        from hypnoai.config import Config
        cfg = Config.load(config_file)
        wav = cfg.voices_dir / "speaker1.wav"
        wav.write_bytes(b"\x00" * 100)

        result = runner.invoke(
            app,
            [
                "voices", "remove", "speaker1",
                "--engine", "coqui",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 0
        assert not wav.exists()

    def test_remove_bark_voice_exits_1(self, config_file):
        """Preset engines raise NotImplementedError on remove."""
        result = runner.invoke(
            app,
            [
                "voices", "remove", "v2/en_speaker_0",
                "--engine", "bark",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# render command (argument validation only — no real TTS binary required)
# ---------------------------------------------------------------------------


class TestRenderCommand:
    def test_render_missing_script_exits_1(self, tmp_path, config_file):
        result = runner.invoke(
            app,
            ["render", str(tmp_path / "missing.hypno"), "--config", str(config_file)],
        )
        assert result.exit_code == 1

    def test_render_invalid_var_format_exits_1(self, simple_script, config_file):
        result = runner.invoke(
            app,
            [
                "render",
                str(simple_script),
                "--var", "NOEQUALS",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 1

    def test_render_unsupported_engine_exits_1(self, simple_script, config_file):
        result = runner.invoke(
            app,
            [
                "render",
                str(simple_script),
                "--engine", "coqui",
                "--config", str(config_file),
            ],
        )
        assert result.exit_code == 1
