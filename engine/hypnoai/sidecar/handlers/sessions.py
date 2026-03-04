"""Session management RPC handlers.

Each session is a folder in the sessions directory::

    {sessions_dir}/
    └── {session-id}/
        ├── meta.json    # name, created_at, modified_at, render_settings
        └── script.hypno # script content

The output audio defaults to ``{session-id}/output.wav``.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a session name to a filesystem-safe slug."""
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "session"


def _unique_slug(sessions_dir: Path, base_slug: str) -> str:
    """Return a slug that does not conflict with existing session directories."""
    if not (sessions_dir / base_slug).exists():
        return base_slug
    counter = 2
    while (sessions_dir / f"{base_slug}-{counter}").exists():
        counter += 1
    return f"{base_slug}-{counter}"


def _get_sessions_dir() -> Path:
    sessions_dir_str = Config.load_state("sessions_dir")
    if sessions_dir_str:
        return Path(sessions_dir_str)
    default = Path.home() / ".hypnoai" / "sessions"
    default.mkdir(parents=True, exist_ok=True)
    return default


def _load_meta(session_dir: Path) -> dict:
    meta_file = session_dir / "meta.json"
    if meta_file.exists():
        with open(meta_file) as f:
            return json.load(f)
    return {
        "id": session_dir.name,
        "name": session_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "modified_at": datetime.now(timezone.utc).isoformat(),
        "render_settings": {},
        "is_draft": False,
    }


def _save_meta(session_dir: Path, meta: dict) -> None:
    with open(session_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)


def _session_info(session_dir: Path) -> dict:
    meta = _load_meta(session_dir)
    return {
        "id": meta.get("id", session_dir.name),
        "name": meta.get("name", session_dir.name),
        "path": str(session_dir),
        "modified_at": meta.get("modified_at", ""),
        "is_draft": meta.get("is_draft", False),
    }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_sessions_list(_session: Any, _params: dict[str, Any]) -> dict:
    sessions_dir = _get_sessions_dir()
    sessions = []
    if sessions_dir.exists():
        dirs = sorted(
            (d for d in sessions_dir.iterdir() if d.is_dir() and (d / "meta.json").exists()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for d in dirs:
            sessions.append(_session_info(d))
    return {"sessions": sessions, "sessions_dir": str(sessions_dir)}


def handle_sessions_create(_session: Any, params: dict[str, Any]) -> dict:
    sessions_dir = _get_sessions_dir()
    name = params.get("name") or "New Session"
    session_id = _unique_slug(sessions_dir, _slugify(name))
    session_dir = sessions_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "id": session_id,
        "name": name,
        "created_at": now,
        "modified_at": now,
        "is_draft": bool(params.get("is_draft", False)),
        "render_settings": params.get("render_settings") or {},
    }
    _save_meta(session_dir, meta)

    script_file = session_dir / "script.hypno"
    script_file.write_text(params.get("script_content") or "", encoding="utf-8")

    return {
        "id": session_id,
        "name": name,
        "path": str(session_dir),
        "script_path": str(script_file),
        "output_path": str(session_dir / "output.wav"),
    }


def handle_sessions_load(_session: Any, params: dict[str, Any]) -> dict:
    sessions_dir = _get_sessions_dir()
    session_id = params["id"]
    session_dir = sessions_dir / session_id
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Session {session_id!r} not found")

    meta = _load_meta(session_dir)
    script_file = session_dir / "script.hypno"
    script_content = script_file.read_text(encoding="utf-8") if script_file.exists() else ""

    return {
        "id": session_id,
        "name": meta.get("name", session_id),
        "path": str(session_dir),
        "script_content": script_content,
        "script_path": str(script_file),
        "output_path": str(session_dir / "output.wav"),
        "render_settings": meta.get("render_settings") or {},
        "variables": meta.get("variables") or {},
        "is_draft": meta.get("is_draft", False),
        "modified_at": meta.get("modified_at", ""),
    }


def handle_sessions_save(_session: Any, params: dict[str, Any]) -> dict:
    sessions_dir = _get_sessions_dir()
    session_id = params["id"]
    session_dir = sessions_dir / session_id
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Session {session_id!r} not found")

    meta = _load_meta(session_dir)
    now = datetime.now(timezone.utc).isoformat()
    meta["modified_at"] = now

    if "name" in params:
        meta["name"] = params["name"]
    if "render_settings" in params:
        meta["render_settings"] = params["render_settings"]
    if "variables" in params:
        meta["variables"] = params["variables"]
    if "is_draft" in params:
        meta["is_draft"] = bool(params["is_draft"])

    _save_meta(session_dir, meta)

    if "script_content" in params:
        script_file = session_dir / "script.hypno"
        script_file.write_text(params["script_content"], encoding="utf-8")

    return {"id": session_id, "modified_at": now}


def handle_sessions_delete(_session: Any, params: dict[str, Any]) -> dict:
    sessions_dir = _get_sessions_dir()
    session_id = params["id"]
    session_dir = sessions_dir / session_id
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Session {session_id!r} not found")
    shutil.rmtree(session_dir)
    return {"deleted": True, "id": session_id}


def handle_sessions_rename(_session: Any, params: dict[str, Any]) -> dict:
    sessions_dir = _get_sessions_dir()
    session_id = params["id"]
    new_name = params["name"]
    session_dir = sessions_dir / session_id
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Session {session_id!r} not found")

    meta = _load_meta(session_dir)
    meta["name"] = new_name
    meta["modified_at"] = datetime.now(timezone.utc).isoformat()
    _save_meta(session_dir, meta)
    return {"id": session_id, "name": new_name}


def handle_sessions_dir_get(_session: Any, _params: dict[str, Any]) -> dict:
    return {"sessions_dir": str(_get_sessions_dir())}


def handle_sessions_dir_set(_session: Any, params: dict[str, Any]) -> dict:
    new_dir = params["sessions_dir"]
    path = Path(new_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    Config.save_state("sessions_dir", str(path))
    return {"sessions_dir": str(path)}
