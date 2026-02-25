"""Voice registry — discovers and indexes available TTS voices across engines."""
from __future__ import annotations

from pathlib import Path

from .base import TTSEngine, VoiceInfo
from .piper_engine import PiperEngine


class VoiceRegistry:
    """Aggregates voices from all registered TTS engines.

    Engines are added via :meth:`register`. The Piper engine is
    automatically registered when *voices_dir* is provided.
    """

    def __init__(self, voices_dir: Path | None = None, piper_bin: str = "piper") -> None:
        self._engines: dict[str, TTSEngine] = {}
        if voices_dir is not None:
            self.register(PiperEngine(voices_dir, piper_bin=piper_bin))

    def register(self, engine: TTSEngine) -> None:
        """Register a TTS engine under its canonical name."""
        self._engines[engine.name] = engine

    def get_engine(self, name: str) -> TTSEngine:
        """Return the engine by name, or raise *KeyError* if not registered."""
        if name not in self._engines:
            raise KeyError(
                f"Engine not registered: {name!r}. "
                f"Available: {list(self._engines)}"
            )
        return self._engines[name]

    def list_voices(self, engine: str | None = None) -> list[VoiceInfo]:
        """Return all voices, optionally filtered by *engine* name."""
        voices: list[VoiceInfo] = []
        for eng_name, eng in self._engines.items():
            if engine is None or eng_name == engine:
                voices.extend(eng.list_voices())
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
