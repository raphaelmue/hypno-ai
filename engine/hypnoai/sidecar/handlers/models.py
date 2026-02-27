"""models.* handlers — TTS engine and voice-pack lifecycle management."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from ...config import Config
from ...resources.model_manager import (
    BarkModelManager,
    CoquiModelManager,
    F5TTSModelManager,
    KokoroModelManager,
    PiperModelManager,
    StyleTTSModelManager,
)
from ..session import DownloadJob, SidecarSession

# ---------------------------------------------------------------------------
# Engine metadata (mirrors cli._ENGINE_CAPABILITIES)
# ---------------------------------------------------------------------------

_ENGINE_INFO: list[dict] = [
    {
        "name": "piper",
        "type": "tts",
        "requires_gpu": False,
        "vram_mb": 0,
        "size_mb": 80,
        "license": "MIT",
        "install_hint": "pip install hypnoai[piper]",
    },
    {
        "name": "coqui-xtts-v2",
        "type": "tts",
        "requires_gpu": True,
        "vram_mb": 4096,
        "size_mb": 1800,
        "license": "CPML",
        "install_hint": "pip install hypnoai[coqui]",
    },
    {
        "name": "kokoro",
        "type": "tts",
        "requires_gpu": True,
        "vram_mb": 2048,
        "size_mb": 500,
        "license": "Apache-2.0",
        "install_hint": "pip install hypnoai[kokoro]",
    },
    {
        "name": "styletts2",
        "type": "tts",
        "requires_gpu": True,
        "vram_mb": 3072,
        "size_mb": 1200,
        "license": "MIT",
        "install_hint": "pip install hypnoai[styletts]",
    },
    {
        "name": "f5tts",
        "type": "tts",
        "requires_gpu": True,
        "vram_mb": 4096,
        "size_mb": 1500,
        "license": "MIT",
        "install_hint": "pip install hypnoai[f5tts]",
    },
    {
        "name": "bark",
        "type": "tts",
        "requires_gpu": True,
        "vram_mb": 6144,
        "size_mb": 6000,
        "license": "MIT",
        "install_hint": "pip install hypnoai[bark]",
    },
]


def _gpu_available() -> bool:
    try:
        import torch  # type: ignore
        return torch.cuda.is_available()
    except ImportError:
        return False


def _vram_total_mb() -> int:
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
    except ImportError:
        pass
    return 0


def _disk_used_mb(voices_dir: Path) -> float:
    if not voices_dir.exists():
        return 0.0
    total = sum(f.stat().st_size for f in voices_dir.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def _piper_installed() -> bool:
    try:
        import piper  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False


def _engine_installed(name: str) -> bool:
    """Check if an engine's Python package is importable."""
    pkg_map = {
        "piper": "piper",
        "coqui-xtts-v2": "TTS",
        "kokoro": "kokoro",
        "styletts2": "styletts2",
        "f5tts": "f5_tts",
        "bark": "bark",
    }
    pkg = pkg_map.get(name)
    if not pkg:
        return False
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_models_status(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Return GPU/disk status.

    Returns: {gpu_available, vram_total_mb, disk_used_mb}
    """
    cfg = Config.load()
    return {
        "gpu_available": _gpu_available(),
        "vram_total_mb": _vram_total_mb(),
        "disk_used_mb": round(_disk_used_mb(cfg.voices_dir), 1),
    }


def handle_models_list(session: SidecarSession, params: dict[str, Any]) -> dict:
    """List installed engines/voice packs and the downloadable catalog.

    Returns: {installed: [...], available_for_download: [...]}
    """
    cfg = Config.load()

    # Installed Piper voice packs
    piper_mgr = PiperModelManager(cfg.voices_dir)
    installed_piper = piper_mgr.list_installed()

    installed: list[dict] = [
        {
            "name": m.id,
            "type": "voice",
            "engine": "piper",
            "size_mb": round(m.size_mb, 1),
            "loaded": False,
            "voices": [m.id],
            "license": m.license,
        }
        for m in installed_piper
    ]

    # Add installed engine packages (no voice packs — pip-managed)
    for eng in _ENGINE_INFO:
        if eng["name"] != "piper" and _engine_installed(eng["name"]):
            installed.append(
                {
                    "name": eng["name"],
                    "type": eng["type"],
                    "engine": eng["name"],
                    "size_mb": eng["size_mb"],
                    "loaded": False,
                    "voices": [],
                    "license": eng["license"],
                }
            )

    # Available for download (engines not yet installed)
    available: list[dict] = []
    for eng in _ENGINE_INFO:
        if not _engine_installed(eng["name"]):
            available.append(
                {
                    "name": eng["name"],
                    "type": eng["type"],
                    "size_mb": eng["size_mb"],
                    "license": eng["license"],
                    "requires_gpu": eng["requires_gpu"],
                    "install_hint": eng["install_hint"],
                }
            )

    return {"installed": installed, "available_for_download": available}


def handle_models_download(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Start an async download of a Piper voice pack.

    Required params: model (voice pack ID, e.g. "en_US-amy-medium")
    Returns: {job_id, size_mb}
    """
    model_id = params.get("model")
    if not model_id:
        raise ValueError("Missing required param 'model'")

    cfg = Config.load()
    piper_mgr = PiperModelManager(cfg.voices_dir)

    # Estimate size from catalog if available
    size_mb = 0.0
    try:
        catalog = piper_mgr.get_catalog()
        if model_id in catalog:
            size_mb = catalog[model_id].size_mb
    except RuntimeError:
        pass

    job = session.create_download_job(model_name=model_id, size_mb=size_mb)

    def _run() -> None:
        job.state = "downloading"
        start = time.monotonic()
        downloaded_bytes = [0]
        total_bytes = [0]

        def _progress(dl: int, total: int) -> None:
            downloaded_bytes[0] = dl
            total_bytes[0] = total
            if total > 0:
                job.progress_pct = int(dl * 100 / total)
            elapsed = time.monotonic() - start
            if elapsed > 0 and dl > 0:
                job.speed_mbps = round((dl / elapsed) / (1024 * 1024), 2)

        try:
            piper_mgr.download(model_id, progress=_progress)
            job.progress_pct = 100
            job.state = "done"
        except Exception as exc:  # noqa: BLE001
            job.state = "failed"
            job.error = str(exc)

    thread = threading.Thread(target=_run, daemon=True, name=f"download-{job.job_id}")
    job._thread = thread
    thread.start()

    return {"job_id": job.job_id, "size_mb": round(size_mb, 1)}


def handle_models_download_progress(
    session: SidecarSession, params: dict[str, Any]
) -> dict:
    """Poll the progress of a download job.

    Required params: job_id
    Returns: {state, progress_pct, speed_mbps, error}
    """
    job_id = params.get("job_id")
    if not job_id:
        raise ValueError("Missing required param 'job_id'")

    job = session.get_download_job(str(job_id))
    if job is None:
        raise ValueError(f"Unknown job_id: {job_id!r}")

    return {
        "state": job.state,
        "progress_pct": job.progress_pct,
        "speed_mbps": job.speed_mbps,
        "error": job.error,
    }


def handle_models_remove(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Remove an installed Piper voice pack.

    Required params: model (voice pack ID)
    Returns: {freed_mb}
    """
    model_id = params.get("model")
    if not model_id:
        raise ValueError("Missing required param 'model'")

    cfg = Config.load()
    piper_mgr = PiperModelManager(cfg.voices_dir)

    # Measure size before removal
    freed = 0.0
    for ext in (".onnx", ".onnx.json"):
        p = cfg.voices_dir / f"{model_id}{ext}"
        if p.exists():
            freed += p.stat().st_size

    removed = piper_mgr.remove(model_id)
    if not removed:
        raise ValueError(f"Voice pack not installed: {model_id!r}")

    return {"freed_mb": round(freed / (1024 * 1024), 1)}
