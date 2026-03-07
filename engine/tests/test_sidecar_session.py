"""Tests for SidecarSession temp directory and job registry."""
from __future__ import annotations

from hypnoai.sidecar.session import SidecarSession


def test_temp_dirs_created(tmp_path):
    session = SidecarSession(tmp_root=tmp_path / "s")
    assert session.tmp_dir.exists()
    assert session.chunks_dir.exists()
    assert session.output_dir.exists()


def test_session_id_unique(tmp_path):
    s1 = SidecarSession(tmp_root=tmp_path / "s1")
    s2 = SidecarSession(tmp_root=tmp_path / "s2")
    assert s1.session_id != s2.session_id


def test_render_job_lifecycle(tmp_path):
    session = SidecarSession(tmp_root=tmp_path / "s")

    job = session.create_render_job(total=5)
    assert job.total == 5
    assert job.state == "pending"
    assert job.current_paragraph == 0

    retrieved = session.get_render_job(job.job_id)
    assert retrieved is job


def test_render_job_not_found(tmp_path):
    session = SidecarSession(tmp_root=tmp_path / "s")
    assert session.get_render_job("nonexistent") is None


def test_download_job_lifecycle(tmp_path):
    session = SidecarSession(tmp_root=tmp_path / "s")

    job = session.create_download_job(model_name="en_US-amy-medium", size_mb=25.0)
    assert job.model_name == "en_US-amy-medium"
    assert job.size_mb == 25.0
    assert job.state == "pending"

    retrieved = session.get_download_job(job.job_id)
    assert retrieved is job


def test_download_job_not_found(tmp_path):
    session = SidecarSession(tmp_root=tmp_path / "s")
    assert session.get_download_job("nonexistent") is None


def test_preview_path(tmp_path):
    session = SidecarSession(tmp_root=tmp_path / "s")
    assert session.preview_path == session.tmp_dir / "preview.wav"


def test_elapsed_s_increases(tmp_path):
    import time
    session = SidecarSession(tmp_root=tmp_path / "s")
    job = session.create_render_job(total=1)
    time.sleep(0.05)
    assert job.elapsed_s >= 0.05


def test_multiple_jobs(tmp_path):
    session = SidecarSession(tmp_root=tmp_path / "s")
    j1 = session.create_render_job(total=3)
    j2 = session.create_render_job(total=7)
    assert j1.job_id != j2.job_id
    assert session.get_render_job(j1.job_id) is j1
    assert session.get_render_job(j2.job_id) is j2
