"""engines.* handlers — active engine selection."""
from __future__ import annotations

from typing import Any

from ...config import Config
from ..session import SidecarSession

_VALID_ENGINES = ["piper", "coqui", "kokoro", "styletts2", "f5tts", "bark"]


def handle_engines_active(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Return the currently active TTS engine.

    Returns: {engine: str}
    """
    cfg = Config.load()
    return {"engine": cfg.default_engine}


def handle_engines_use(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Set the active TTS engine (persisted to runtime state file).

    Required params: engine (str)
    Returns: {engine: str}
    """
    engine = params.get("engine")
    if not engine:
        raise ValueError("Missing required param 'engine'")
    if engine not in _VALID_ENGINES:
        raise ValueError(
            f"Unknown engine: {engine!r}. "
            f"Valid engines: {', '.join(_VALID_ENGINES)}"
        )
    Config.save_state("active_engine", engine)
    return {"engine": engine}
