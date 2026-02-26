"""Tests for the VoiceManager implementations."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from hypnoai.resources.voice_manager import CloneVoiceManager, PresetVoiceManager, PiperVoiceManager
from hypnoai.tts.base import VoiceInfo


# ---------------------------------------------------------------------------
# CloneVoiceManager (used by coqui, f5tts, styletts2)
# ---------------------------------------------------------------------------


class TestCloneVoiceManager:
    def test_engine_name(self, tmp_path):
        vm = CloneVoiceManager("coqui", tmp_path)
        assert vm.engine_name == "coqui"

    def test_supports_custom_voices(self, tmp_path):
        vm = CloneVoiceManager("coqui", tmp_path)
        assert vm.supports_custom_voices() is True

    def test_list_voices_empty(self, tmp_path):
        vm = CloneVoiceManager("coqui", tmp_path)
        assert vm.list_voices() == []

    def test_list_voices_discovers_wav(self, tmp_path):
        (tmp_path / "narrator.wav").write_bytes(b"\x00" * 200)
        vm = CloneVoiceManager("coqui", tmp_path)
        voices = vm.list_voices()
        assert len(voices) == 1
        v = voices[0]
        assert v.id == "narrator"
        assert v.engine == "coqui"
        assert v.is_custom is True
        assert v.language == "multilingual"

    def test_list_voices_multiple(self, tmp_path):
        for name in ["alice", "bob", "carol"]:
            (tmp_path / f"{name}.wav").write_bytes(b"\x00" * 100)
        vm = CloneVoiceManager("coqui", tmp_path)
        assert len(vm.list_voices()) == 3

    def test_add_voice_copies_wav(self, tmp_path):
        ref = tmp_path / "source.wav"
        ref.write_bytes(b"WAV DATA")
        voices_dir = tmp_path / "voices"
        voices_dir.mkdir()

        vm = CloneVoiceManager("coqui", voices_dir)
        voice = vm.add_voice("speaker1", ref)

        assert voice.id == "speaker1"
        assert voice.engine == "coqui"
        assert voice.is_custom is True
        dest = voices_dir / "speaker1.wav"
        assert dest.exists()
        assert dest.read_bytes() == b"WAV DATA"

    def test_add_voice_without_reference_raises_value_error(self, tmp_path):
        vm = CloneVoiceManager("coqui", tmp_path)
        with pytest.raises(ValueError, match="requires a reference"):
            vm.add_voice("speaker1", None)

    def test_add_voice_nonexistent_reference_raises_value_error(self, tmp_path):
        vm = CloneVoiceManager("coqui", tmp_path)
        with pytest.raises(ValueError, match="not found"):
            vm.add_voice("speaker1", tmp_path / "nonexistent.wav")

    def test_remove_voice_found(self, tmp_path):
        wav = tmp_path / "narrator.wav"
        wav.write_bytes(b"\x00" * 100)
        vm = CloneVoiceManager("coqui", tmp_path)
        removed = vm.remove_voice("narrator")
        assert removed is True
        assert not wav.exists()

    def test_remove_voice_not_found(self, tmp_path):
        vm = CloneVoiceManager("coqui", tmp_path)
        assert vm.remove_voice("nonexistent") is False

    def test_works_for_f5tts_engine_name(self, tmp_path):
        vm = CloneVoiceManager("f5tts", tmp_path)
        assert vm.engine_name == "f5tts"
        (tmp_path / "test.wav").write_bytes(b"\x00" * 50)
        assert vm.list_voices()[0].engine == "f5tts"


# ---------------------------------------------------------------------------
# PresetVoiceManager (used by kokoro, bark)
# ---------------------------------------------------------------------------


class TestPresetVoiceManager:
    @pytest.fixture
    def preset_voices(self):
        return [
            VoiceInfo(id="af", name="Af", language="en-us", quality="high", engine="kokoro"),
            VoiceInfo(id="am_adam", name="Am Adam", language="en-us", quality="high", engine="kokoro"),
        ]

    def test_engine_name(self, preset_voices):
        vm = PresetVoiceManager("kokoro", preset_voices)
        assert vm.engine_name == "kokoro"

    def test_supports_custom_voices_false(self, preset_voices):
        vm = PresetVoiceManager("kokoro", preset_voices)
        assert vm.supports_custom_voices() is False

    def test_list_voices_returns_presets(self, preset_voices):
        vm = PresetVoiceManager("kokoro", preset_voices)
        voices = vm.list_voices()
        assert len(voices) == 2
        ids = [v.id for v in voices]
        assert "af" in ids
        assert "am_adam" in ids

    def test_list_voices_returns_copy(self, preset_voices):
        vm = PresetVoiceManager("kokoro", preset_voices)
        v1 = vm.list_voices()
        v2 = vm.list_voices()
        assert v1 is not v2  # returns new list each time

    def test_add_voice_raises_not_implemented(self, preset_voices):
        vm = PresetVoiceManager("kokoro", preset_voices)
        with pytest.raises(NotImplementedError, match="no custom voice support"):
            vm.add_voice("new_voice")

    def test_remove_voice_raises_not_implemented(self, preset_voices):
        vm = PresetVoiceManager("kokoro", preset_voices)
        with pytest.raises(NotImplementedError, match="no custom voice support"):
            vm.remove_voice("af")

    def test_bark_engine_name(self):
        vm = PresetVoiceManager("bark", [])
        assert vm.engine_name == "bark"


# ---------------------------------------------------------------------------
# PiperVoiceManager
# ---------------------------------------------------------------------------


class TestPiperVoiceManager:
    def test_engine_name(self, tmp_path):
        vm = PiperVoiceManager(tmp_path)
        assert vm.engine_name == "piper"

    def test_supports_custom_voices(self, tmp_path):
        vm = PiperVoiceManager(tmp_path)
        assert vm.supports_custom_voices() is True

    def test_list_voices_empty(self, tmp_path):
        vm = PiperVoiceManager(tmp_path)
        assert vm.list_voices() == []

    def test_list_voices_detects_installed_onnx(self, tmp_path):
        import json
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00" * 100)
        (tmp_path / "en_US-amy-medium.onnx.json").write_text(
            json.dumps({"audio": {"sample_rate": 22050}})
        )
        vm = PiperVoiceManager(tmp_path)
        voices = vm.list_voices()
        assert len(voices) == 1
        assert voices[0].id == "en_US-amy-medium"

    def test_add_voice_calls_model_manager_download(self, tmp_path):
        from hypnoai.resources.model_manager import PiperModelManager

        vm = PiperVoiceManager(tmp_path)
        with patch.object(PiperModelManager, "download") as mock_dl:
            # add_voice calls download then scans for the file
            # Since download is mocked (no file created), list_voices returns []
            # and the fallback VoiceInfo is returned
            result = vm.add_voice("en_US-ryan-medium")
        mock_dl.assert_called_once_with("en_US-ryan-medium")
        # Fallback VoiceInfo has the correct id
        assert result.id == "en_US-ryan-medium"

    def test_remove_voice_returns_true_when_found(self, tmp_path):
        (tmp_path / "en_US-amy-medium.onnx").write_bytes(b"\x00")
        vm = PiperVoiceManager(tmp_path)
        removed = vm.remove_voice("en_US-amy-medium")
        assert removed is True
        assert not (tmp_path / "en_US-amy-medium.onnx").exists()

    def test_remove_voice_returns_false_when_not_found(self, tmp_path):
        vm = PiperVoiceManager(tmp_path)
        assert vm.remove_voice("en_US-nobody-medium") is False
