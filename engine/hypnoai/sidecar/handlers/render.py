"""render.* handlers — full-session rendering and single-paragraph preview."""
from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import soundfile as sf

from ...audio.post_processor import PostProcessConfig, PostProcessor
from ...config import Config
from ...parser import inject_variables, parse
from ...render.cache import RenderCache
from ...render.pipeline import RenderPipeline
from ..session import RenderJob, SidecarSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_engine(engine: str, cfg: Config):
    """Instantiate a TTS engine by name (lazy imports, matching cli.py)."""
    if engine == "piper":
        from ...tts.piper_engine import PiperEngine
        return PiperEngine(cfg.voices_dir, piper_bin=cfg.piper_bin)
    if engine == "coqui":
        from ...tts.coqui_engine import CoquiEngine
        return CoquiEngine(cfg.voices_dir, model_name=cfg.coqui_model, use_gpu=cfg.use_gpu)
    if engine == "kokoro":
        from ...tts.kokoro_engine import KokoroEngine
        return KokoroEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
    if engine == "styletts2":
        from ...tts.styletts_engine import StyleTTSEngine
        return StyleTTSEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
    if engine == "f5tts":
        from ...tts.f5tts_engine import F5TTSEngine
        return F5TTSEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
    if engine == "bark":
        from ...tts.bark_engine import BarkEngine
        return BarkEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
    raise ValueError(f"Unknown engine: {engine!r}")


def _wav_duration_s(path: Path) -> float:
    """Return duration in seconds of a WAV file."""
    info = sf.info(str(path))
    return float(info.duration)


def _run_render_job(job: RenderJob, params: dict, cfg: Config) -> None:
    """Background thread: runs the render pipeline and updates *job* state."""
    job.state = "rendering"
    try:
        script_path = Path(params["script_path"])
        output_path = Path(params["output_path"])
        variables: dict = params.get("variables", {})
        voice: str = params.get("voice", cfg.default_voice)
        engine_name: str = params.get("engine", cfg.default_engine)
        speed: float = float(params.get("speed", cfg.default_speed))

        source = script_path.read_text(encoding="utf-8")
        source = inject_variables(source, variables)
        blocks = parse(source)

        # Count text + pause blocks to give progress total
        from ...parser.ast_nodes import TextBlock, PauseBlock
        renderable = [b for b in blocks if isinstance(b, (TextBlock, PauseBlock))]
        job.total = len(renderable)

        tts_engine = _build_engine(engine_name, cfg)
        cache = RenderCache(cfg.cache_dir) if cfg.cache_enabled else None
        max_workers = min(cfg.max_workers, tts_engine.max_workers)

        chunks_dir = output_path.parent / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)

        pipeline = RenderPipeline(tts_engine, cfg.sample_rate, cache, max_workers)

        # Wrap pipeline.render to track progress
        # We do this by hooking into the job object inside a sequential subclass
        render_job = pipeline.render(
            blocks=blocks,
            output_dir=chunks_dir,
            initial_voice=voice,
            initial_speed=speed,
            job_id=job.job_id,
        )

        job.chunk_paths = [str(p) for p in render_job.chunk_paths]
        job.current_paragraph = len(render_job.chunk_paths)

        # Post-process to final output
        pp_cfg = PostProcessConfig(
            crossfade_ms=cfg.crossfade_ms,
            warmth_db=cfg.warmth_db,
            normalize=cfg.normalize,
            target_lufs=cfg.target_lufs,
            limit=cfg.limit,
            limit_db=cfg.limit_db,
        )
        pp = PostProcessor(pp_cfg, sample_rate=cfg.sample_rate)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pp.process(render_job.chunk_paths, output_path)

        job.state = "done"
    except Exception as exc:  # noqa: BLE001
        job.state = "failed"
        job.error = str(exc)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_render_start(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Start an async render job.

    Required params: script_path, output_path
    Optional params: variables, voice, engine, speed, format
    Returns: {job_id}
    """
    for key in ("script_path", "output_path"):
        if key not in params:
            raise ValueError(f"Missing required param {key!r}")

    cfg = Config.load()

    # Count blocks first for total
    source = Path(params["script_path"]).read_text(encoding="utf-8")
    source_injected = inject_variables(source, params.get("variables", {}))
    blocks = parse(source_injected)

    from ...parser.ast_nodes import TextBlock, PauseBlock
    renderable = [b for b in blocks if isinstance(b, (TextBlock, PauseBlock))]
    job = session.create_render_job(total=len(renderable))

    thread = threading.Thread(
        target=_run_render_job,
        args=(job, params, cfg),
        daemon=True,
        name=f"render-{job.job_id}",
    )
    job._thread = thread
    thread.start()

    return {"job_id": job.job_id}


def handle_render_progress(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Poll the progress of a render job.

    Required params: job_id
    Returns: {state, current_paragraph, total, chunk_paths, elapsed_s}
    """
    job_id = params.get("job_id")
    if not job_id:
        raise ValueError("Missing required param 'job_id'")

    job = session.get_render_job(str(job_id))
    if job is None:
        raise ValueError(f"Unknown job_id: {job_id!r}")

    return {
        "state": job.state,
        "current_paragraph": job.current_paragraph,
        "total": job.total,
        "chunk_paths": job.chunk_paths,
        "elapsed_s": round(job.elapsed_s, 2),
        "error": job.error,
    }


def handle_render_cancel(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Cancel a running render job.

    Required params: job_id
    Returns: {cancelled}
    """
    job_id = params.get("job_id")
    if not job_id:
        raise ValueError("Missing required param 'job_id'")

    job = session.get_render_job(str(job_id))
    if job is None:
        raise ValueError(f"Unknown job_id: {job_id!r}")

    if job.state in ("rendering", "pending"):
        job.state = "cancelled"
        return {"cancelled": True}
    return {"cancelled": False}


def handle_render_preview(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Render a single paragraph for quick preview.

    Required params: text, voice, engine
    Optional params: speed
    Returns: {audio_path, duration_s}
    """
    text = params.get("text")
    if not text:
        raise ValueError("Missing required param 'text'")

    voice = params.get("voice")
    if not voice:
        raise ValueError("Missing required param 'voice'")

    engine_name = params.get("engine", "piper")
    speed = float(params.get("speed", 1.0))

    cfg = Config.load()
    tts_engine = _build_engine(engine_name, cfg)

    preview_path = session.preview_path
    tts_engine.generate(
        text=text,
        voice=voice,
        speed=speed,
        output_path=preview_path,
    )

    duration = _wav_duration_s(preview_path)
    return {"audio_path": str(preview_path), "duration_s": round(duration, 2)}
