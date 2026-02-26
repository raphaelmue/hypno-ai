"""Tests for the model downloader."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from hypnoai.resources.model_downloader import ModelDownloader, ModelInfo

# Minimal fake catalog response
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
    "de_DE-thorsten-medium": {
        "name": "Thorsten",
        "language": {"code": "de"},
        "quality": "medium",
        "license": "Apache 2.0",
        "files": {
            "de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx": {"size_bytes": 30_000_000},
            "de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json": {"size_bytes": 5_000},
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
    resp.read.side_effect = [data, b""]  # one chunk then EOF
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestModelDownloaderInit:
    def test_creates_voices_dir(self, tmp_path):
        new_dir = tmp_path / "voices"
        assert not new_dir.exists()
        ModelDownloader(new_dir)
        assert new_dir.exists()


class TestFetchCatalog:
    def test_returns_model_infos(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        resp = _mock_catalog_response()
        with patch("urllib.request.urlopen", return_value=resp):
            catalog = downloader.fetch_catalog()
        assert "en_US-amy-medium" in catalog
        assert "de_DE-thorsten-medium" in catalog

    def test_model_info_fields(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        resp = _mock_catalog_response()
        with patch("urllib.request.urlopen", return_value=resp):
            catalog = downloader.fetch_catalog()
        amy = catalog["en_US-amy-medium"]
        assert amy.engine == "piper"
        assert amy.language == "en"
        assert amy.quality == "medium"
        assert amy.license == "MIT"
        assert amy.size_mb > 0

    def test_raises_on_network_error(self, tmp_path):
        import urllib.error
        downloader = ModelDownloader(tmp_path)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with pytest.raises(RuntimeError, match="Failed to fetch voice catalog"):
                downloader.fetch_catalog()

    def test_catalog_cached(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        resp = _mock_catalog_response()
        with patch("urllib.request.urlopen", return_value=resp) as mock_open:
            downloader.get_catalog()
            downloader.get_catalog()  # second call — should use cache
        assert mock_open.call_count == 1

    def test_force_refresh_re_fetches(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        resp1 = _mock_catalog_response()
        resp2 = _mock_catalog_response()
        with patch("urllib.request.urlopen", side_effect=[resp1, resp2]) as mock_open:
            downloader.get_catalog()
            downloader.get_catalog(force_refresh=True)
        assert mock_open.call_count == 2


class TestListInstalled:
    def test_empty_voices_dir(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        assert downloader.list_installed() == []

    def test_detects_installed_voice(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00" * 100)
        (tmp_path / "en_US-amy-medium.onnx.json").write_text("{}")
        downloader = ModelDownloader(tmp_path)
        installed = downloader.list_installed()
        assert len(installed) == 1
        assert installed[0].id == "en_US-amy-medium"
        assert installed[0].installed is True

    def test_multiple_installed_voices(self, tmp_path):
        for vid in ("en_US-amy-medium", "de_DE-thorsten-medium"):
            (tmp_path / f"{vid}.onnx").write_bytes(b"\x00")
            (tmp_path / f"{vid}.onnx.json").write_text("{}")
        downloader = ModelDownloader(tmp_path)
        installed = downloader.list_installed()
        ids = [m.id for m in installed]
        assert "en_US-amy-medium" in ids
        assert "de_DE-thorsten-medium" in ids

    def test_returns_model_info_objects(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        downloader = ModelDownloader(tmp_path)
        installed = downloader.list_installed()
        assert all(isinstance(m, ModelInfo) for m in installed)


class TestDownload:
    def test_raises_for_invalid_voice_id_format(self, tmp_path):
        """A voice_id that can't be parsed raises ValueError."""
        downloader = ModelDownloader(tmp_path)
        # Fake catalog that contains the bad voice_id so we bypass the
        # "unknown voice" check and reach the format-parsing check.
        from hypnoai.resources.model_downloader import ModelInfo
        fake_entry = ModelInfo(id="invalid", name="invalid", engine="piper",
                               language="", quality="", size_mb=0)
        with patch.object(downloader, "get_catalog", return_value={"invalid": fake_entry}):
            with pytest.raises(ValueError, match="Cannot parse"):
                downloader.download("invalid")

    def test_raises_for_unknown_voice_in_catalog(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        catalog = {k: v for k, v in _FAKE_CATALOG.items()}
        mock_infos = {}
        with patch("urllib.request.urlopen", return_value=_mock_catalog_response()):
            downloader.get_catalog()
        with pytest.raises(ValueError, match="Unknown voice"):
            downloader.download("en_US-unknown-medium")

    def test_download_creates_files(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        catalog_resp = _mock_catalog_response()
        onnx_resp = _mock_file_response(b"\x00" * 50)
        json_resp = _mock_file_response(b"{}")

        with patch("urllib.request.urlopen", side_effect=[catalog_resp, onnx_resp, json_resp]):
            downloader.download("en_US-amy-medium")

        assert (tmp_path / "en_US-amy-medium.onnx").exists()
        assert (tmp_path / "en_US-amy-medium.onnx.json").exists()

    def test_progress_callback_called(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        calls: list[tuple[int, int]] = []

        def track_progress(downloaded: int, total: int) -> None:
            calls.append((downloaded, total))

        catalog_resp = _mock_catalog_response()
        data = b"\x00" * 200
        onnx_resp = _mock_file_response(data)
        json_resp = _mock_file_response(b"{}")

        with patch("urllib.request.urlopen", side_effect=[catalog_resp, onnx_resp, json_resp]):
            downloader.download("en_US-amy-medium", progress=track_progress)

        assert len(calls) > 0

    def test_download_raises_on_network_error(self, tmp_path):
        import urllib.error
        downloader = ModelDownloader(tmp_path)
        catalog_resp = _mock_catalog_response()
        with patch(
            "urllib.request.urlopen",
            side_effect=[catalog_resp, urllib.error.URLError("bad")],
        ):
            with pytest.raises(RuntimeError, match="Failed to download"):
                downloader.download("en_US-amy-medium")


class TestRemove:
    def test_remove_existing_voice(self, tmp_path):
        onnx = tmp_path / "en_US-amy-medium.onnx"
        json_f = tmp_path / "en_US-amy-medium.onnx.json"
        onnx.write_bytes(b"\x00")
        json_f.write_text("{}")
        downloader = ModelDownloader(tmp_path)
        removed = downloader.remove("en_US-amy-medium")
        assert removed is True
        assert not onnx.exists()
        assert not json_f.exists()

    def test_remove_nonexistent_voice_returns_false(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        removed = downloader.remove("en_US-nobody-medium")
        assert removed is False

    def test_remove_partial_install(self, tmp_path):
        onnx = tmp_path / "en_US-amy-medium.onnx"
        onnx.write_bytes(b"\x00")
        # No .onnx.json
        downloader = ModelDownloader(tmp_path)
        removed = downloader.remove("en_US-amy-medium")
        assert removed is True


class TestInfo:
    def test_info_for_installed_voice(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        downloader = ModelDownloader(tmp_path)
        info = downloader.info("en_US-amy-medium")
        assert info is not None
        assert info.id == "en_US-amy-medium"
        assert info.installed is True

    def test_info_from_catalog(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        resp = _mock_catalog_response()
        with patch("urllib.request.urlopen", return_value=resp):
            info = downloader.info("de_DE-thorsten-medium")
        assert info is not None
        assert info.language == "de"

    def test_info_returns_none_for_unknown(self, tmp_path):
        downloader = ModelDownloader(tmp_path)
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            info = downloader.info("en_US-nobody-medium")
        assert info is None
