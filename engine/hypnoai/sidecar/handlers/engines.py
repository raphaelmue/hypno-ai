"""engines.* handlers — engine discovery, selection, and lifecycle."""
from __future__ import annotations

import queue
import threading
from typing import Any, Generator

from ...config import Config
from ...resources.engine_manager import ENGINES, install, is_installed, uninstall
from ..session import SidecarSession


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
    if engine not in ENGINES:
        raise ValueError(
            f"Unknown engine: {engine!r}. "
            f"Valid engines: {', '.join(ENGINES)}"
        )
    Config.save_state("active_engine", engine)
    return {"engine": engine}


def handle_engines_list(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Return all engines with their capabilities and install status.

    Returns: {engines: [{name, installed, voice_type, vram_mb, model_size_gb,
                         languages, supports_cloning, supports_emotions,
                         license, description}]}
    """
    engines = []
    for spec in ENGINES.values():
        engines.append({
            "name": spec.name,
            "installed": is_installed(spec.name),
            "voice_type": spec.voice_type,
            "vram_mb": spec.vram_mb,
            "model_size_gb": spec.model_size_gb,
            "languages": spec.languages,
            "supports_cloning": spec.supports_cloning,
            "supports_emotions": spec.supports_emotions,
            "emotions": spec.emotions,
            "license": spec.license,
            "description": spec.description,
        })
    return {"engines": engines}


def handle_engines_install(
    session: SidecarSession, params: dict[str, Any]
) -> Generator[dict, None, None]:
    """Install an engine's Python package via pip (streaming).

    Required params: engine (str)
    Yields: {line: str, done: False} for each pip output line,
            {done: True} on success,
            {done: True, error: str} on failure.
    """
    engine = params.get("engine")
    if not engine:
        raise ValueError("Missing required param 'engine'")
    if engine not in ENGINES:
        raise ValueError(f"Unknown engine: {engine!r}. Valid: {', '.join(ENGINES)}")

    if is_installed(engine):
        yield {"done": True, "already_installed": True}
        return

    q: queue.Queue[tuple[str, str]] = queue.Queue()

    def _run() -> None:
        try:
            install(engine, line_callback=lambda line: q.put(("line", line)))
            q.put(("done", ""))
        except Exception as exc:  # noqa: BLE001
            q.put(("error", str(exc)))

    threading.Thread(target=_run, daemon=True, name=f"install-{engine}").start()

    while True:
        kind, value = q.get()
        if kind == "line":
            yield {"line": value, "done": False}
        elif kind == "done":
            yield {"done": True}
            break
        else:  # "error"
            yield {"done": True, "error": value}
            break


def handle_engines_uninstall(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Uninstall an engine's Python package via pip.

    Required params: engine (str)
    Returns: {uninstalled: True}
    """
    engine = params.get("engine")
    if not engine:
        raise ValueError("Missing required param 'engine'")
    if engine not in ENGINES:
        raise ValueError(f"Unknown engine: {engine!r}. Valid: {', '.join(ENGINES)}")

    if not is_installed(engine):
        return {"uninstalled": False, "reason": "not_installed"}

    try:
        uninstall(engine)
    except EnvironmentError as exc:
        raise RuntimeError(str(exc)) from exc

    return {"uninstalled": True}
