"""voices.list and voices.clone handlers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config import Config
from ...tts.voice_registry import VoiceRegistry
from ..session import SidecarSession


def handle_voices_list(session: SidecarSession, params: dict[str, Any]) -> dict:
    """List available voices for an engine.

    Optional params: engine (default "piper"), language
    Returns: {voices: [{id, name, language, quality, sample_rate, size_mb, is_custom}]}
    """
    cfg = Config.load()
    engine = params.get("engine", "piper")
    language = params.get("language")

    registry = VoiceRegistry(voices_dir=cfg.voices_dir, piper_bin=cfg.piper_bin)
    engine_filter = None if engine == "all" else engine
    voice_list = registry.list_voices(engine=engine_filter, language=language)

    return {
        "voices": [
            {
                "id": v.id,
                "name": v.name,
                "language": v.language,
                "quality": v.quality,
                "sample_rate": v.sample_rate,
                "size_mb": round(v.size_mb, 2),
                "is_custom": v.is_custom,
                "engine": v.engine,
            }
            for v in voice_list
        ]
    }


def handle_voices_clone(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Clone a voice from a reference audio file.

    Required params: name, reference_path, engine
    Returns: {voice_id, status}
    """
    name = params.get("name")
    if not name:
        raise ValueError("Missing required param 'name'")

    reference_path_str = params.get("reference_path")
    if not reference_path_str:
        raise ValueError("Missing required param 'reference_path'")

    engine_name = params.get("engine", "coqui")
    reference_path = Path(reference_path_str)

    if not reference_path.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_path}")

    cfg = Config.load()

    if engine_name == "coqui":
        from ...tts.coqui_engine import CoquiEngine
        tts = CoquiEngine(cfg.voices_dir, model_name=cfg.coqui_model, use_gpu=cfg.use_gpu)
    elif engine_name == "f5tts":
        from ...tts.f5tts_engine import F5TTSEngine
        tts = F5TTSEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
    elif engine_name == "styletts2":
        from ...tts.styletts_engine import StyleTTSEngine
        tts = StyleTTSEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
    else:
        raise ValueError(
            f"Engine {engine_name!r} does not support voice cloning. "
            "Supported: coqui, f5tts, styletts2."
        )

    voice_info = tts.clone_voice(name=name, reference_audio=reference_path)
    return {"voice_id": voice_info.id, "status": "ready"}
