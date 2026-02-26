"""Engine registry — discovers and indexes available TTS voices across engines."""
from __future__ import annotations

from pathlib import Path

from .base import TTSEngine, VoiceInfo
from .piper_engine import PiperEngine


class EngineRegistry:
    """Aggregates voices from all registered TTS engines.

    Engines are added via :meth:`register`. The Piper engine is
    automatically registered when *voices_dir* is provided.

    The first engine registered automatically becomes the *active* engine.
    Use :meth:`set_active` or the *make_active* parameter of :meth:`register`
    to change which engine is active.
    """

    def __init__(self, voices_dir: Path | None = None, piper_bin: str = "piper") -> None:
        self._engines: dict[str, TTSEngine] = {}
        self._active: str | None = None
        if voices_dir is not None:
            self.register(PiperEngine(voices_dir, piper_bin=piper_bin))

    def register(self, engine: TTSEngine, make_active: bool = False) -> None:
        """Register a TTS engine under its canonical name.

        The first engine registered becomes active automatically.
        Pass *make_active=True* to explicitly set the active engine.
        """
        self._engines[engine.name] = engine
        if self._active is None or make_active:
            self._active = engine.name

    def get_engine(self, name: str) -> TTSEngine:
        """Return the engine by name, or raise *KeyError* if not registered."""
        if name not in self._engines:
            raise KeyError(
                f"Engine not registered: {name!r}. "
                f"Available: {list(self._engines)}"
            )
        return self._engines[name]

    def set_active(self, name: str) -> None:
        """Set the active engine by name.

        Raises:
            KeyError: if *name* is not registered.
        """
        if name not in self._engines:
            raise KeyError(
                f"Engine not registered: {name!r}. "
                f"Available: {list(self._engines)}"
            )
        self._active = name

    @property
    def active_engine(self) -> TTSEngine:
        """The currently active engine.

        Raises:
            RuntimeError: if no engine has been registered.
        """
        if self._active is None:
            raise RuntimeError("No engine registered in EngineRegistry.")
        return self._engines[self._active]

    @property
    def active_name(self) -> str | None:
        """The name of the active engine, or *None* if nothing is registered."""
        return self._active

    def list_engines(self) -> list[str]:
        """Return the names of all registered engines."""
        return list(self._engines.keys())

    def list_voices(
        self,
        engine: str | None = None,
        language: str | None = None,
    ) -> list[VoiceInfo]:
        """Return all voices, optionally filtered by *engine* name and/or *language*.

        Language matching: an exact match on *voice.language* OR the special
        value ``"multilingual"`` (multi-language engines match any language filter).
        """
        voices: list[VoiceInfo] = []
        for eng_name, eng in self._engines.items():
            if engine is None or eng_name == engine:
                for voice in eng.list_voices():
                    if (
                        language is None
                        or voice.language == language
                        or voice.language == "multilingual"
                    ):
                        voices.append(voice)
        return voices

    def find_voice(self, voice_id: str) -> tuple[str, VoiceInfo] | None:
        """Search all engines for a voice by ID.

        Returns *(engine_name, VoiceInfo)* or *None* if not found.
        """
        for engine_name, eng in self._engines.items():
            for voice in eng.list_voices():
                if voice.id == voice_id:
                    return engine_name, voice
        return None


# Backward-compatibility alias — existing code importing VoiceRegistry continues to work.
VoiceRegistry = EngineRegistry
