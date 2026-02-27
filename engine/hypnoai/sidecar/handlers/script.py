"""script.lint handler — parse and validate a HypnoScript file."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from ...parser import find_variables, inject_variables, parse
from ...parser.ast_nodes import (
    PauseBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
)
from ..session import SidecarSession

# Words-per-minute baselines
_BASELINE_WPM = 130
_IDEAL_WPM_MIN = 60
_IDEAL_WPM_MAX = 80


def handle_script_lint(session: SidecarSession, params: dict[str, Any]) -> dict:
    """Parse and validate a .hypno script.

    Expected params:
        path (str): Absolute path to the script file.

    Returns:
        valid (bool)
        warnings (list[str])
        paragraph_count (int)
        estimated_duration_s (float)
        variables (list[str])
        pacing (list[{paragraph, wpm}])
    """
    path_str = params.get("path")
    if not path_str:
        raise ValueError("Missing required param 'path'")

    script_path = Path(path_str)
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    source = script_path.read_text(encoding="utf-8")

    # Collect parser warnings
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        blocks = parse(source)

    warning_messages = [str(w.message) for w in caught_warnings]
    variables = sorted(set(find_variables(source)))

    # Gather statistics
    text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
    pause_blocks = [b for b in blocks if isinstance(b, PauseBlock)]
    section_blocks = [b for b in blocks if isinstance(b, SectionBlock)]

    # Estimate duration and per-paragraph WPM
    current_speed = 1.0
    estimated_s = 0.0
    pacing: list[dict] = []
    paragraph_idx = 0

    for block in blocks:
        if isinstance(block, SpeedChangeBlock):
            current_speed = block.speed
        elif isinstance(block, TextBlock):
            words = len(block.text.split())
            effective_wpm = _BASELINE_WPM * current_speed
            duration_s = (words / effective_wpm) * 60 if effective_wpm > 0 else 0.0
            estimated_s += duration_s
            wpm = round(effective_wpm)
            pacing.append({"paragraph": paragraph_idx, "wpm": wpm})
            paragraph_idx += 1
        elif isinstance(block, PauseBlock):
            estimated_s += block.duration_s

    return {
        "valid": len(warning_messages) == 0,
        "warnings": warning_messages,
        "paragraph_count": len(text_blocks),
        "pause_count": len(pause_blocks),
        "section_count": len(section_blocks),
        "estimated_duration_s": round(estimated_s, 1),
        "variables": variables,
        "pacing": pacing,
    }
