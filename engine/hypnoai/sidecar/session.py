"""Session state: temp directory and job registry for the HypnoAI sidecar."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Job dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RenderJob:
    """Tracks an async render job started by render.start."""

    job_id: str
    state: str = "pending"  # pending | rendering | done | failed | cancelled
    current_paragraph: int = 0
    total: int = 0
    chunk_paths: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    error: str | None = None
    # Internal: the background thread running the render
    _thread: threading.Thread | None = field(default=None, compare=False, repr=False)

    @property
    def elapsed_s(self) -> float:
        return time.time() - self.started_at


@dataclass
class DownloadJob:
    """Tracks an async model-download job started by models.download."""

    job_id: str
    model_name: str = ""
    state: str = "pending"  # pending | downloading | done | failed
    progress_pct: int = 0
    speed_mbps: float = 0.0
    error: str | None = None
    size_mb: float = 0.0
    _thread: threading.Thread | None = field(default=None, compare=False, repr=False)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SidecarSession:
    """Holds all mutable state for one sidecar process lifetime.

    * Creates a session-scoped temp directory under ``/tmp/hypnoai-<id>/``.
    * Owns render-job and download-job registries.
    * Thread-safe via an internal lock.
    """

    def __init__(self, tmp_root: Path | None = None) -> None:
        self._session_id = uuid.uuid4().hex[:12]
        if tmp_root is not None:
            self._tmp_root = Path(tmp_root)
        else:
            self._tmp_root = Path(f"/tmp/hypnoai-{self._session_id}")
        self._tmp_root.mkdir(parents=True, exist_ok=True)
        (self._tmp_root / "chunks").mkdir(exist_ok=True)
        (self._tmp_root / "output").mkdir(exist_ok=True)

        self._render_jobs: dict[str, RenderJob] = {}
        self._download_jobs: dict[str, DownloadJob] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Directory accessors

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def tmp_dir(self) -> Path:
        return self._tmp_root

    @property
    def chunks_dir(self) -> Path:
        return self._tmp_root / "chunks"

    @property
    def output_dir(self) -> Path:
        return self._tmp_root / "output"

    @property
    def preview_path(self) -> Path:
        return self._tmp_root / "preview.wav"

    # ------------------------------------------------------------------
    # Render jobs

    def create_render_job(self, total: int) -> RenderJob:
        job = RenderJob(job_id=uuid.uuid4().hex[:8], total=total)
        with self._lock:
            self._render_jobs[job.job_id] = job
        return job

    def get_render_job(self, job_id: str) -> RenderJob | None:
        return self._render_jobs.get(job_id)

    # ------------------------------------------------------------------
    # Download jobs

    def create_download_job(self, model_name: str, size_mb: float = 0.0) -> DownloadJob:
        job = DownloadJob(
            job_id=uuid.uuid4().hex[:8],
            model_name=model_name,
            size_mb=size_mb,
        )
        with self._lock:
            self._download_jobs[job.job_id] = job
        return job

    def get_download_job(self, job_id: str) -> DownloadJob | None:
        return self._download_jobs.get(job_id)
