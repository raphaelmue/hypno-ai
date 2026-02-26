"""Tests for TTS engine and engine registry."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hypnoai.tts.piper_engine import PiperEngine
from hypnoai.tts.voice_registry import EngineRegistry, VoiceRegistry


class TestPiperEngine:
    def test_name(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.name == "piper"

    def test_list_voices_empty_dir(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.list_voices() == []

    def test_list_voices_dir_missing(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path / "nonexistent")
        assert engine.list_voices() == []

    def test_list_voices_ignores_onnx_without_json(self, tmp_path):
        (tmp_path / "en_US-test.onnx").write_bytes(b"\x00")
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.list_voices() == []

    def test_list_voices_discovers_pair(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00" * 512)
        (tmp_path / "en_US-amy-medium.onnx.json").write_text(
            json.dumps({"audio": {"sample_rate": 22050}})
        )
        engine = PiperEngine(voices_dir=tmp_path)
        voices = engine.list_voices()
        assert len(voices) == 1
        v = voices[0]
        assert v.id == "en_US-amy-medium"
        assert v.engine == "piper"
        assert v.language == "en_US"
        assert v.name == "Amy"
        assert v.quality == "medium"
        assert v.sample_rate == 22050

    def test_list_voices_custom_sample_rate(self, tmp_path):
        (tmp_path / "en_GB-jenny-low.onnx").write_bytes(b"\x00")
        (tmp_path / "en_GB-jenny-low.onnx.json").write_text(
            json.dumps({"audio": {"sample_rate": 16000}})
        )
        engine = PiperEngine(voices_dir=tmp_path)
        v = engine.list_voices()[0]
        assert v.sample_rate == 16000
        assert v.quality == "low"

    def test_list_voices_multiple(self, tmp_path):
        for name in ["en_US-amy-medium", "en_US-ryan-low", "de_DE-thorsten-medium"]:
            (tmp_path / f"{name}.onnx").write_bytes(b"\x00")
            (tmp_path / f"{name}.onnx.json").write_text(
                json.dumps({"audio": {"sample_rate": 22050}})
            )
        engine = PiperEngine(voices_dir=tmp_path)
        assert len(engine.list_voices()) == 3

    def test_generate_model_not_found(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        with pytest.raises(FileNotFoundError, match="Piper model not found"):
            engine.generate("hello", "missing-voice", 1.0, tmp_path / "out.wav")

    def test_generate_model_not_found_message_contains_voice(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        with pytest.raises(FileNotFoundError) as exc_info:
            engine.generate("text", "en_US-amy-medium", 1.0, tmp_path / "out.wav")
        assert "en_US-amy-medium" in str(exc_info.value)

    def test_generate_piper_binary_not_found(self, tmp_path):
        """When the piper binary itself is missing, raise a helpful FileNotFoundError."""
        # Create a valid model file so we pass the model-exists check
        voice_id = "en_US-amy-medium"
        (tmp_path / f"{voice_id}.onnx").write_bytes(b"\x00")
        (tmp_path / f"{voice_id}.onnx.json").write_text("{}")
        engine = PiperEngine(voices_dir=tmp_path, piper_bin="piper_does_not_exist_xyz")
        with pytest.raises(FileNotFoundError, match="Piper executable not found"):
            engine.generate("hello", voice_id, 1.0, tmp_path / "out.wav")

    def test_size_mb_computed(self, tmp_path):
        data = b"\x00" * (2 * 1024 * 1024)  # 2 MiB
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(data)
        (tmp_path / "en_US-amy-medium.onnx.json").write_text("{}")
        engine = PiperEngine(voices_dir=tmp_path)
        v = engine.list_voices()[0]
        assert v.size_mb == pytest.approx(2.0, abs=0.1)


class TestPiperEngineCapabilities:
    def test_requires_gpu_is_false(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.requires_gpu is False

    def test_vram_estimate_is_zero(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.vram_estimate_mb == 0

    def test_supports_voice_cloning_is_false(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.supports_voice_cloning() is False

    def test_supported_emotions_is_empty(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.supported_emotions() == []

    def test_supported_languages_empty_when_no_voices(self, tmp_path):
        engine = PiperEngine(voices_dir=tmp_path)
        assert engine.supported_languages == []

    def test_supported_languages_reflects_installed_voices(self, tmp_path):
        for name in ["en_US-amy-medium", "de_DE-thorsten-medium"]:
            (tmp_path / f"{name}.onnx").write_bytes(b"\x00")
            (tmp_path / f"{name}.onnx.json").write_text("{}")
        engine = PiperEngine(voices_dir=tmp_path)
        langs = engine.supported_languages
        assert "en_US" in langs
        assert "de_DE" in langs
        assert langs == sorted(langs)  # must be sorted


class TestEngineRegistry:
    def test_empty_voices_dir(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        assert registry.list_voices() == []

    def test_voices_dir_not_exist(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path / "nonexistent")
        assert registry.list_voices() == []

    def test_discovers_piper_voice(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        (tmp_path / "en_US-amy-medium.onnx.json").write_text(
            json.dumps({"audio": {"sample_rate": 22050}})
        )
        registry = EngineRegistry(voices_dir=tmp_path)
        voices = registry.list_voices()
        assert len(voices) == 1
        assert voices[0].id == "en_US-amy-medium"

    def test_filter_by_engine(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        (tmp_path / "en_US-amy-medium.onnx.json").write_text("{}")
        registry = EngineRegistry(voices_dir=tmp_path)
        assert len(registry.list_voices(engine="piper")) == 1
        assert len(registry.list_voices(engine="coqui")) == 0

    def test_language_filter_exact_match(self, tmp_path):
        for name in ["en_US-amy-medium", "de_DE-thorsten-medium"]:
            (tmp_path / f"{name}.onnx").write_bytes(b"\x00")
            (tmp_path / f"{name}.onnx.json").write_text("{}")
        registry = EngineRegistry(voices_dir=tmp_path)
        en_voices = registry.list_voices(language="en_US")
        de_voices = registry.list_voices(language="de_DE")
        assert len(en_voices) == 1
        assert en_voices[0].id == "en_US-amy-medium"
        assert len(de_voices) == 1
        assert de_voices[0].id == "de_DE-thorsten-medium"

    def test_language_filter_no_match_returns_empty(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        (tmp_path / "en_US-amy-medium.onnx.json").write_text("{}")
        registry = EngineRegistry(voices_dir=tmp_path)
        assert registry.list_voices(language="ja") == []

    def test_find_voice_found(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        (tmp_path / "en_US-amy-medium.onnx.json").write_text(
            json.dumps({"audio": {"sample_rate": 22050}})
        )
        registry = EngineRegistry(voices_dir=tmp_path)
        result = registry.find_voice("en_US-amy-medium")
        assert result is not None
        engine_name, voice = result
        assert engine_name == "piper"
        assert voice.id == "en_US-amy-medium"

    def test_find_voice_not_found(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        assert registry.find_voice("nonexistent-voice") is None

    def test_get_engine_registered(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        engine = registry.get_engine("piper")
        assert engine.name == "piper"

    def test_get_engine_not_registered(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        with pytest.raises(KeyError, match="coqui"):
            registry.get_engine("coqui")

    def test_list_voices_all_engines(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        (tmp_path / "en_US-amy-medium.onnx.json").write_text("{}")
        registry = EngineRegistry(voices_dir=tmp_path)
        assert len(registry.list_voices()) == 1
        assert len(registry.list_voices(engine=None)) == 1

    def test_first_registered_engine_becomes_active(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        assert registry.active_name == "piper"

    def test_active_engine_returns_piper(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        assert registry.active_engine.name == "piper"

    def test_active_engine_raises_when_nothing_registered(self):
        registry = EngineRegistry()
        with pytest.raises(RuntimeError, match="No engine registered"):
            _ = registry.active_engine

    def test_set_active_switches_engine(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        # Register a second engine (using mock)
        from tests.conftest import MockTTSEngine
        mock = MockTTSEngine()
        registry.register(mock)
        assert registry.active_name == "piper"  # still piper (first registered)
        registry.set_active("mock")
        assert registry.active_name == "mock"
        assert registry.active_engine.name == "mock"

    def test_set_active_raises_for_unknown_engine(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        with pytest.raises(KeyError, match="coqui"):
            registry.set_active("coqui")

    def test_register_make_active_true(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        from tests.conftest import MockTTSEngine
        mock = MockTTSEngine()
        registry.register(mock, make_active=True)
        assert registry.active_name == "mock"

    def test_list_engines(self, tmp_path):
        registry = EngineRegistry(voices_dir=tmp_path)
        assert "piper" in registry.list_engines()

    def test_active_name_none_when_no_engines(self):
        registry = EngineRegistry()
        assert registry.active_name is None


class TestVoiceRegistryAlias:
    """VoiceRegistry must remain importable as an alias for EngineRegistry."""

    def test_voice_registry_is_alias(self):
        assert VoiceRegistry is EngineRegistry

    def test_voice_registry_behaves_identically(self, tmp_path):
        registry = VoiceRegistry(voices_dir=tmp_path)
        assert registry.list_voices() == []
