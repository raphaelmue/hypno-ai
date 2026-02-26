"""Tests for ModelManager implementations."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hypnoai.resources.model_manager import (
    BarkModelManager,
    CoquiModelManager,
    F5TTSModelManager,
    KokoroModelManager,
    ModelInfo,
    PiperModelManager,
    StyleTTSModelManager,
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
# CoquiModelManager stub
# ---------------------------------------------------------------------------


class TestCoquiModelManager:
    def test_engine_name(self):
        mgr = CoquiModelManager()
        assert mgr.engine_name == "coqui"

    def test_list_installed_returns_empty(self):
        mgr = CoquiModelManager()
        assert mgr.list_installed() == []

    def test_get_catalog_returns_single_entry(self):
        mgr = CoquiModelManager()
        catalog = mgr.get_catalog()
        assert len(catalog) == 1
        entry = next(iter(catalog.values()))
        assert entry.engine == "coqui"

    def test_download_raises_not_implemented(self):
        mgr = CoquiModelManager()
        with pytest.raises(NotImplementedError):
            mgr.download("xtts_v2")

    def test_remove_raises_not_implemented(self):
        mgr = CoquiModelManager()
        with pytest.raises(NotImplementedError):
            mgr.remove("xtts_v2")

    def test_info_returns_catalog_entry(self):
        mgr = CoquiModelManager()
        info = mgr.info(mgr._MODEL_ID)
        assert info is not None
        assert info.engine == "coqui"


# ---------------------------------------------------------------------------
# Stub managers — verify engine_name and consistent behavior
# ---------------------------------------------------------------------------


class TestStubManagers:
    @pytest.mark.parametrize(
        "manager_cls, expected_engine",
        [
            (KokoroModelManager, "kokoro"),
            (StyleTTSModelManager, "styletts2"),
            (F5TTSModelManager, "f5tts"),
            (BarkModelManager, "bark"),
        ],
    )
    def test_engine_name(self, manager_cls, expected_engine):
        mgr = manager_cls()
        assert mgr.engine_name == expected_engine

    @pytest.mark.parametrize(
        "manager_cls",
        [KokoroModelManager, StyleTTSModelManager, F5TTSModelManager, BarkModelManager],
    )
    def test_get_catalog_returns_one_entry(self, manager_cls):
        mgr = manager_cls()
        catalog = mgr.get_catalog()
        assert len(catalog) == 1

    @pytest.mark.parametrize(
        "manager_cls",
        [KokoroModelManager, StyleTTSModelManager, F5TTSModelManager, BarkModelManager],
    )
    def test_download_raises_not_implemented(self, manager_cls):
        mgr = manager_cls()
        with pytest.raises(NotImplementedError):
            mgr.download("some_model")

    @pytest.mark.parametrize(
        "manager_cls",
        [KokoroModelManager, StyleTTSModelManager, F5TTSModelManager, BarkModelManager],
    )
    def test_remove_raises_not_implemented(self, manager_cls):
        mgr = manager_cls()
        with pytest.raises(NotImplementedError):
            mgr.remove("some_model")

    @pytest.mark.parametrize(
        "manager_cls",
        [KokoroModelManager, StyleTTSModelManager, F5TTSModelManager, BarkModelManager],
    )
    def test_list_installed_returns_list(self, manager_cls):
        mgr = manager_cls()
        result = mgr.list_installed()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Backward-compatibility: ModelDownloader import
# ---------------------------------------------------------------------------


class TestModelDownloaderBackwardCompat:
    def test_model_downloader_is_importable(self):
        from hypnoai.resources.model_downloader import ModelDownloader, ModelInfo, ProgressCallback
        assert ModelDownloader is PiperModelManager

    def test_model_downloader_works_as_piper_manager(self, tmp_path):
        from hypnoai.resources.model_downloader import ModelDownloader
        mgr = ModelDownloader(tmp_path)
        assert mgr.engine_name == "piper"
        assert mgr.list_installed() == []

    def test_model_info_importable_from_shim(self):
        from hypnoai.resources.model_downloader import ModelInfo as MI
        assert MI is ModelInfo
