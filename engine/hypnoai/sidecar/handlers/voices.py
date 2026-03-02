"""Voice handlers — list, catalog, engines status, clone, and remove."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ...config import Config
from ...resources.model_manager import PiperModelManager
from ..session import SidecarSession

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Maps engine name → Python package required at runtime
_ENGINE_PKG: dict[str, str] = {
    "coqui": "TTS",
    "kokoro": "kokoro",
    "styletts2": "styletts2",
    "f5tts": "f5_tts",
    "bark": "bark",
}

# voice_type characterises what kind of voice management each engine supports
# catalog  — downloadable individual model files (Piper)
# preset   — fixed voices baked into one shared checkpoint (Kokoro, Bark)
# clone    — user-supplied .wav reference clips (Coqui, F5TTS, StyleTTS2)
_VOICE_TYPE: dict[str, str] = {
    "piper": "catalog",
    "coqui": "clone",
    "kokoro": "preset",
    "styletts2": "clone",
    "f5tts": "clone",
    "bark": "preset",
}

_ALL_ENGINES = ["piper", "coqui", "kokoro", "styletts2", "f5tts", "bark"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pkg_importable(pkg: str) -> bool:
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False


def _engine_available(engine_name: str, cfg: Config) -> bool:
    """Return True if the engine runtime is present on this machine."""
    if engine_name == "piper":
        return (
            bool(shutil.which(cfg.piper_bin))
            or Path(cfg.piper_bin).exists()
            or _pkg_importable("piper")
        )
    pkg = _ENGINE_PKG.get(engine_name)
    return _pkg_importable(pkg) if pkg else False


def _voices_for_engine(engine_name: str, cfg: Config) -> list[dict]:
    """Return serialised voice dicts for *engine_name* — no engine instantiation
    for preset engines so we never import heavy GPU libraries just to list voices."""

    if engine_name == "piper":
        from ...tts.piper_engine import PiperEngine
        try:
            return [_v(v) for v in PiperEngine(cfg.voices_dir, piper_bin=cfg.piper_bin).list_voices()]
        except Exception:  # noqa: BLE001
            return []

    if engine_name == "kokoro":
        from ...tts.kokoro_engine import _KOKORO_VOICES
        result = []
        for v_id in _KOKORO_VOICES:
            lang = "en-gb" if v_id.startswith(("bf", "bm")) else "en-us"
            result.append({
                "id": v_id,
                "name": v_id.replace("_", " ").title(),
                "language": lang,
                "quality": "high",
                "sample_rate": 24000,
                "size_mb": 0.0,
                "is_custom": False,
                "engine": "kokoro",
            })
        return result

    if engine_name == "bark":
        from ...tts.bark_engine import _BARK_ALL_SPEAKERS
        result = []
        for speaker in _BARK_ALL_SPEAKERS:
            lang = speaker.split("/")[1].split("_")[0] if "/" in speaker else "en"
            result.append({
                "id": speaker,
                "name": speaker,
                "language": lang,
                "quality": "high",
                "sample_rate": 24000,
                "size_mb": 0.0,
                "is_custom": False,
                "engine": "bark",
            })
        return result

    if engine_name in ("coqui", "f5tts", "styletts2"):
        if not cfg.voices_dir.exists():
            return []
        result = []
        for wav in sorted(cfg.voices_dir.glob("*.wav")):
            result.append({
                "id": wav.stem,
                "name": wav.stem.replace("_", " ").title(),
                "language": "multilingual",
                "quality": "excellent",
                "sample_rate": 24000,
                "size_mb": round(wav.stat().st_size / (1024 * 1024), 1),
                "is_custom": True,
                "engine": engine_name,
            })
        return result

    return []


def _v(voice) -> dict:
    return {
        "id": voice.id,
        "name": voice.name,
        "language": voice.language,
        "quality": voice.quality,
        "sample_rate": voice.sample_rate,
        "size_mb": round(voice.size_mb, 2),
        "is_custom": voice.is_custom,
        "engine": voice.engine,
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_voices_list(session: SidecarSession, params: dict[str, Any]) -> dict:
    """List available voices, optionally filtered by engine and language.

    Optional params: engine (default "piper" | "all"), language
    Returns: {voices: [{id, name, language, quality, sample_rate, size_mb, is_custom, engine}]}
    """
    cfg = Config.load()
    engine_param = params.get("engine", "piper")
    language = params.get("language")

    engines_to_query = _ALL_ENGINES if engine_param == "all" else [engine_param]

    # For "all", deduplicate clone-engine .wav voices — they share the same
    # voices_dir, so we only include them once under the first installed
    # clone engine to avoid showing the same voice three times.
    clone_engines = ("coqui", "f5tts", "styletts2")
    clone_included = False

    all_voices: list[dict] = []
    for eng in engines_to_query:
        if engine_param == "all" and eng in clone_engines:
            if not _engine_available(eng, cfg):
                continue
            if clone_included:
                continue
            clone_included = True
        all_voices.extend(_voices_for_engine(eng, cfg))

    if language:
        all_voices = [
            v for v in all_voices
            if v["language"].startswith(language) or v["language"] == "multilingual"
        ]

    return {"voices": all_voices}


def handle_voices_engines(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Return per-engine status and current voice list.

    Returns: {
        engines: [{
            name, installed, voice_type,   // "catalog" | "preset" | "clone"
            voices: [VoiceInfo...]
        }]
    }
    """
    cfg = Config.load()

    result = []
    for eng in _ALL_ENGINES:
        installed = _engine_available(eng, cfg)
        voices = _voices_for_engine(eng, cfg)
        result.append({
            "name": eng,
            "installed": installed,
            "voice_type": _VOICE_TYPE[eng],
            "voices": voices,
        })

    return {"engines": result}


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


def handle_voices_catalog(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Fetch the Piper voice catalog from HuggingFace and mark installed voices.

    Returns: {voices: [{id, name, language, quality, size_mb, installed}]}
    """
    cfg = Config.load()
    mgr = PiperModelManager(cfg.voices_dir)

    try:
        catalog = mgr.get_catalog()
    except RuntimeError as exc:
        raise RuntimeError(f"Failed to fetch voice catalog: {exc}") from exc

    installed_ids = {m.id for m in mgr.list_installed()}

    voices = [
        {
            "id": voice_id,
            "name": voice_id,
            "language": info.language,
            "quality": info.quality,
            "size_mb": round(info.size_mb, 1),
            "installed": voice_id in installed_ids,
        }
        for voice_id, info in catalog.items()
    ]
    voices.sort(key=lambda v: (v["language"], v["id"]))
    return {"voices": voices}


def handle_voices_add(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Copy a reference .wav clip into the voices directory as a named custom voice.

    Required params: name (str), source_path (str), engine (str)
    Returns: {voice_id: str}
    """
    name = params.get("name")
    source_path_str = params.get("source_path")
    engine = params.get("engine")

    if not name or not source_path_str or not engine:
        raise ValueError("Missing required params: name, source_path, engine")

    if engine not in ("coqui", "f5tts", "styletts2"):
        raise ValueError(
            f"Engine {engine!r} does not support custom voices. "
            "Use coqui, f5tts, or styletts2."
        )

    source = Path(source_path_str)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source_path_str!r}")
    if source.suffix.lower() != ".wav":
        raise ValueError("Reference clip must be a .wav file")

    cfg = Config.load()
    cfg.voices_dir.mkdir(parents=True, exist_ok=True)
    dest = cfg.voices_dir / f"{name}.wav"
    shutil.copy2(source, dest)

    return {"voice_id": name}


def handle_voices_remove(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Remove an installed voice.

    Required params: voice_id (str), engine (str)
    Returns: {removed: True}
    """
    voice_id = params.get("voice_id")
    if not voice_id:
        raise ValueError("Missing required param 'voice_id'")

    engine = params.get("engine", "piper")
    cfg = Config.load()

    if engine == "piper":
        mgr = PiperModelManager(cfg.voices_dir)
        removed = mgr.remove(voice_id)
        if not removed:
            raise ValueError(f"Piper voice not installed: {voice_id!r}")
    elif engine in ("coqui", "f5tts", "styletts2"):
        ref_audio = cfg.voices_dir / f"{voice_id}.wav"
        if not ref_audio.exists():
            raise ValueError(f"Custom voice not found: {voice_id!r}")
        ref_audio.unlink()
    else:
        raise ValueError(f"Cannot remove voices for engine {engine!r}")

    return {"removed": True}
