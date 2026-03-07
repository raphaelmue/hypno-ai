"""Tests for `hypnoai engines` and `hypnoai voices list --available` CLI commands.

The `models` subcommand has been removed; engine lifecycle is now handled
by `engines install` / `engines uninstall`.
"""
from __future__ import annotations

import json
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


def _make_config(tmp_path) -> str:
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir(exist_ok=True)
    cfg = tmp_path / "hypnoai.toml"
    cfg.write_text(f'voices_dir = "{voices_dir.as_posix()}"\n', encoding="utf-8")
    return str(cfg)


# ---------------------------------------------------------------------------
# engines list
# ---------------------------------------------------------------------------


class TestEnginesList:
    def test_shows_all_engines(self, tmp_path):
        result = runner.invoke(app, ["engines", "list"])
        assert result.exit_code == 0
        for name in ("piper", "coqui", "kokoro", "styletts2", "f5tts", "bark"):
            assert name in result.output

    def test_shows_installed_status(self, tmp_path):
        # "yes" or "no" are the installed status values
        result = runner.invoke(app, ["engines", "list"])
        assert result.exit_code == 0
        assert "yes" in result.output or "no" in result.output

    def test_shows_voice_types(self, tmp_path):
        result = runner.invoke(app, ["engines", "list"])
        assert result.exit_code == 0
        # catalog (piper), preset (kokoro/bark), clone (coqui/styletts/f5tts)
        assert "catalog" in result.output or "preset" in result.output

    def test_shows_license(self, tmp_path):
        result = runner.invoke(app, ["engines", "list"])
        assert result.exit_code == 0
        assert "MIT" in result.output


# ---------------------------------------------------------------------------
# engines install
# ---------------------------------------------------------------------------


_EM = "hypnoai.resources.engine_manager"


class TestEnginesInstall:
    def test_unknown_engine_exits_1(self, tmp_path):
        result = runner.invoke(app, ["engines", "install", "nonexistent"])
        assert result.exit_code == 1

    def test_already_installed_exits_0(self, tmp_path):
        with patch(f"{_EM}.is_installed", return_value=True):
            result = runner.invoke(app, ["engines", "install", "kokoro"])
        assert result.exit_code == 0
        assert "already installed" in result.output

    def test_install_calls_engine_manager(self, tmp_path):
        with patch(f"{_EM}.is_installed", return_value=False), \
             patch(f"{_EM}._run_pip") as mock_pip:
            mock_pip.return_value = None
            result = runner.invoke(app, ["engines", "install", "kokoro"])
        assert result.exit_code == 0
        mock_pip.assert_called_once()

    def test_frozen_env_no_python_exits_1(self, tmp_path):
        import sys
        with patch(f"{_EM}.is_installed", return_value=False), \
             patch.object(sys, "frozen", True, create=True), \
             patch("shutil.which", return_value=None):
            result = runner.invoke(app, ["engines", "install", "kokoro"])
        assert result.exit_code == 1

    def test_pip_failure_exits_1(self, tmp_path):
        with patch(f"{_EM}.is_installed", return_value=False), \
             patch(f"{_EM}._run_pip", side_effect=RuntimeError("pip failed")):
            result = runner.invoke(app, ["engines", "install", "kokoro"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# engines uninstall
# ---------------------------------------------------------------------------


class TestEnginesUninstall:
    def test_unknown_engine_exits_1(self, tmp_path):
        result = runner.invoke(app, ["engines", "uninstall", "nonexistent"])
        assert result.exit_code == 1

    def test_not_installed_exits_0(self, tmp_path):
        with patch(f"{_EM}.is_installed", return_value=False):
            result = runner.invoke(app, ["engines", "uninstall", "kokoro"])
        assert result.exit_code == 0
        assert "not installed" in result.output

    def test_uninstall_calls_engine_manager(self, tmp_path):
        with patch(f"{_EM}.is_installed", return_value=True), \
             patch(f"{_EM}._run_pip") as mock_pip:
            mock_pip.return_value = None
            result = runner.invoke(app, ["engines", "uninstall", "kokoro"])
        assert result.exit_code == 0
        mock_pip.assert_called_once()


# ---------------------------------------------------------------------------
# voices list --available
# ---------------------------------------------------------------------------


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
            result = runner.invoke(app, ["voices", "list", "--available", "--config", cfg])
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.output

    def test_available_shows_license(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", return_value=self._mock_catalog_response()):
            result = runner.invoke(app, ["voices", "list", "--available", "--config", cfg])
        assert "MIT" in result.output

    def test_available_language_filter(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", return_value=self._mock_catalog_response()):
            result = runner.invoke(
                app, ["voices", "list", "--available", "--language", "de", "--config", cfg]
            )
        assert result.exit_code == 0
        assert "en_US-amy-medium" not in result.output

    def test_available_network_error_exits_1(self, tmp_path):
        import urllib.error
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = runner.invoke(
                app, ["voices", "list", "--available", "--config", cfg]
            )
        assert result.exit_code == 1

    def test_available_non_piper_engine_shows_note(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["voices", "list", "--available", "--engine", "kokoro", "--config", cfg]
        )
        assert result.exit_code == 0
        assert "Note" in result.output or "built-in" in result.output.lower()
