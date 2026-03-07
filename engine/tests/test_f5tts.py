"""Tests for the F5-TTS engine adapter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import hypnoai.tts.f5tts_engine as _fe
import numpy as np
import pytest
import soundfile as sf
from hypnoai.tts.f5tts_engine import F5TTSEngine


def _wav(path: Path, n: int = 100, sr: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(n, dtype=np.float32), sr, subtype="FLOAT")


def _make_model_mock(wav: np.ndarray | None = None, sr: int = 24000):
    """Return a mock F5TTS instance whose .infer() returns (wav, sr, None)."""
    if wav is None:
        wav = np.zeros(2400, dtype=np.float32)
    mock_model = MagicMock()
    mock_model.infer.return_value = (wav, sr, None)
    return mock_model


@pytest.fixture
def patched_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(_fe, "_HAS_F5TTS", True)
    mock_cls = MagicMock(return_value=_make_model_mock())
    monkeypatch.setattr(_fe, "_F5TTS", mock_cls)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    engine = F5TTSEngine(voices_dir=voices_dir, use_gpu=False)
    return engine, mock_cls, voices_dir


class TestF5TTSEngineInit:
    def test_raises_import_error_when_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_fe, "_HAS_F5TTS", False)
        _real_import = __import__

        def _blocked(name, *a, **kw):
            if name == "f5_tts.api":
                raise ImportError("mocked")
            return _real_import(name, *a, **kw)

        with patch("builtins.__import__", side_effect=_blocked):
            with pytest.raises(ImportError, match="pip install f5-tts"):
                F5TTSEngine(voices_dir=tmp_path)


class TestF5TTSEngineProtocol:
    def test_name(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.name == "f5tts"

    def test_vram_estimate_mb(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.vram_estimate_mb == 4096

    def test_max_workers(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.max_workers == 1

    def test_supports_prosody_reference(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supports_prosody_reference() is True

    def test_supports_voice_cloning(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supports_voice_cloning() is True

    def test_supported_emotions_empty(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supported_emotions() == []

    def test_supported_languages(self, patched_engine):
        engine, _, _ = patched_engine
        assert "en" in engine.supported_languages


class TestF5TTSEngineListVoices:
    def test_empty_when_no_wav_files(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.list_voices() == []

    def test_discovers_wav_files(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        _wav(voices_dir / "bob.wav")
        ids = [v.id for v in engine.list_voices()]
        assert "alice" in ids
        assert "bob" in ids

    def test_engine_tag_is_f5tts(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        assert engine.list_voices()[0].engine == "f5tts"

    def test_voices_sorted(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "zoe.wav")
        _wav(voices_dir / "ada.wav")
        ids = [v.id for v in engine.list_voices()]
        assert ids == sorted(ids)

    def test_missing_voices_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_fe, "_HAS_F5TTS", True)
        engine = F5TTSEngine(voices_dir=tmp_path / "nonexistent")
        assert engine.list_voices() == []


class TestF5TTSEngineResolveVoice:
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

    def test_ignores_missing_prosody_ref(self, patched_engine):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        missing = voices_dir / "nope.wav"
        result = engine._resolve_voice("alice", prosody_ref=missing)
        assert result == voices_dir / "alice.wav"

    def test_raises_when_no_ref_and_no_voice_file(self, patched_engine):
        engine, _, _ = patched_engine
        with pytest.raises(FileNotFoundError, match="alice"):
            engine._resolve_voice("alice", prosody_ref=None)


class TestF5TTSEngineGenerate:
    def test_generate_calls_infer(self, patched_engine, tmp_path):
        engine, mock_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        out = tmp_path / "out.wav"
        engine.generate("Hello.", "alice", 1.0, out)
        engine._model.infer.assert_called_once()

    def test_generate_passes_ref_file(self, patched_engine, tmp_path):
        engine, mock_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        engine.generate("Hello.", "alice", 1.0, tmp_path / "out.wav")
        call_kwargs = engine._model.infer.call_args[1]
        assert str(voices_dir / "alice.wav") == call_kwargs.get("ref_file", "")

    def test_generate_uses_prosody_ref(self, patched_engine, tmp_path):
        engine, _, voices_dir = patched_engine
        prosody = tmp_path / "prosody.wav"
        _wav(prosody)
        engine.generate("Hello.", "alice", 1.0, tmp_path / "out.wav", prosody_reference=prosody)
        call_kwargs = engine._model.infer.call_args[1]
        assert str(prosody) == call_kwargs.get("ref_file", "")

    def test_generate_passes_speed(self, patched_engine, tmp_path):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        engine.generate("Hello.", "alice", 0.85, tmp_path / "out.wav")
        call_kwargs = engine._model.infer.call_args[1]
        assert call_kwargs.get("speed") == pytest.approx(0.85)

    def test_model_loaded_lazily(self, patched_engine, tmp_path):
        engine, mock_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        assert engine._model is None
        engine.generate("Hello.", "alice", 1.0, tmp_path / "out.wav")
        assert engine._model is not None

    def test_model_loaded_only_once(self, patched_engine, tmp_path):
        engine, mock_cls, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        engine.generate("Hello.", "alice", 1.0, tmp_path / "a.wav")
        engine.generate("World.", "alice", 1.0, tmp_path / "b.wav")
        mock_cls.assert_called_once()

    def test_generate_creates_output_dir(self, patched_engine, tmp_path):
        engine, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        out = tmp_path / "deep" / "out.wav"
        engine.generate("Hello.", "alice", 1.0, out)
        assert out.parent.exists()
