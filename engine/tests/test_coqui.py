"""Tests for the Coqui XTTS v2 engine adapter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf

import hypnoai.tts.coqui_engine as _ce
from hypnoai.tts.coqui_engine import CoquiEngine


def _wav(path: Path, n: int = 100, sr: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(n, dtype=np.float32), sr, subtype="FLOAT")


@pytest.fixture
def patched_engine(tmp_path, monkeypatch):
    """CoquiEngine with _HAS_COQUI patched to True and _CoquiTTS mocked."""
    monkeypatch.setattr(_ce, "_HAS_COQUI", True)
    mock_tts_cls = MagicMock()
    monkeypatch.setattr(_ce, "_CoquiTTS", mock_tts_cls)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    engine = CoquiEngine(voices_dir=voices_dir, use_gpu=False)
    return engine, mock_tts_cls, voices_dir


class TestCoquiEngineInit:
    def test_raises_import_error_when_tts_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ce, "_HAS_COQUI", False)
        with pytest.raises(ImportError, match="pip install TTS"):
            CoquiEngine(voices_dir=tmp_path)


class TestCoquiEngineProtocol:
    def test_name_property(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.name == "coqui"

    def test_vram_estimate_mb(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.vram_estimate_mb == 4096

    def test_max_workers(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.max_workers == 1

    def test_supports_prosody_reference(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supports_prosody_reference() is True


class TestCoquiEngineListVoices:
    def test_empty_when_no_wav_files(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.list_voices() == []

    def test_discovers_wav_reference_files(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        _wav(voices_dir / "bob.wav")
        voices = engine.list_voices()
        ids = [v.id for v in voices]
        assert "alice" in ids
        assert "bob" in ids

    def test_voice_engine_tag_is_coqui(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "narrator.wav")
        voices = engine.list_voices()
        assert voices[0].engine == "coqui"

    def test_voices_sorted_alphabetically(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "zoe.wav")
        _wav(voices_dir / "ada.wav")
        voices = engine.list_voices()
        assert voices[0].id == "ada"
        assert voices[1].id == "zoe"

    def test_missing_voices_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ce, "_HAS_COQUI", True)
        engine = CoquiEngine(voices_dir=tmp_path / "nonexistent")
        assert engine.list_voices() == []


class TestCoquiEngineResolveVoice:
    def test_uses_prosody_ref_when_present(self, patched_engine, tmp_path):
        engine, _, voices_dir = patched_engine
        ref = tmp_path / "ref.wav"
        _wav(ref)
        result = engine._resolve_voice("alice", prosody_ref=ref)
        assert result == ref

    def test_falls_back_to_voice_file(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        result = engine._resolve_voice("alice", prosody_ref=None)
        assert result == voices_dir / "alice.wav"

    def test_raises_when_no_ref_and_no_voice_file(self, patched_engine):
        engine, _, _ = patched_engine
        with pytest.raises(FileNotFoundError, match="alice"):
            engine._resolve_voice("alice", prosody_ref=None)

    def test_ignores_missing_prosody_ref_falls_back_to_voice(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        missing_ref = voices_dir / "does_not_exist.wav"
        result = engine._resolve_voice("alice", prosody_ref=missing_ref)
        assert result == voices_dir / "alice.wav"


class TestCoquiEngineGenerate:
    def test_generate_calls_tts_to_file(self, patched_engine, tmp_path):
        engine, mock_tts_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        out = tmp_path / "out.wav"

        # Trigger lazy load
        engine.generate(text="Hello.", voice="alice", speed=1.0, output_path=out)

        mock_tts_cls.assert_called_once()
        engine._tts.tts_to_file.assert_called_once()

    def test_generate_passes_voice_as_speaker_wav(self, patched_engine, tmp_path):
        engine, mock_tts_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        out = tmp_path / "out.wav"
        engine.generate(text="Hello.", voice="alice", speed=1.0, output_path=out)
        call_kwargs = engine._tts.tts_to_file.call_args[1]
        assert str(voices_dir / "alice.wav") in call_kwargs.get("speaker_wav", "")

    def test_generate_uses_prosody_ref_when_provided(self, patched_engine, tmp_path):
        engine, mock_tts_cls, voices_dir = patched_engine
        prosody = tmp_path / "prosody.wav"
        _wav(prosody)
        out = tmp_path / "out.wav"
        engine.generate(text="Hello.", voice="alice", speed=1.0, output_path=out, prosody_reference=prosody)
        call_kwargs = engine._tts.tts_to_file.call_args[1]
        assert str(prosody) in call_kwargs.get("speaker_wav", "")

    def test_generate_creates_output_dir(self, patched_engine, tmp_path):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        out = tmp_path / "deep" / "nested" / "out.wav"
        engine.generate(text="Hello.", voice="alice", speed=1.0, output_path=out)
        assert (tmp_path / "deep" / "nested").exists()

    def test_model_loaded_lazily(self, patched_engine, tmp_path):
        engine, mock_tts_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        assert engine._tts is None  # not loaded yet
        engine.generate(text="Hello.", voice="alice", speed=1.0, output_path=tmp_path / "out.wav")
        assert engine._tts is not None

    def test_model_loaded_only_once(self, patched_engine, tmp_path):
        engine, mock_tts_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        engine.generate(text="Hello.", voice="alice", speed=1.0, output_path=tmp_path / "out1.wav")
        engine.generate(text="World.", voice="alice", speed=1.0, output_path=tmp_path / "out2.wav")
        assert mock_tts_cls.call_count == 1  # constructor called once
