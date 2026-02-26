"""TTS engine package.

Engine implementations (PiperEngine, CoquiEngine, KokoroEngine, etc.) are
intentionally **not** imported here.  Importing ``hypnoai.tts`` at CLI startup
must not trigger heavy ML-framework imports (torch, TTS, bark, …) for engines
that may not even be installed.  All engine classes are imported lazily, only
when the user explicitly selects that engine.
"""
from .base import TTSEngine, VoiceInfo
from .voice_registry import EngineRegistry, VoiceRegistry

__all__ = ["TTSEngine", "VoiceInfo", "EngineRegistry", "VoiceRegistry"]
