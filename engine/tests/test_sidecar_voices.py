"""Tests for voices.list and voices.clone sidecar handlers."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from hypnoai.sidecar.handlers.voices import handle_voices_clone, handle_voices_list
from hypnoai.sidecar.session import SidecarSession
from hypnoai.tts.base import VoiceInfo


@pytest.fixture
def session(tmp_path):
    return SidecarSession(tmp_root=tmp_path / "session")


# ---------------------------------------------------------------------------
# voices.list
# ---------------------------------------------------------------------------


def test_voices_list_returns_list(session):
    mock_voice = VoiceInfo(
        id="en_US-amy-medium",
        name="Amy",
        language="en_US",
        quality="medium",
        engine="piper",
        sample_rate=22050,
        size_mb=25.0,
        is_custom=False,
    )

    with patch("hypnoai.tts.piper_engine.PiperEngine") as mock_piper_cls:
        mock_engine = MagicMock()
        mock_engine.list_voices.return_value = [mock_voice]
        mock_piper_cls.return_value = mock_engine

        result = handle_voices_list(session, {"engine": "piper"})

    assert "voices" in result
    assert len(result["voices"]) == 1
    v = result["voices"][0]
    assert v["id"] == "en_US-amy-medium"
    assert v["name"] == "Amy"
    assert v["language"] == "en_US"
    assert v["quality"] == "medium"
    assert v["engine"] == "piper"


def test_voices_list_empty(session, tmp_path):
    """Clone engine with no .wav files returns an empty voice list."""
    from hypnoai.config import Config

    cfg = Config(voices_dir=tmp_path)
    with patch("hypnoai.sidecar.handlers.voices.Config") as mock_cfg_cls:
        mock_cfg_cls.load.return_value = cfg

        result = handle_voices_list(session, {"engine": "coqui"})

    assert result["voices"] == []


def test_voices_list_default_engine(session):
    """If no engine param is given, defaults gracefully."""
    with patch("hypnoai.tts.piper_engine.PiperEngine") as mock_piper_cls:
        mock_engine = MagicMock()
        mock_engine.list_voices.return_value = []
        mock_piper_cls.return_value = mock_engine

        result = handle_voices_list(session, {})

    assert "voices" in result


# ---------------------------------------------------------------------------
# voices.clone
# ---------------------------------------------------------------------------


def test_voices_clone_success(session, tmp_path):
    ref_wav = tmp_path / "ref.wav"
    data = np.zeros(22050, dtype=np.float32)
    sf.write(str(ref_wav), data, 22050)

    expected_voice = VoiceInfo(
        id="cloned-my_therapist",
        name="my_therapist",
        language="en",
        quality="cloned",
        engine="coqui",
        sample_rate=22050,
        size_mb=0.0,
        is_custom=True,
    )

    # Patch CoquiEngine at its source module so the lazy import inside
    # handle_voices_clone picks up the mock.
    with patch("hypnoai.tts.coqui_engine.CoquiEngine") as mock_cls:
        mock_engine = MagicMock()
        mock_engine.clone_voice.return_value = expected_voice
        mock_cls.return_value = mock_engine

        result = handle_voices_clone(session, {
            "name": "my_therapist",
            "reference_path": str(ref_wav),
            "engine": "coqui",
        })

    assert result["voice_id"] == "cloned-my_therapist"
    assert result["status"] == "ready"


def test_voices_clone_missing_name(session, tmp_path):
    ref_wav = tmp_path / "ref.wav"
    ref_wav.write_bytes(b"")
    with pytest.raises(ValueError, match="name"):
        handle_voices_clone(session, {"reference_path": str(ref_wav), "engine": "coqui"})


def test_voices_clone_missing_reference_path(session):
    with pytest.raises(ValueError, match="reference_path"):
        handle_voices_clone(session, {"name": "voice", "engine": "coqui"})


def test_voices_clone_reference_not_found(session, tmp_path):
    with pytest.raises(FileNotFoundError):
        handle_voices_clone(session, {
            "name": "v",
            "reference_path": str(tmp_path / "missing.wav"),
            "engine": "coqui",
        })


def test_voices_clone_unsupported_engine(session, tmp_path):
    ref_wav = tmp_path / "ref.wav"
    data = np.zeros(100, dtype=np.float32)
    sf.write(str(ref_wav), data, 22050)

    with pytest.raises(ValueError, match="cloning"):
        handle_voices_clone(session, {
            "name": "v",
            "reference_path": str(ref_wav),
            "engine": "piper",
        })
