"""Voice manager — CRUD operations for voices across different TTS engines."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from ..tts.base import VoiceInfo

ProgressCallback = Callable[[int, int], None]  # (downloaded_bytes, total_bytes)

_DEFAULT_SAMPLE_RATE = 24000


@runtime_checkable
class VoiceManager(Protocol):
    """Protocol for engine-specific voice management."""

    @property
    def engine_name(self) -> str:
        """The TTS engine this manager handles."""
        ...

    def list_voices(self) -> list[VoiceInfo]:
        """Return all voices available for this engine."""
        ...

    def supports_custom_voices(self) -> bool:
        """Return True if voices can be added/removed by the user."""
        ...

    def add_voice(self, name: str, reference: Path | None = None) -> VoiceInfo:
        """Add a new voice.

        For cloning engines (XTTS, F5-TTS, StyleTTS2): *reference* is a .wav
        clip to copy into the voices directory — required.
        For Piper: *name* is used as the catalog voice_id and the model is
        downloaded from HuggingFace; *reference* is ignored.

        Raises:
            NotImplementedError: if the engine does not support custom voices.
            ValueError: if required arguments are missing or invalid.
        """
        ...

    def remove_voice(self, voice_id: str) -> bool:
        """Remove a voice.

        Returns True if the voice was found and removed, False if not found.

        Raises:
            NotImplementedError: if the engine does not support custom voices
                                  (e.g. Kokoro, Bark use fixed built-in presets).
        """
        ...


# ---------------------------------------------------------------------------
# CloneVoiceManager — shared by XTTS, F5-TTS, StyleTTS2
# ---------------------------------------------------------------------------


class CloneVoiceManager:
    """Voice manager for cloning engines that use .wav reference clips.

    Voices are stored as ``<voices_dir>/<name>.wav`` files.
    Adding a voice copies a user-supplied reference clip into the voices
    directory; removing a voice deletes the corresponding file.
    """

    def __init__(
        self,
        engine_name: str,
        voices_dir: Path,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
    ) -> None:
        self._engine_name = engine_name
        self.voices_dir = Path(voices_dir)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.sample_rate = sample_rate

    @property
    def engine_name(self) -> str:
        return self._engine_name

    def supports_custom_voices(self) -> bool:
        return True

    def list_voices(self) -> list[VoiceInfo]:
        """Scan voices_dir for .wav files."""
        voices: list[VoiceInfo] = []
        for wav in sorted(self.voices_dir.glob("*.wav")):
            voices.append(
                VoiceInfo(
                    id=wav.stem,
                    name=wav.stem.replace("_", " ").title(),
                    language="multilingual",
                    quality="excellent",
                    engine=self._engine_name,
                    sample_rate=self.sample_rate,
                    size_mb=round(wav.stat().st_size / (1024 * 1024), 1),
                    is_custom=True,
                )
            )
        return voices

    def add_voice(self, name: str, reference: Path | None = None) -> VoiceInfo:
        """Copy *reference* wav into voices_dir as ``<name>.wav``.

        Args:
            name: Voice identifier (used as the file stem).
            reference: Path to the source .wav clip — required.

        Raises:
            ValueError: if *reference* is not provided or does not exist.
        """
        if reference is None:
            raise ValueError(
                f"Engine '{self._engine_name}' requires a reference .wav clip. "
                "Provide the path as the second argument."
            )
        reference = Path(reference)
        if not reference.exists():
            raise ValueError(f"Reference clip not found: {reference}")

        dest = self.voices_dir / f"{name}.wav"
        shutil.copy2(reference, dest)
        return VoiceInfo(
            id=name,
            name=name.replace("_", " ").title(),
            language="multilingual",
            quality="excellent",
            engine=self._engine_name,
            sample_rate=self.sample_rate,
            size_mb=round(dest.stat().st_size / (1024 * 1024), 1),
            is_custom=True,
        )

    def remove_voice(self, voice_id: str) -> bool:
        """Delete ``<voice_id>.wav`` from voices_dir.

        Returns True if the file existed and was removed, False otherwise.
        """
        wav = self.voices_dir / f"{voice_id}.wav"
        if wav.exists():
            wav.unlink()
            return True
        return False


# ---------------------------------------------------------------------------
# PresetVoiceManager — Kokoro, Bark (read-only built-in presets)
# ---------------------------------------------------------------------------


class PresetVoiceManager:
    """Voice manager for engines with fixed built-in speaker presets.

    Adding or removing voices is not supported — these engines ship with a
    fixed set of speakers baked into the model checkpoint.
    """

    def __init__(self, engine_name: str, voices: list[VoiceInfo]) -> None:
        self._engine_name = engine_name
        self._voices = voices

    @property
    def engine_name(self) -> str:
        return self._engine_name

    def supports_custom_voices(self) -> bool:
        return False

    def list_voices(self) -> list[VoiceInfo]:
        return list(self._voices)

    def add_voice(self, name: str, reference: Path | None = None) -> VoiceInfo:
        raise NotImplementedError(
            f"Engine '{self._engine_name}' has no custom voice support. "
            "Its voices are fixed built-in speaker presets."
        )

    def remove_voice(self, voice_id: str) -> bool:
        raise NotImplementedError(
            f"Engine '{self._engine_name}' has no custom voice support. "
            "Its voices are fixed built-in speaker presets."
        )


# ---------------------------------------------------------------------------
# PiperVoiceManager — voices = installed ONNX models
# ---------------------------------------------------------------------------


class PiperVoiceManager:
    """Voice manager for Piper where voice management == model management.

    :meth:`add_voice` downloads the ONNX model from the HuggingFace catalog
    using :class:`~hypnoai.resources.model_manager.PiperModelManager`.
    :meth:`remove_voice` deletes the ONNX files via the same manager.

    The *reference* Path parameter is unused for Piper (voices are downloaded
    from the catalog by voice_id, not cloned from a clip).
    """

    def __init__(self, voices_dir: Path, piper_bin: str = "piper") -> None:
        from .model_manager import PiperModelManager
        from ..tts.piper_engine import PiperEngine

        self.voices_dir = Path(voices_dir)
        self._model_manager = PiperModelManager(voices_dir)
        self._piper_engine = PiperEngine(voices_dir, piper_bin=piper_bin)

    @property
    def engine_name(self) -> str:
        return "piper"

    def supports_custom_voices(self) -> bool:
        return True  # add_voice = catalog download

    def list_voices(self) -> list[VoiceInfo]:
        """Scan voices_dir for installed .onnx pairs."""
        return self._piper_engine.list_voices()

    def add_voice(
        self,
        name: str,
        reference: Path | None = None,
        progress: ProgressCallback | None = None,
    ) -> VoiceInfo:
        """Download a Piper voice from the HuggingFace catalog.

        Args:
            name: Piper voice_id (e.g. ``"en_US-amy-medium"``).
            reference: Unused for Piper (catalog download, not reference clip).
            progress: Optional ``(downloaded_bytes, total_bytes)`` callback.

        Raises:
            ValueError: if the voice_id is not found in the catalog.
            RuntimeError: on network or I/O errors.
        """
        self._model_manager.download(name, progress=progress)
        # Refresh voice list and find the newly installed voice.
        for voice in self.list_voices():
            if voice.id == name:
                return voice
        # Fallback if scan doesn't find it immediately (shouldn't happen).
        return VoiceInfo(
            id=name,
            name=name,
            language=name.split("-")[0] if "-" in name else "unknown",
            quality=name.split("-")[2] if name.count("-") >= 2 else "medium",
            engine="piper",
        )

    def remove_voice(self, voice_id: str) -> bool:
        """Remove an installed Piper voice (deletes .onnx files).

        Returns True if at least one file was removed, False if not found.
        """
        return self._model_manager.remove(voice_id)
