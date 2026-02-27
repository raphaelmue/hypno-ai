"""Tests for models.* sidecar handlers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hypnoai.resources.model_manager import ModelInfo
from hypnoai.sidecar.handlers.models import (
    handle_models_download,
    handle_models_download_progress,
    handle_models_list,
    handle_models_remove,
    handle_models_status,
)
from hypnoai.sidecar.session import SidecarSession


@pytest.fixture
def session(tmp_path):
    return SidecarSession(tmp_root=tmp_path / "session")


# ---------------------------------------------------------------------------
# models.status
# ---------------------------------------------------------------------------


def test_models_status_keys(session):
    with patch("hypnoai.sidecar.handlers.models._gpu_available", return_value=False), \
         patch("hypnoai.sidecar.handlers.models._vram_total_mb", return_value=0), \
         patch("hypnoai.sidecar.handlers.models._disk_used_mb", return_value=100.0):
        result = handle_models_status(session, {})

    assert result["gpu_available"] is False
    assert result["vram_total_mb"] == 0
    assert result["disk_used_mb"] == 100.0


# ---------------------------------------------------------------------------
# models.list
# ---------------------------------------------------------------------------


def test_models_list_returns_structure(session):
    installed_voice = ModelInfo(
        id="en_US-amy-medium",
        name="Amy",
        engine="piper",
        language="en_US",
        quality="medium",
        size_mb=25.0,
        license="MIT",
        installed=True,
    )

    with patch("hypnoai.sidecar.handlers.models.PiperModelManager") as mock_cls, \
         patch("hypnoai.sidecar.handlers.models._engine_installed", return_value=False):
        mock_mgr = MagicMock()
        mock_mgr.list_installed.return_value = [installed_voice]
        mock_cls.return_value = mock_mgr

        result = handle_models_list(session, {})

    assert "installed" in result
    assert "available_for_download" in result
    installed = result["installed"]
    assert len(installed) >= 1
    assert installed[0]["name"] == "en_US-amy-medium"


def test_models_list_available_for_download(session):
    with patch("hypnoai.sidecar.handlers.models.PiperModelManager") as mock_cls, \
         patch("hypnoai.sidecar.handlers.models._engine_installed", return_value=False):
        mock_mgr = MagicMock()
        mock_mgr.list_installed.return_value = []
        mock_cls.return_value = mock_mgr

        result = handle_models_list(session, {})

    available = result["available_for_download"]
    assert len(available) > 0
    for item in available:
        assert "name" in item
        assert "license" in item
        assert "requires_gpu" in item


# ---------------------------------------------------------------------------
# models.download
# ---------------------------------------------------------------------------


def test_models_download_returns_job_id(session):
    with patch("hypnoai.sidecar.handlers.models.PiperModelManager") as mock_cls:
        mock_mgr = MagicMock()
        mock_mgr.get_catalog.return_value = {
            "en_US-amy-medium": ModelInfo(
                id="en_US-amy-medium", name="Amy", engine="piper",
                language="en_US", quality="medium", size_mb=25.0,
            )
        }
        mock_mgr.download.return_value = None
        mock_cls.return_value = mock_mgr

        result = handle_models_download(session, {"model": "en_US-amy-medium"})

    assert "job_id" in result
    assert "size_mb" in result


def test_models_download_missing_model(session):
    with pytest.raises(ValueError, match="model"):
        handle_models_download(session, {})


# ---------------------------------------------------------------------------
# models.download.progress
# ---------------------------------------------------------------------------


def test_models_download_progress(session):
    job = session.create_download_job("en_US-amy-medium", size_mb=25.0)
    job.state = "downloading"
    job.progress_pct = 50
    job.speed_mbps = 5.0

    result = handle_models_download_progress(session, {"job_id": job.job_id})
    assert result["state"] == "downloading"
    assert result["progress_pct"] == 50
    assert result["speed_mbps"] == 5.0


def test_models_download_progress_unknown(session):
    with pytest.raises(ValueError, match="Unknown job_id"):
        handle_models_download_progress(session, {"job_id": "nonexistent"})


def test_models_download_progress_missing_job_id(session):
    with pytest.raises(ValueError, match="Missing required param"):
        handle_models_download_progress(session, {})


# ---------------------------------------------------------------------------
# models.remove
# ---------------------------------------------------------------------------


def test_models_remove_success(session, tmp_path):
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    onnx = voices_dir / "en_US-amy-medium.onnx"
    json_f = voices_dir / "en_US-amy-medium.onnx.json"
    onnx.write_bytes(b"x" * 1024)
    json_f.write_bytes(b"y" * 512)

    with patch("hypnoai.sidecar.handlers.models.Config") as mock_cfg_cls, \
         patch("hypnoai.sidecar.handlers.models.PiperModelManager") as mock_mgr_cls:
        mock_cfg = MagicMock()
        mock_cfg.voices_dir = voices_dir
        mock_cfg_cls.load.return_value = mock_cfg

        mock_mgr = MagicMock()
        mock_mgr.remove.return_value = True
        mock_mgr_cls.return_value = mock_mgr

        result = handle_models_remove(session, {"model": "en_US-amy-medium"})

    assert "freed_mb" in result


def test_models_remove_not_installed(session, tmp_path):
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()

    with patch("hypnoai.sidecar.handlers.models.Config") as mock_cfg_cls, \
         patch("hypnoai.sidecar.handlers.models.PiperModelManager") as mock_mgr_cls:
        mock_cfg = MagicMock()
        mock_cfg.voices_dir = voices_dir
        mock_cfg_cls.load.return_value = mock_cfg

        mock_mgr = MagicMock()
        mock_mgr.remove.return_value = False
        mock_mgr_cls.return_value = mock_mgr

        with pytest.raises(ValueError, match="not installed"):
            handle_models_remove(session, {"model": "en_US-missing"})


def test_models_remove_missing_model(session):
    with pytest.raises(ValueError, match="model"):
        handle_models_remove(session, {})
