"""TTS engine lifecycle management.

Single authoritative registry of all supported engines and helpers to
install/uninstall their Python packages via pip.

Design notes
------------
* The registry replaces the scattered ``_ENGINE_CAPABILITIES`` / ``_ENGINE_INFO``
  / ``_ENGINE_PKG`` constants that were duplicated across cli.py, sidecar
  handlers, and model_manager.py.
* ``is_installed()`` uses ``importlib.util.find_spec`` so that checking whether
  an engine is available does NOT trigger a heavy ML-framework import.
* ``install()`` / ``uninstall()`` delegate to pip via ``sys.executable -m pip``
  so they always target the correct Python environment.
* When *line_callback* is ``None`` the subprocess inherits the parent's
  stdout/stderr (suitable for CLI use where output flows to the terminal).
  When provided, lines are captured and delivered one at a time (suitable
  for the sidecar which streams them over JSON-RPC).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable

LineCallback = Callable[[str], None]


@dataclass
class EngineSpec:
    """Metadata and installation details for one TTS engine."""

    name: str
    """Canonical engine identifier used throughout the codebase."""

    pip_package: str
    """PyPI package name passed to ``pip install``, e.g. ``"suno-bark"``."""

    pip_extra: str
    """The ``extras_require`` key in ``pyproject.toml``, e.g. ``"bark"``.
    Used to install via ``pip install hypnoai[bark]``."""

    import_name: str
    """Top-level Python module to probe with ``find_spec``, e.g. ``"bark"``."""

    description: str
    """One-line human-readable description shown in the UI."""

    voice_type: str
    """How voices work: ``"catalog"`` (Piper ONNX), ``"preset"``
    (built-in speakers), or ``"clone"`` (user-supplied WAV clips)."""

    vram_mb: int
    """Approximate GPU VRAM required at inference time (0 = CPU-only)."""

    model_size_gb: float
    """Approximate size of the model weights auto-downloaded on first use."""

    languages: list[str]
    """BCP-47 language codes or ``["many"]`` / ``["multilingual"]``."""

    supports_cloning: bool
    """True if the engine can clone a voice from a reference WAV clip."""

    supports_emotions: bool
    """True if the engine exposes emotion/style parameters."""

    license: str
    """SPDX license identifier of the engine's upstream package."""

    emotions: list[str] = field(default_factory=list)
    """Emotion labels when ``supports_emotions`` is True."""


# ---------------------------------------------------------------------------
# Engine registry — single source of truth
# ---------------------------------------------------------------------------

ENGINES: dict[str, EngineSpec] = {
    "piper": EngineSpec(
        name="piper",
        pip_package="piper-tts",
        pip_extra="piper",
        import_name="piper",
        description="Fast CPU-only TTS; hundreds of voices across many languages.",
        voice_type="catalog",
        vram_mb=0,
        model_size_gb=0.0,  # voices downloaded individually via voices add
        languages=["many"],
        supports_cloning=False,
        supports_emotions=False,
        license="MIT",
    ),
    "coqui": EngineSpec(
        name="coqui",
        pip_package="coqui-tts",
        pip_extra="coqui",
        import_name="TTS",
        description="XTTS v2 — high-quality multilingual voice cloning.",
        voice_type="clone",
        vram_mb=4096,
        model_size_gb=2.5,
        languages=["multilingual"],
        supports_cloning=True,
        supports_emotions=False,
        license="CPML",
    ),
    "kokoro": EngineSpec(
        name="kokoro",
        pip_package="kokoro",
        pip_extra="kokoro",
        import_name="kokoro",
        description="Lightweight model with 30+ built-in presets across 9 languages.",
        voice_type="preset",
        vram_mb=2048,
        model_size_gb=0.3,
        languages=["en-us", "en-gb", "es", "fr-fr", "hi", "it", "ja", "pt", "zh"],
        supports_cloning=False,
        supports_emotions=False,
        license="Apache-2.0",
    ),
    "styletts2": EngineSpec(
        name="styletts2",
        pip_package="styletts2",
        pip_extra="styletts",
        import_name="styletts2",
        description="StyleTTS 2 — voice cloning with rich emotion controls.",
        voice_type="clone",
        vram_mb=3072,
        model_size_gb=1.2,
        languages=["en"],
        supports_cloning=True,
        supports_emotions=True,
        license="MIT",
        emotions=["neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised"],
    ),
    "f5tts": EngineSpec(
        name="f5tts",
        pip_package="f5-tts",
        pip_extra="f5tts",
        import_name="f5_tts",
        description="F5-TTS — zero-shot voice cloning for English and Chinese.",
        voice_type="clone",
        vram_mb=4096,
        model_size_gb=2.5,
        languages=["en", "zh"],
        supports_cloning=True,
        supports_emotions=False,
        license="MIT",
    ),
    "bark": EngineSpec(
        name="bark",
        pip_package="suno-bark",
        pip_extra="bark",
        import_name="bark",
        description="Bark — expressive multilingual TTS with 120 built-in speaker presets.",
        voice_type="preset",
        vram_mb=6144,
        model_size_gb=6.0,
        languages=["en", "de", "fr", "es", "it", "ja", "ko", "pl", "pt", "ru", "tr", "zh"],
        supports_cloning=False,
        supports_emotions=False,
        license="MIT",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_installed(name: str) -> bool:
    """Return True if *name*'s Python package is importable.

    Uses ``importlib.util.find_spec`` which checks the filesystem without
    executing any package code — safe even for large ML libraries.
    """
    spec = ENGINES.get(name)
    if spec is None:
        return False
    return importlib.util.find_spec(spec.import_name) is not None


def install(name: str, line_callback: LineCallback | None = None) -> None:
    """Install the engine's Python package via pip.

    Args:
        name: Engine identifier (must be a key in :data:`ENGINES`).
        line_callback: When provided, each line of pip's combined
            stdout/stderr output is passed to this callable (suitable for
            streaming progress to a GUI).  When ``None``, pip's output is
            inherited from the parent process (streams to the terminal).

    Raises:
        KeyError: If *name* is not a known engine.
        RuntimeError: If pip exits with a non-zero return code.
        EnvironmentError: If called inside a frozen PyInstaller bundle
            where pip is not available.
    """
    spec = ENGINES[name]  # propagate KeyError for unknown engines
    _check_not_frozen()
    cmd = [
        sys.executable, "-u", "-m", "pip", "install",
        spec.pip_package, "--no-warn-script-location",
    ]
    _run_pip(cmd, line_callback)


def uninstall(name: str, line_callback: LineCallback | None = None) -> None:
    """Uninstall the engine's Python package via pip.

    Args:
        name: Engine identifier (must be a key in :data:`ENGINES`).
        line_callback: Same streaming semantics as :func:`install`.

    Raises:
        KeyError: If *name* is not a known engine.
        RuntimeError: If pip exits with a non-zero return code.
        EnvironmentError: If called inside a frozen PyInstaller bundle.
    """
    spec = ENGINES[name]  # propagate KeyError for unknown engines
    _check_not_frozen()
    cmd = [sys.executable, "-u", "-m", "pip", "uninstall", spec.pip_package, "-y"]
    _run_pip(cmd, line_callback)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_not_frozen() -> None:
    """Raise EnvironmentError when running inside a PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        raise EnvironmentError(
            "Engine installation is not available in the packaged app binary. "
            "Use the app's built-in engine installer which manages a separate "
            "Python environment."
        )


def _run_pip(cmd: list[str], line_callback: LineCallback | None) -> None:
    """Execute *cmd* (a pip invocation), optionally capturing output."""
    if line_callback is None:
        # Stream directly to terminal — no capture.
        result = subprocess.run(cmd, check=False)
    else:
        # PYTHONUNBUFFERED ensures pip flushes each line immediately even when
        # writing to a pipe (which would otherwise be block-buffered).
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            line_callback(line.rstrip())
        proc.wait()
        result = proc

    if result.returncode != 0:
        raise RuntimeError(
            f"pip exited with code {result.returncode}. "
            "Check the output above for details."
        )
