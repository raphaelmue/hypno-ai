"""Tests for the script.lint sidecar handler."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from hypnoai.sidecar.handlers.script import handle_script_lint
from hypnoai.sidecar.session import SidecarSession


@pytest.fixture
def session(tmp_path):
    return SidecarSession(tmp_root=tmp_path / "session")


@pytest.fixture
def simple_script(tmp_path) -> Path:
    script = tmp_path / "test.hypno"
    # Note: @{language: en} is a future/unknown directive in the parser,
    # so we omit it here to keep warnings=[] for the "valid" assertion.
    script.write_text(
        textwrap.dedent("""\
        @{voice: en_US-amy-medium}
        @{speed: 0.85}

        Close your eyes and take a deep breath, {{name}}.

        @{pause: 4s}

        Now slowly release the air from your lungs.

        @{pause: 6s}

        When you are ready, open your eyes.
        """),
        encoding="utf-8",
    )
    return script


def test_lint_valid_script(session, simple_script):
    # Provide the variable so the script is considered fully valid
    result = handle_script_lint(
        session, {"path": str(simple_script), "variables": {"name": "World"}}
    )

    assert result["valid"] is True
    assert result["warnings"] == []
    assert result["paragraph_count"] == 3
    assert result["pause_count"] == 2
    assert result["estimated_duration_s"] > 0
    assert "name" in result["variables"]
    assert len(result["pacing"]) == 3


def test_lint_undefined_variable_warning(session, simple_script):
    # No variables provided → lint should warn about {{name}}
    result = handle_script_lint(session, {"path": str(simple_script)})

    assert result["valid"] is False
    assert any("name" in w for w in result["warnings"])


def test_lint_pacing_entries(session, simple_script):
    result = handle_script_lint(
        session, {"path": str(simple_script), "variables": {"name": "World"}}
    )

    for i, entry in enumerate(result["pacing"]):
        assert entry["paragraph"] == i
        assert entry["wpm"] > 0


def test_lint_missing_path(session):
    with pytest.raises(ValueError, match="Missing required param"):
        handle_script_lint(session, {})


def test_lint_file_not_found(session, tmp_path):
    with pytest.raises(FileNotFoundError):
        handle_script_lint(session, {"path": str(tmp_path / "nonexistent.hypno")})


def test_lint_includes_variables(session, tmp_path):
    script = tmp_path / "vars.hypno"
    script.write_text(
        "Hello, {{name}}. Welcome to {{place}}.\n\n@{pause: 2s}\n\nGoodbye, {{name}}.",
        encoding="utf-8",
    )
    result = handle_script_lint(session, {"path": str(script)})
    assert set(result["variables"]) == {"name", "place"}


def test_lint_unknown_directive_produces_warning(session, tmp_path):
    script = tmp_path / "warn.hypno"
    script.write_text(
        "@{unknowndirective: value}\n\nSome spoken text here.\n",
        encoding="utf-8",
    )
    result = handle_script_lint(session, {"path": str(script)})
    assert result["valid"] is False
    assert len(result["warnings"]) > 0


def test_lint_section_count(session, tmp_path):
    script = tmp_path / "sections.hypno"
    script.write_text(
        textwrap.dedent("""\
        @{section: Introduction}

        Welcome to the session.

        @{section: Body}

        This is the main content.

        @{section: Ending}

        Thank you.
        """),
        encoding="utf-8",
    )
    result = handle_script_lint(session, {"path": str(script)})
    assert result["section_count"] == 3


def test_lint_empty_script(session, tmp_path):
    script = tmp_path / "empty.hypno"
    script.write_text("", encoding="utf-8")
    result = handle_script_lint(session, {"path": str(script)})
    assert result["paragraph_count"] == 0
    assert result["estimated_duration_s"] == 0.0
