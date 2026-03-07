"""Tests for the StyleTTS 2 engine adapter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import hypnoai.tts.styletts_engine as _se
import numpy as np
import pytest
import soundfile as sf
from hypnoai.tts.styletts_engine import StyleTTSEngine, _STYLETTS2_EMOTIONS


def _wav(path: Path, n: int = 100, sr: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(n, dtype=np.float32), sr, subtype="FLOAT")


def _make_stts2_mock(wav: np.ndarray | None = None):
    """Return a mock styletts2.tts module with a StyleTTS2 class."""
    if wav is None:
        wav = np.zeros(2400, dtype=np.float32)
    mock_model = MagicMock()
    mock_model.inference.return_value = wav
    mock_stts2_module = MagicMock()
    mock_stts2_module.StyleTTS2.return_value = mock_model
    return mock_stts2_module, mock_model


@pytest.fixture
def patched_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(_se, "_HAS_STYLETTS2", True)
    mock_mod, mock_model = _make_stts2_mock()
    monkeypatch.setattr(_se, "_stts2", mock_mod)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    engine = StyleTTSEngine(voices_dir=voices_dir, use_gpu=False)
    return engine, mock_mod, mock_model, voices_dir


class TestStyleTTSEngineInit:
    def test_raises_import_error_when_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_se, "_HAS_STYLETTS2", False)
        _real_import = __import__

        def _blocked(name, *a, **kw):
            if name == "styletts2":
                raise ImportError("mocked")
            return _real_import(name, *a, **kw)

        with patch("builtins.__import__", side_effect=_blocked):
            with pytest.raises(ImportError, match="pip install styletts2"):
                StyleTTSEngine(voices_dir=tmp_path)


class TestStyleTTSEngineProtocol:
    def test_name(self, patched_engine):
        engine, *_ = patched_engine
        assert engine.name == "styletts2"

    def test_vram_estimate_mb(self, patched_engine):
        engine, *_ = patched_engine
        assert engine.vram_estimate_mb == 3072

    def test_max_workers(self, patched_engine):
        engine, *_ = patched_engine
        assert engine.max_workers == 1

    def test_requires_gpu_reflects_use_gpu(self, patched_engine, tmp_path, monkeypatch):
        engine, *_ = patched_engine
        assert engine.requires_gpu is False  # fixture uses use_gpu=False
        mock_mod, _ = _make_stts2_mock()
        monkeypatch.setattr(_se, "_stts2", mock_mod)
        gpu_engine = StyleTTSEngine(voices_dir=tmp_path, use_gpu=True)
        assert gpu_engine.requires_gpu is True

    def test_supports_voice_cloning(self, patched_engine):
        engine, *_ = patched_engine
        assert engine.supports_voice_cloning() is True

    def test_supports_prosody_reference_false(self, patched_engine):
        engine, *_ = patched_engine
        assert engine.supports_prosody_reference() is False

    def test_supported_emotions(self, patched_engine):
        engine, *_ = patched_engine
        emotions = engine.supported_emotions()
        assert "neutral" in emotions
        assert "happy" in emotions
        assert emotions == _STYLETTS2_EMOTIONS

    def test_supported_languages(self, patched_engine):
        engine, *_ = patched_engine
        assert engine.supported_languages == ["en"]


class TestStyleTTSEngineListVoices:
    def test_empty_when_no_wav_files(self, patched_engine):
        engine, *_ = patched_engine
        assert engine.list_voices() == []

    def test_discovers_wav_files(self, patched_engine):
        engine, _, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        _wav(voices_dir / "bob.wav")
        ids = [v.id for v in engine.list_voices()]
        assert "alice" in ids
        assert "bob" in ids

    def test_engine_tag_is_styletts2(self, patched_engine):
        engine, _, _, voices_dir = patched_engine
        _wav(voices_dir / "narrator.wav")
        assert engine.list_voices()[0].engine == "styletts2"

    def test_voices_sorted(self, patched_engine):
        engine, _, _, voices_dir = patched_engine
        _wav(voices_dir / "zoe.wav")
        _wav(voices_dir / "ada.wav")
        ids = [v.id for v in engine.list_voices()]
        assert ids == sorted(ids)

    def test_missing_voices_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_se, "_HAS_STYLETTS2", True)
        monkeypatch.setattr(_se, "_stts2", MagicMock())
        engine = StyleTTSEngine(voices_dir=tmp_path / "nonexistent")
        assert engine.list_voices() == []


class TestStyleTTSEngineResolveVoice:
    def test_resolves_voice_file(self, patched_engine):
        engine, _, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        result = engine._resolve_voice("alice")
        assert result == voices_dir / "alice.wav"

    def test_raises_when_voice_file_missing(self, patched_engine):
        engine, *_ = patched_engine
        with pytest.raises(FileNotFoundError, match="alice"):
            engine._resolve_voice("alice")


class TestStyleTTSEngineGenerate:
    def test_generate_calls_inference(self, patched_engine, tmp_path):
        engine, mock_mod, mock_model, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        engine.generate("Hello.", "alice", 1.0, tmp_path / "out.wav")
        mock_model.inference.assert_called_once()

    def test_generate_passes_voice_ref(self, patched_engine, tmp_path):
        engine, _, mock_model, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        engine.generate("Hello.", "alice", 1.0, tmp_path / "out.wav")
        call_kwargs = mock_model.inference.call_args[1]
        assert str(voices_dir / "alice.wav") == call_kwargs.get("target_voice_path", "")

    def test_model_loaded_lazily(self, patched_engine, tmp_path):
        engine, mock_mod, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        assert engine._model is None
        engine.generate("Hello.", "alice", 1.0, tmp_path / "out.wav")
        assert engine._model is not None

    def test_model_loaded_only_once(self, patched_engine, tmp_path):
        engine, mock_mod, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        engine.generate("Hello.", "alice", 1.0, tmp_path / "a.wav")
        engine.generate("World.", "alice", 1.0, tmp_path / "b.wav")
        mock_mod.StyleTTS2.assert_called_once()

    def test_generate_creates_output_dir(self, patched_engine, tmp_path):
        engine, _, _, voices_dir = patched_engine
        _wav(voices_dir / "alice.wav")
        out = tmp_path / "deep" / "out.wav"
        engine.generate("Hello.", "alice", 1.0, out)
        assert out.parent.exists()

    def test_speed_resamples_audio(self, patched_engine, tmp_path):
        engine, _, mock_model, voices_dir = patched_engine
        original = np.zeros(4800, dtype=np.float32)
        mock_model.inference.return_value = original
        _wav(voices_dir / "alice.wav")
        out = tmp_path / "out.wav"
        engine.generate("Hello.", "alice", 2.0, out)
        data, sr = sf.read(str(out))
        assert len(data) < len(original)

    def test_raises_when_voice_missing(self, patched_engine, tmp_path):
        engine, *_ = patched_engine
        with pytest.raises(FileNotFoundError, match="alice"):
            engine.generate("Hello.", "alice", 1.0, tmp_path / "out.wav")
