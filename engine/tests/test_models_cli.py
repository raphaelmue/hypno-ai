"""Tests for the `hypnoai models` CLI sub-app."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypnoai.cli import app
from typer.testing import CliRunner

runner = CliRunner()

_FAKE_PIPER_CATALOG = {
    "en_US-amy-medium": {
        "name": "Amy",
        "language": {"code": "en"},
        "quality": "medium",
        "license": "MIT",
        "files": {
            "en/en_US/amy/medium/en_US-amy-medium.onnx": {"size_bytes": 26_000_000},
            "en/en_US/amy/medium/en_US-amy-medium.onnx.json": {"size_bytes": 5_000},
        },
    },
}


def _make_config(tmp_path: Path) -> Path:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir(exist_ok=True)
    cfg = tmp_path / "hypnoai.toml"
    cfg.write_text(
        f'voices_dir = "{voices_dir.as_posix()}"\n',
        encoding="utf-8",
    )
    return cfg


class TestModelsList:
    def test_list_no_installed_models(self, tmp_path):
        """All GPU engines have no detected installed state — shows empty message."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(app, ["models", "list", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "No models installed" in result.output

    def test_list_available_shows_gpu_engines(self, tmp_path):
        """--available lists all GPU engine entries without any network call."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "list", "--available", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        # Model IDs appear in the (non-truncated) ID column.
        for model_id in ("coqui-xtts-v2", "kokoro-v1.0", "styletts2-libri-tts", "f5-tts", "bark"):
            assert model_id in result.output

    def test_list_available_engine_filter(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "list", "--available", "--engine", "kokoro", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "kokoro" in result.output.lower()
        assert "coqui" not in result.output.lower()

    def test_list_available_unknown_engine_exits_1(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "list", "--available", "--engine", "unknown", "--config", str(cfg)]
        )
        assert result.exit_code == 1

    def test_list_piper_voices_not_shown(self, tmp_path):
        """Piper .onnx files must NOT appear in 'models list' — they belong to 'voices'."""
        cfg = _make_config(tmp_path)
        voices_dir = tmp_path / "voices"
        (voices_dir / "en_US-amy-medium.onnx").write_bytes(b"\x00" * 100)
        (voices_dir / "en_US-amy-medium.onnx.json").write_text(
            json.dumps({"audio": {"sample_rate": 22050}})
        )
        result = runner.invoke(app, ["models", "list", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "en_US-amy-medium" not in result.output


class TestModelsDownload:
    def test_download_gpu_engine_by_name_shows_hint(self, tmp_path):
        """Downloading a GPU engine by name prints install hint (NotImplementedError)."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "download", "coqui", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "pip install" in result.output.lower()

    def test_download_by_engine_flag_shows_hint(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "download", "kokoro", "--engine", "kokoro", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "pip install" in result.output.lower()

    def test_download_piper_voice_id_exits_1(self, tmp_path):
        """Piper voice IDs are no longer handled by 'models download'."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "download", "en_US-amy-medium", "--config", str(cfg)]
        )
        assert result.exit_code == 1

    def test_download_unknown_model_exits_1(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "download", "totally-unknown", "--config", str(cfg)]
        )
        assert result.exit_code == 1

    def test_download_unknown_engine_flag_exits_1(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "download", "anything", "--engine", "nonexistent", "--config", str(cfg)]
        )
        assert result.exit_code == 1


class TestModelsRemove:
    def test_remove_nonexistent_exits_1(self, tmp_path):
        """Nothing is removable via models command — should always 'not found'."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "remove", "en_US-nobody-medium", "--config", str(cfg)]
        )
        assert result.exit_code == 1

    def test_remove_gpu_engine_by_name_shows_hint(self, tmp_path):
        """Removing a GPU engine with --engine shows the uninstall hint."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "remove", "coqui", "--engine", "coqui", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "pip" in result.output.lower() or "Note" in result.output


class TestModelsInfo:
    def test_info_gpu_engine_by_name(self, tmp_path):
        """'models info coqui' resolves via engine-name shorthand."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "info", "coqui", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "coqui" in result.output.lower()

    def test_info_shows_install_hint_for_size(self, tmp_path):
        """GPU engines report size as 'auto (managed by engine)'."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "info", "kokoro", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "auto" in result.output.lower()

    def test_info_unknown_exits_1(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "info", "en_US-nobody-medium", "--config", str(cfg)]
        )
        assert result.exit_code == 1

    def test_info_piper_voice_id_exits_1(self, tmp_path):
        """Piper voice IDs are no longer resolved by 'models info'."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "info", "en_US-amy-medium", "--config", str(cfg)]
        )
        assert result.exit_code == 1


class TestVoicesListAvailable:
    def _mock_catalog_response(self):
        resp = MagicMock()
        resp.read.return_value = json.dumps(_FAKE_PIPER_CATALOG).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_available_fetches_piper_catalog(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", return_value=self._mock_catalog_response()):
            result = runner.invoke(
                app, ["voices", "list", "--available", "--config", str(cfg)]
            )
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.output

    def test_available_shows_license(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", return_value=self._mock_catalog_response()):
            result = runner.invoke(
                app, ["voices", "list", "--available", "--config", str(cfg)]
            )
        assert "MIT" in result.output

    def test_available_language_filter(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", return_value=self._mock_catalog_response()):
            result = runner.invoke(
                app, ["voices", "list", "--available", "--language", "de", "--config", str(cfg)]
            )
        assert result.exit_code == 0
        # Fake catalog only has English voices — nothing should appear in the table body.
        assert "en_US-amy-medium" not in result.output

    def test_available_network_error_exits_1(self, tmp_path):
        import urllib.error
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = runner.invoke(
                app, ["voices", "list", "--available", "--config", str(cfg)]
            )
        assert result.exit_code == 1

    def test_available_non_piper_engine_shows_note(self, tmp_path):
        """--available for a non-Piper engine shows an informational note, not an error."""
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["voices", "list", "--available", "--engine", "kokoro", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "Note" in result.output or "built-in" in result.output.lower()
