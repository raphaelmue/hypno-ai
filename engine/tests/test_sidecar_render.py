"""Tests for render.* sidecar handlers."""
from __future__ import annotations

import textwrap
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from hypnoai.sidecar.handlers.render import (
    handle_render_cancel,
    handle_render_preview,
    handle_render_progress,
    handle_render_start,
)
from hypnoai.sidecar.session import SidecarSession


@pytest.fixture
def session(tmp_path):
    return SidecarSession(tmp_root=tmp_path / "session")


@pytest.fixture
def script_path(tmp_path) -> Path:
    p = tmp_path / "test.hypno"
    p.write_text(
        textwrap.dedent("""\
        @{voice: en_US-amy-medium}

        Close your eyes.

        @{pause: 2s}

        Take a deep breath.
        """),
        encoding="utf-8",
    )
    return p


def _make_wav(path: Path, duration_s: float = 1.0, sample_rate: int = 22050) -> None:
    data = np.zeros(int(duration_s * sample_rate), dtype=np.float32)
    sf.write(str(path), data, sample_rate)


# ---------------------------------------------------------------------------
# render.start
# ---------------------------------------------------------------------------


def test_render_start_returns_job_id(session, script_path, tmp_path):
    output_path = tmp_path / "out" / "session.wav"

    with patch("hypnoai.sidecar.handlers.render._build_engine") as mock_build, \
         patch("hypnoai.sidecar.handlers.render.PostProcessor") as mock_pp_cls:
        mock_engine = MagicMock()
        mock_engine.max_workers = 1
        mock_engine.supports_prosody_reference.return_value = False

        def _fake_generate(**kwargs):
            _make_wav(kwargs["output_path"])

        mock_engine.generate.side_effect = _fake_generate
        mock_build.return_value = mock_engine

        mock_pp = MagicMock()
        mock_pp_cls.return_value = mock_pp

        result = handle_render_start(session, {
            "script_path": str(script_path),
            "output_path": str(output_path),
            "voice": "en_US-amy-medium",
            "engine": "piper",
        })

    assert "job_id" in result
    assert isinstance(result["job_id"], str)
    assert len(result["job_id"]) > 0


def test_render_start_missing_script_path(session, tmp_path):
    with pytest.raises(ValueError, match="script_path"):
        handle_render_start(session, {"output_path": str(tmp_path / "out.wav")})


def test_render_start_missing_output_path(session, script_path):
    with pytest.raises(ValueError, match="output_path"):
        handle_render_start(session, {"script_path": str(script_path)})


# ---------------------------------------------------------------------------
# render.progress
# ---------------------------------------------------------------------------


def test_render_progress_pending(session):
    job = session.create_render_job(total=5)
    result = handle_render_progress(session, {"job_id": job.job_id})
    assert result["state"] == "pending"
    assert result["total"] == 5
    assert result["current_paragraph"] == 0


def test_render_progress_unknown_job(session):
    with pytest.raises(ValueError, match="Unknown job_id"):
        handle_render_progress(session, {"job_id": "nonexistent"})


def test_render_progress_missing_job_id(session):
    with pytest.raises(ValueError, match="Missing required param"):
        handle_render_progress(session, {})


def test_render_progress_elapsed_included(session):
    job = session.create_render_job(total=3)
    time.sleep(0.05)
    result = handle_render_progress(session, {"job_id": job.job_id})
    assert result["elapsed_s"] >= 0.05


# ---------------------------------------------------------------------------
# render.cancel
# ---------------------------------------------------------------------------


def test_render_cancel_pending_job(session):
    job = session.create_render_job(total=5)
    result = handle_render_cancel(session, {"job_id": job.job_id})
    assert result["cancelled"] is True
    assert job.state == "cancelled"


def test_render_cancel_done_job(session):
    job = session.create_render_job(total=5)
    job.state = "done"
    result = handle_render_cancel(session, {"job_id": job.job_id})
    assert result["cancelled"] is False


def test_render_cancel_unknown_job(session):
    with pytest.raises(ValueError, match="Unknown job_id"):
        handle_render_cancel(session, {"job_id": "nonexistent"})


def test_render_cancel_missing_job_id(session):
    with pytest.raises(ValueError, match="Missing required param"):
        handle_render_cancel(session, {})


# ---------------------------------------------------------------------------
# render.preview
# ---------------------------------------------------------------------------


def test_render_preview_returns_audio_path(session, tmp_path):
    with patch("hypnoai.sidecar.handlers.render._build_engine") as mock_build:
        mock_engine = MagicMock()

        def _fake_generate(**kwargs):
            _make_wav(kwargs["output_path"], duration_s=3.0)

        mock_engine.generate.side_effect = _fake_generate
        mock_build.return_value = mock_engine

        result = handle_render_preview(session, {
            "text": "Close your eyes and breathe deeply.",
            "voice": "en_US-amy-medium",
            "engine": "piper",
            "speed": 0.85,
        })

    assert "audio_path" in result
    assert result["audio_path"] == str(session.preview_path)
    assert result["duration_s"] == pytest.approx(3.0, abs=0.1)


def test_render_preview_missing_text(session):
    with pytest.raises(ValueError, match="text"):
        handle_render_preview(session, {"voice": "en_US-amy-medium", "engine": "piper"})


def test_render_preview_missing_voice(session):
    with pytest.raises(ValueError, match="voice"):
        handle_render_preview(session, {"text": "hello", "engine": "piper"})
