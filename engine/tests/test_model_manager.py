"""Tests for PiperModelManager."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from hypnoai.resources.model_manager import (
    ModelInfo,
    PiperModelManager,
)

# ---------------------------------------------------------------------------
# Shared fake catalog (reused from test_model_downloader.py)
# ---------------------------------------------------------------------------

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


def _mock_catalog_response() -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(_FAKE_CATALOG).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _mock_file_response(data: bytes = b"\x00" * 100) -> MagicMock:
    resp = MagicMock()
    resp.headers = {"Content-Length": str(len(data))}
    resp.read.side_effect = [data, b""]
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# PiperModelManager — same behavior as old ModelDownloader
# ---------------------------------------------------------------------------


class TestPiperModelManager:
    def test_engine_name(self, tmp_path):
        mgr = PiperModelManager(tmp_path)
        assert mgr.engine_name == "piper"

    def test_creates_voices_dir(self, tmp_path):
        new_dir = tmp_path / "voices"
        assert not new_dir.exists()
        PiperModelManager(new_dir)
        assert new_dir.exists()

    def test_fetch_catalog_returns_model_infos(self, tmp_path):
        mgr = PiperModelManager(tmp_path)
        with patch("urllib.request.urlopen", return_value=_mock_catalog_response()):
            catalog = mgr.fetch_catalog()
        assert "en_US-amy-medium" in catalog
        assert catalog["en_US-amy-medium"].engine == "piper"

    def test_list_installed_empty(self, tmp_path):
        mgr = PiperModelManager(tmp_path)
        assert mgr.list_installed() == []

    def test_list_installed_detects_onnx(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00" * 100)
        (tmp_path / "en_US-amy-medium.onnx.json").write_text("{}")
        mgr = PiperModelManager(tmp_path)
        installed = mgr.list_installed()
        assert len(installed) == 1
        assert installed[0].id == "en_US-amy-medium"
        assert installed[0].installed is True

    def test_download_creates_files(self, tmp_path):
        mgr = PiperModelManager(tmp_path)
        catalog_resp = _mock_catalog_response()
        onnx_resp = _mock_file_response(b"\x00" * 50)
        json_resp = _mock_file_response(b"{}")
        with patch("urllib.request.urlopen", side_effect=[catalog_resp, onnx_resp, json_resp]):
            mgr.download("en_US-amy-medium")
        assert (tmp_path / "en_US-amy-medium.onnx").exists()
        assert (tmp_path / "en_US-amy-medium.onnx.json").exists()

    def test_remove_existing_voice(self, tmp_path):
        onnx = tmp_path / "en_US-amy-medium.onnx"
        onnx.write_bytes(b"\x00")
        mgr = PiperModelManager(tmp_path)
        assert mgr.remove("en_US-amy-medium") is True
        assert not onnx.exists()

    def test_remove_nonexistent_returns_false(self, tmp_path):
        mgr = PiperModelManager(tmp_path)
        assert mgr.remove("en_US-nobody-medium") is False

    def test_info_for_installed_voice(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        mgr = PiperModelManager(tmp_path)
        info = mgr.info("en_US-amy-medium")
        assert info is not None
        assert info.id == "en_US-amy-medium"
        assert info.installed is True


# ---------------------------------------------------------------------------
# Backward-compatibility: ModelDownloader import shim
# ---------------------------------------------------------------------------


class TestModelDownloaderBackwardCompat:
    def test_model_downloader_is_importable(self):
        from hypnoai.resources.model_downloader import ModelDownloader
        assert ModelDownloader is PiperModelManager

    def test_model_downloader_works_as_piper_manager(self, tmp_path):
        from hypnoai.resources.model_downloader import ModelDownloader
        mgr = ModelDownloader(tmp_path)
        assert mgr.engine_name == "piper"
        assert mgr.list_installed() == []

    def test_model_info_importable_from_shim(self):
        from hypnoai.resources.model_downloader import ModelInfo as MI
        assert MI is ModelInfo
