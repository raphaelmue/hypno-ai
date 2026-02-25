"""Tests for the HypnoScript parser."""
from __future__ import annotations

import warnings

import pytest

from hypnoai.parser.ast_nodes import (
    CommentBlock,
    PauseBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
    UnknownDirectiveBlock,
    VoiceChangeBlock,
)
from hypnoai.parser.parser import parse


# ---------------------------------------------------------------------------
# Text blocks
# ---------------------------------------------------------------------------


def test_empty_source():
    assert parse("") == []


def test_single_text_paragraph():
    blocks = parse("Hello world.")
    assert len(blocks) == 1
    assert isinstance(blocks[0], TextBlock)
    assert blocks[0].text == "Hello world."


def test_two_paragraphs_separated_by_blank():
    blocks = parse("First paragraph.\n\nSecond paragraph.")
    texts = [b for b in blocks if isinstance(b, TextBlock)]
    assert len(texts) == 2
    assert texts[0].text == "First paragraph."
    assert texts[1].text == "Second paragraph."


def test_multiline_paragraph_joined_by_newline():
    blocks = parse("Line one.\nLine two.\nLine three.")
    assert len(blocks) == 1
    assert isinstance(blocks[0], TextBlock)
    assert blocks[0].text == "Line one.\nLine two.\nLine three."


def test_multiple_blank_lines_treated_as_one_separator():
    blocks = parse("A\n\n\n\nB")
    texts = [b for b in blocks if isinstance(b, TextBlock)]
    assert len(texts) == 2


# ---------------------------------------------------------------------------
# Pause directive
# ---------------------------------------------------------------------------


def test_pause_seconds():
    blocks = parse("@{pause: 3s}")
    assert len(blocks) == 1
    b = blocks[0]
    assert isinstance(b, PauseBlock)
    assert b.duration_s == pytest.approx(3.0)


def test_pause_milliseconds():
    blocks = parse("@{pause: 500ms}")
    b = blocks[0]
    assert isinstance(b, PauseBlock)
    assert b.duration_s == pytest.approx(0.5)


def test_pause_decimal_seconds():
    blocks = parse("@{pause: 1.5s}")
    b = blocks[0]
    assert isinstance(b, PauseBlock)
    assert b.duration_s == pytest.approx(1.5)


def test_pause_zero_ms():
    blocks = parse("@{pause: 0ms}")
    assert blocks[0].duration_s == pytest.approx(0.0)


def test_pause_invalid_format_warns_and_returns_unknown():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        blocks = parse("@{pause: 3minutes}")
    assert any(issubclass(w.category, SyntaxWarning) for w in caught)
    assert isinstance(blocks[0], UnknownDirectiveBlock)


# ---------------------------------------------------------------------------
# Voice directive
# ---------------------------------------------------------------------------


def test_voice_change_simple():
    blocks = parse("@{voice: en_US-amy-medium}")
    b = blocks[0]
    assert isinstance(b, VoiceChangeBlock)
    assert b.voice_id == "en_US-amy-medium"


def test_voice_change_preserves_id():
    blocks = parse("@{voice: de_DE-thorsten-medium}")
    assert blocks[0].voice_id == "de_DE-thorsten-medium"


def test_complex_voice_warns_and_returns_unknown():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        blocks = parse("@{voice: pitch=-2st, emotion=soothing}")
    assert any("Complex @{voice}" in str(w.message) for w in caught)
    assert isinstance(blocks[0], UnknownDirectiveBlock)


# ---------------------------------------------------------------------------
# Speed directive
# ---------------------------------------------------------------------------


def test_speed_change():
    blocks = parse("@{speed: 0.85}")
    b = blocks[0]
    assert isinstance(b, SpeedChangeBlock)
    assert b.speed == pytest.approx(0.85)


def test_speed_integer():
    blocks = parse("@{speed: 1}")
    assert blocks[0].speed == pytest.approx(1.0)


def test_speed_invalid_warns_and_returns_unknown():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        blocks = parse("@{speed: notanumber}")
    assert any(issubclass(w.category, SyntaxWarning) for w in caught)
    assert isinstance(blocks[0], UnknownDirectiveBlock)


def test_speed_out_of_range_warns_but_returns_block():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        blocks = parse("@{speed: 99.0}")
    assert any("recommended range" in str(w.message) for w in caught)
    assert isinstance(blocks[0], SpeedChangeBlock)
    assert blocks[0].speed == pytest.approx(99.0)


# ---------------------------------------------------------------------------
# Section / Comment directives
# ---------------------------------------------------------------------------


def test_section():
    blocks = parse("@{section: Introduction}")
    b = blocks[0]
    assert isinstance(b, SectionBlock)
    assert b.title == "Introduction"


def test_section_multi_word():
    blocks = parse("@{section: Body Scan & Deepening}")
    assert blocks[0].title == "Body Scan & Deepening"


def test_comment():
    blocks = parse("@{comment: Author note here}")
    b = blocks[0]
    assert isinstance(b, CommentBlock)
    assert b.text == "Author note here"


# ---------------------------------------------------------------------------
# Unknown / future directives
# ---------------------------------------------------------------------------


def test_unknown_directive_warns():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        blocks = parse("@{totally_unknown: value}")
    assert any("Unknown directive" in str(w.message) for w in caught)
    assert isinstance(blocks[0], UnknownDirectiveBlock)
    assert blocks[0].key == "totally_unknown"


def test_future_directive_no_unknown_warning():
    """Phase 2+ directives should not trigger the 'Unknown directive' warning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parse("@{music: start, file=test.mp3}")
    unknown = [w for w in caught if "Unknown directive" in str(w.message)]
    assert len(unknown) == 0


# ---------------------------------------------------------------------------
# Ordering and line numbers
# ---------------------------------------------------------------------------


def test_directives_before_first_paragraph():
    script = "@{voice: calm}\n@{speed: 0.9}\n\nHello."
    blocks = parse(script)
    assert isinstance(blocks[0], VoiceChangeBlock)
    assert isinstance(blocks[1], SpeedChangeBlock)
    assert isinstance(blocks[2], TextBlock)


def test_line_numbers_preserved():
    script = "@{voice: calm}\n\nHello."
    blocks = parse(script)
    assert blocks[0].line == 1
    assert blocks[1].line == 3


def test_directive_between_paragraphs_splits_them():
    script = "First.\n@{pause: 1s}\nSecond."
    blocks = parse(script)
    assert isinstance(blocks[0], TextBlock)
    assert isinstance(blocks[1], PauseBlock)
    assert isinstance(blocks[2], TextBlock)


# ---------------------------------------------------------------------------
# Full script integration
# ---------------------------------------------------------------------------


def test_full_script_block_sequence():
    script = (
        "@{comment: Test session}\n"
        "@{voice: en_US-amy-medium}\n"
        "@{speed: 0.85}\n"
        "@{section: Introduction}\n"
        "\n"
        "Welcome, traveler.\n"
        "\n"
        "@{pause: 3s}\n"
        "\n"
        "Take a deep breath.\n"
        "\n"
        "@{voice: en_US-ryan-medium}\n"
        "\n"
        "Excellent."
    )
    blocks = parse(script)
    block_types = [type(b).__name__ for b in blocks]
    assert "CommentBlock" in block_types
    assert "VoiceChangeBlock" in block_types
    assert "SpeedChangeBlock" in block_types
    assert "SectionBlock" in block_types
    assert "TextBlock" in block_types
    assert "PauseBlock" in block_types

    text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
    assert len(text_blocks) == 3
    assert text_blocks[0].text == "Welcome, traveler."
