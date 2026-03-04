"""Tests for the Bark TTS engine adapter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import hypnoai.tts.bark_engine as _be
import numpy as np
import pytest
import soundfile as sf
from hypnoai.tts.bark_engine import BarkEngine, _BARK_ALL_SPEAKERS


def _patch_bark(monkeypatch, audio: np.ndarray | None = None):
    """Patch all bark module-level symbols to safe mocks."""
    if audio is None:
        audio = np.zeros(2400, dtype=np.float32)
    mock_generate = MagicMock(return_value=audio)
    mock_preload = MagicMock()
    monkeypatch.setattr(_be, "_HAS_BARK", True)
    monkeypatch.setattr(_be, "generate_audio", mock_generate)
    monkeypatch.setattr(_be, "preload_models", mock_preload)
    monkeypatch.setattr(_be, "_BARK_SAMPLE_RATE", 24000)
    return mock_generate, mock_preload


@pytest.fixture
def patched_engine(tmp_path, monkeypatch):
    mock_gen, mock_pre = _patch_bark(monkeypatch)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    engine = BarkEngine(voices_dir=voices_dir, use_gpu=False)
    return engine, mock_gen, mock_pre


class TestBarkEngineInit:
    def test_raises_import_error_when_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_be, "_HAS_BARK", False)
        with pytest.raises(ImportError, match="pip install suno-bark"):
            BarkEngine(voices_dir=tmp_path)


class TestBarkEngineProtocol:
    def test_name(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.name == "bark"

    def test_vram_estimate_mb(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.vram_estimate_mb == 6144

    def test_max_workers(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.max_workers == 1

    def test_requires_gpu_reflects_use_gpu(self, patched_engine, tmp_path, monkeypatch):
        engine, _, _ = patched_engine
        assert engine.requires_gpu is False  # fixture uses use_gpu=False
        _patch_bark(monkeypatch)
        gpu_engine = BarkEngine(voices_dir=tmp_path, use_gpu=True)
        assert gpu_engine.requires_gpu is True

    def test_supports_prosody_reference_false(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supports_prosody_reference() is False

    def test_supports_voice_cloning_false(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supports_voice_cloning() is False

    def test_supported_emotions(self, patched_engine):
        engine, _, _ = patched_engine
        assert "neutral" in engine.supported_emotions()


class TestBarkEngineListVoices:
    def test_returns_preset_voices(self, patched_engine):
        engine, _, _ = patched_engine
        voices = engine.list_voices()
        ids = [v.id for v in voices]
        assert "v2/en_speaker_0" in ids
        assert "v2/de_speaker_3" in ids

    def test_voice_count(self, patched_engine):
        engine, _, _ = patched_engine
        assert len(engine.list_voices()) == len(_BARK_ALL_SPEAKERS)

    def test_english_language_tag(self, patched_engine):
        engine, _, _ = patched_engine
        en_voices = [v for v in engine.list_voices() if v.id.startswith("v2/en")]
        assert all(v.language == "en" for v in en_voices)

    def test_german_language_tag(self, patched_engine):
        engine, _, _ = patched_engine
        de_voices = [v for v in engine.list_voices() if v.id.startswith("v2/de")]
        assert all(v.language == "de" for v in de_voices)

    def test_engine_tag_is_bark(self, patched_engine):
        engine, _, _ = patched_engine
        for v in engine.list_voices():
            assert v.engine == "bark"


class TestBarkEngineGenerate:
    def test_generate_writes_wav(self, patched_engine, tmp_path):
        engine, _, _ = patched_engine
        out = tmp_path / "out.wav"
        engine.generate("Hello.", "v2/en_speaker_0", 1.0, out)
        assert out.exists()

    def test_generate_calls_generate_audio_with_voice(self, patched_engine, tmp_path):
        engine, mock_gen, _ = patched_engine
        engine.generate("Hello.", "v2/en_speaker_3", 1.0, tmp_path / "out.wav")
        mock_gen.assert_called_once_with("Hello.", history_prompt="v2/en_speaker_3")

    def test_preload_models_called_on_first_generate(self, patched_engine, tmp_path):
        engine, _, mock_pre = patched_engine
        assert not engine._loaded
        engine.generate("Hello.", "v2/en_speaker_0", 1.0, tmp_path / "out.wav")
        mock_pre.assert_called_once()
        assert engine._loaded

    def test_preload_models_called_only_once(self, patched_engine, tmp_path):
        engine, mock_gen, mock_pre = patched_engine
        engine.generate("Hello.", "v2/en_speaker_0", 1.0, tmp_path / "a.wav")
        engine.generate("World.", "v2/en_speaker_0", 1.0, tmp_path / "b.wav")
        mock_pre.assert_called_once()

    def test_generate_creates_output_dir(self, patched_engine, tmp_path):
        engine, _, _ = patched_engine
        out = tmp_path / "a" / "b" / "out.wav"
        engine.generate("Hello.", "v2/en_speaker_0", 1.0, out)
        assert out.parent.exists()

    def test_speed_resamples_audio(self, tmp_path, monkeypatch):
        """When speed != 1.0, output should have different length."""
        original = np.zeros(4800, dtype=np.float32)
        mock_gen, _ = _patch_bark(monkeypatch, audio=original)
        engine = BarkEngine(voices_dir=tmp_path, use_gpu=False)
        out = tmp_path / "out.wav"
        engine.generate("Hello.", "v2/en_speaker_0", 2.0, out)
        data, sr = sf.read(str(out))
        # At speed=2.0 the output should be roughly half the length
        assert len(data) < len(original)
