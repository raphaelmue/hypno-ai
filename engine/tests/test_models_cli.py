"""Tests for the `hypnoai models` CLI sub-app."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from hypnoai.cli import app
from hypnoai.resources.model_downloader import ModelInfo

runner = CliRunner()

_FAKE_CATALOG = {
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


def _install_fake_voice(voices_dir: Path, voice_id: str = "en_US-amy-medium") -> None:
    (voices_dir / f"{voice_id}.onnx").write_bytes(b"\x00" * 100)
    (voices_dir / f"{voice_id}.onnx.json").write_text(
        json.dumps({"audio": {"sample_rate": 22050}})
    )


class TestModelsList:
    def test_list_no_installed_voices(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(app, ["models", "list", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "No voice packs installed" in result.output

    def test_list_shows_installed_voice(self, tmp_path):
        cfg = _make_config(tmp_path)
        _install_fake_voice(tmp_path / "voices")
        result = runner.invoke(app, ["models", "list", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.output

    def test_list_available_fetches_catalog(self, tmp_path):
        cfg = _make_config(tmp_path)
        catalog_resp = MagicMock()
        catalog_resp.read.return_value = json.dumps(_FAKE_CATALOG).encode()
        catalog_resp.__enter__ = lambda s: s
        catalog_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=catalog_resp):
            result = runner.invoke(
                app, ["models", "list", "--available", "--config", str(cfg)]
            )
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.output

    def test_list_available_shows_license(self, tmp_path):
        cfg = _make_config(tmp_path)
        catalog_resp = MagicMock()
        catalog_resp.read.return_value = json.dumps(_FAKE_CATALOG).encode()
        catalog_resp.__enter__ = lambda s: s
        catalog_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=catalog_resp):
            result = runner.invoke(
                app, ["models", "list", "--available", "--config", str(cfg)]
            )
        assert "MIT" in result.output

    def test_list_available_network_error_exits_1(self, tmp_path):
        import urllib.error
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = runner.invoke(
                app, ["models", "list", "--available", "--config", str(cfg)]
            )
        assert result.exit_code == 1


class TestModelsDownload:
    def _make_file_response(self, data: bytes = b"\x00" * 100) -> MagicMock:
        resp = MagicMock()
        resp.headers = {"Content-Length": str(len(data))}
        resp.read.side_effect = [data, b""]
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_download_success(self, tmp_path):
        cfg = _make_config(tmp_path)
        catalog_resp = MagicMock()
        catalog_resp.read.return_value = json.dumps(_FAKE_CATALOG).encode()
        catalog_resp.__enter__ = lambda s: s
        catalog_resp.__exit__ = MagicMock(return_value=False)
        onnx_resp = self._make_file_response()
        json_resp = self._make_file_response(b"{}")

        with patch("urllib.request.urlopen", side_effect=[catalog_resp, onnx_resp, json_resp]):
            result = runner.invoke(
                app,
                ["models", "download", "en_US-amy-medium", "--config", str(cfg)],
            )
        assert result.exit_code == 0
        assert "Done" in result.output or "done" in result.output.lower()

    def test_download_unknown_voice_exits_1(self, tmp_path):
        cfg = _make_config(tmp_path)
        catalog_resp = MagicMock()
        catalog_resp.read.return_value = json.dumps(_FAKE_CATALOG).encode()
        catalog_resp.__enter__ = lambda s: s
        catalog_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=catalog_resp):
            result = runner.invoke(
                app,
                ["models", "download", "en_US-nobody-medium", "--config", str(cfg)],
            )
        assert result.exit_code == 1

    def test_download_bad_format_exits_1(self, tmp_path):
        cfg = _make_config(tmp_path)
        catalog_resp = MagicMock()
        catalog_resp.read.return_value = json.dumps(_FAKE_CATALOG).encode()
        catalog_resp.__enter__ = lambda s: s
        catalog_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=catalog_resp):
            result = runner.invoke(
                app, ["models", "download", "badformat", "--config", str(cfg)]
            )
        assert result.exit_code == 1


class TestModelsRemove:
    def test_remove_installed_voice(self, tmp_path):
        cfg = _make_config(tmp_path)
        _install_fake_voice(tmp_path / "voices")
        result = runner.invoke(
            app, ["models", "remove", "en_US-amy-medium", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert not (tmp_path / "voices" / "en_US-amy-medium.onnx").exists()

    def test_remove_nonexistent_exits_1(self, tmp_path):
        cfg = _make_config(tmp_path)
        result = runner.invoke(
            app, ["models", "remove", "en_US-nobody-medium", "--config", str(cfg)]
        )
        assert result.exit_code == 1

    def test_remove_shows_removed_message(self, tmp_path):
        cfg = _make_config(tmp_path)
        _install_fake_voice(tmp_path / "voices")
        result = runner.invoke(
            app, ["models", "remove", "en_US-amy-medium", "--config", str(cfg)]
        )
        assert "Removed" in result.output or "removed" in result.output.lower()


class TestModelsInfo:
    def test_info_installed_voice(self, tmp_path):
        cfg = _make_config(tmp_path)
        _install_fake_voice(tmp_path / "voices")
        result = runner.invoke(
            app, ["models", "info", "en_US-amy-medium", "--config", str(cfg)]
        )
        assert result.exit_code == 0
        assert "en_US-amy-medium" in result.output

    def test_info_shows_engine(self, tmp_path):
        cfg = _make_config(tmp_path)
        _install_fake_voice(tmp_path / "voices")
        result = runner.invoke(
            app, ["models", "info", "en_US-amy-medium", "--config", str(cfg)]
        )
        assert "piper" in result.output.lower()

    def test_info_shows_installed_yes(self, tmp_path):
        cfg = _make_config(tmp_path)
        _install_fake_voice(tmp_path / "voices")
        result = runner.invoke(
            app, ["models", "info", "en_US-amy-medium", "--config", str(cfg)]
        )
        assert "yes" in result.output.lower()

    def test_info_unknown_voice_exits_1(self, tmp_path):
        import urllib.error
        cfg = _make_config(tmp_path)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = runner.invoke(
                app, ["models", "info", "en_US-nobody-medium", "--config", str(cfg)]
            )
        assert result.exit_code == 1
