"""Tests for the Kokoro TTS engine adapter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import hypnoai.tts.kokoro_engine as _ke
import numpy as np
import pytest
import soundfile as sf
from hypnoai.tts.kokoro_engine import KokoroEngine, _KOKORO_VOICES


def _make_pipeline_mock(audio: np.ndarray | None = None):
    """Return a mock KPipeline that yields one chunk of audio per call."""
    if audio is None:
        audio = np.zeros(100, dtype=np.float32)
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = iter([("g", "p", audio)])
    return mock_pipeline


@pytest.fixture
def patched_engine(tmp_path, monkeypatch):
    """KokoroEngine with _HAS_KOKORO=True and KPipeline mocked."""
    monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
    mock_pipeline_cls = _make_pipeline_mock()
    monkeypatch.setattr(_ke, "KPipeline", mock_pipeline_cls)
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    engine = KokoroEngine(voices_dir=voices_dir, use_gpu=False)
    return engine, mock_pipeline_cls, voices_dir


class TestKokoroEngineInit:
    def test_raises_import_error_when_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", False)
        with pytest.raises(ImportError, match="pip install kokoro"):
            KokoroEngine(voices_dir=tmp_path)


class TestKokoroEngineProtocol:
    def test_name(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.name == "kokoro"

    def test_vram_estimate_mb(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.vram_estimate_mb == 2048

    def test_max_workers(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.max_workers == 2

    def test_requires_gpu(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.requires_gpu is True

    def test_supported_languages(self, patched_engine):
        engine, _, _ = patched_engine
        assert "en-us" in engine.supported_languages
        assert "en-gb" in engine.supported_languages

    def test_supports_prosody_reference_false(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supports_prosody_reference() is False

    def test_supports_voice_cloning_false(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supports_voice_cloning() is False

    def test_supported_emotions_empty(self, patched_engine):
        engine, _, _ = patched_engine
        assert engine.supported_emotions() == []


class TestKokoroEngineListVoices:
    def test_returns_preset_voices(self, patched_engine):
        engine, _, _ = patched_engine
        voices = engine.list_voices()
        ids = [v.id for v in voices]
        assert "af_bella" in ids
        assert "bm_george" in ids

    def test_voice_count_matches_preset_list(self, patched_engine):
        engine, _, _ = patched_engine
        assert len(engine.list_voices()) == len(_KOKORO_VOICES)

    def test_american_english_language_tag(self, patched_engine):
        engine, _, _ = patched_engine
        voices = {v.id: v for v in engine.list_voices()}
        assert voices["af_bella"].language == "en-us"
        assert voices["am_adam"].language == "en-us"

    def test_british_english_language_tag(self, patched_engine):
        engine, _, _ = patched_engine
        voices = {v.id: v for v in engine.list_voices()}
        assert voices["bf_emma"].language == "en-gb"
        assert voices["bm_george"].language == "en-gb"

    def test_engine_tag_is_kokoro(self, patched_engine):
        engine, _, _ = patched_engine
        for v in engine.list_voices():
            assert v.engine == "kokoro"


class TestKokoroEngineGenerate:
    def test_generate_writes_wav(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        audio = np.zeros(2400, dtype=np.float32)
        mock_cls = MagicMock(return_value=MagicMock(
            return_value=iter([("g", "p", audio)])
        ))
        monkeypatch.setattr(_ke, "KPipeline", mock_cls)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        out = tmp_path / "out.wav"
        engine.generate("Hello.", "af_bella", 1.0, out)
        assert out.exists()

    def test_generate_creates_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        audio = np.zeros(100, dtype=np.float32)
        mock_cls = MagicMock(return_value=MagicMock(
            return_value=iter([("g", "p", audio)])
        ))
        monkeypatch.setattr(_ke, "KPipeline", mock_cls)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        out = tmp_path / "deep" / "nested" / "out.wav"
        engine.generate("Hello.", "af_bella", 1.0, out)
        assert out.parent.exists()

    def test_generate_raises_on_empty_audio(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        mock_cls = MagicMock(return_value=MagicMock(
            return_value=iter([("g", "p", None)])
        ))
        monkeypatch.setattr(_ke, "KPipeline", mock_cls)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        with pytest.raises(RuntimeError, match="no audio"):
            engine.generate("Hello.", "af_bella", 1.0, tmp_path / "out.wav")

    def test_pipeline_cached_per_lang_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        audio = np.zeros(100, dtype=np.float32)
        pipeline_instance = MagicMock(return_value=iter([("g", "p", audio)]))
        mock_cls = MagicMock(return_value=pipeline_instance)
        monkeypatch.setattr(_ke, "KPipeline", mock_cls)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        # Reset the return value to be callable multiple times
        pipeline_instance.side_effect = [
            iter([("g", "p", audio)]),
            iter([("g", "p", audio)]),
        ]
        engine.generate("Hello.", "af_bella", 1.0, tmp_path / "a.wav")
        engine.generate("World.", "af_sarah", 1.0, tmp_path / "b.wav")
        # KPipeline should be constructed only once for lang_code 'a'
        assert mock_cls.call_count == 1

    def test_british_voice_uses_different_lang_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        audio = np.zeros(100, dtype=np.float32)
        pipeline_instance = MagicMock(side_effect=[
            iter([("g", "p", audio)]),
            iter([("g", "p", audio)]),
        ])
        mock_cls = MagicMock(return_value=pipeline_instance)
        monkeypatch.setattr(_ke, "KPipeline", mock_cls)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        engine.generate("Hello.", "af_bella", 1.0, tmp_path / "en.wav")
        engine.generate("Hello.", "bf_emma", 1.0, tmp_path / "gb.wav")
        # Should create two pipelines: 'a' and 'b'
        assert mock_cls.call_count == 2


class TestKokoroLangCodeMapping:
    def test_american_prefix(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        assert engine._lang_code_for_voice("af_bella") == "a"
        assert engine._lang_code_for_voice("am_adam") == "a"

    def test_british_prefix(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        assert engine._lang_code_for_voice("bf_emma") == "b"
        assert engine._lang_code_for_voice("bm_george") == "b"

    def test_unknown_prefix_defaults_to_american(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_ke, "_HAS_KOKORO", True)
        engine = KokoroEngine(voices_dir=tmp_path, use_gpu=False)
        assert engine._lang_code_for_voice("unknown_voice") == "a"
