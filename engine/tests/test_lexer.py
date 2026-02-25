"""Tests for the HypnoScript lexer."""
from __future__ import annotations

import pytest

from hypnoai.parser.lexer import Token, TokenType, lex


def test_empty_source_returns_empty():
    assert lex("") == []


def test_single_blank_line():
    tokens = lex("\n")
    assert len(tokens) == 1
    assert tokens[0].type == TokenType.BLANK


def test_whitespace_only_line_is_blank():
    tokens = lex("   ")
    assert tokens[0].type == TokenType.BLANK


def test_text_line():
    tokens = lex("Hello world.")
    assert len(tokens) == 1
    t = tokens[0]
    assert t.type == TokenType.TEXT
    assert t.text == "Hello world."
    assert t.line == 1


def test_text_line_stripped():
    tokens = lex("  Hello world.  ")
    assert tokens[0].text == "Hello world."


def test_directive_no_value():
    tokens = lex("@{pause}")
    t = tokens[0]
    assert t.type == TokenType.DIRECTIVE
    assert t.key == "pause"
    assert t.value == ""


def test_directive_with_seconds():
    tokens = lex("@{pause: 3s}")
    t = tokens[0]
    assert t.type == TokenType.DIRECTIVE
    assert t.key == "pause"
    assert t.value == "3s"


def test_directive_with_milliseconds():
    tokens = lex("@{pause: 500ms}")
    t = tokens[0]
    assert t.key == "pause"
    assert t.value == "500ms"


def test_directive_voice():
    tokens = lex("@{voice: en_US-amy-medium}")
    t = tokens[0]
    assert t.type == TokenType.DIRECTIVE
    assert t.key == "voice"
    assert t.value == "en_US-amy-medium"


def test_directive_speed():
    tokens = lex("@{speed: 0.85}")
    t = tokens[0]
    assert t.key == "speed"
    assert t.value == "0.85"


def test_directive_section():
    tokens = lex("@{section: Introduction}")
    t = tokens[0]
    assert t.key == "section"
    assert t.value == "Introduction"


def test_directive_comment():
    tokens = lex("@{comment: Author note here}")
    t = tokens[0]
    assert t.key == "comment"
    assert t.value == "Author note here"


def test_complex_voice_directive():
    tokens = lex("@{voice: pitch=-2st, emotion=soothing}")
    t = tokens[0]
    assert t.type == TokenType.DIRECTIVE
    assert t.key == "voice"
    assert t.value == "pitch=-2st, emotion=soothing"


def test_music_directive():
    tokens = lex('@{music: start, file="ocean.mp3", volume=0.15}')
    t = tokens[0]
    assert t.key == "music"


def test_multiple_lines():
    source = "Line one\nLine two\n\nLine three"
    tokens = lex(source)
    assert len(tokens) == 4
    assert tokens[0].type == TokenType.TEXT
    assert tokens[0].text == "Line one"
    assert tokens[1].type == TokenType.TEXT
    assert tokens[1].text == "Line two"
    assert tokens[2].type == TokenType.BLANK
    assert tokens[3].type == TokenType.TEXT
    assert tokens[3].text == "Line three"


def test_line_numbers():
    source = "@{voice: test}\nHello\n\n@{pause: 1s}"
    tokens = lex(source)
    assert tokens[0].line == 1
    assert tokens[1].line == 2
    assert tokens[2].line == 3
    assert tokens[3].line == 4


def test_directive_with_surrounding_spaces():
    tokens = lex("  @{pause: 2s}  ")
    t = tokens[0]
    assert t.type == TokenType.DIRECTIVE
    assert t.key == "pause"
    assert t.value == "2s"


def test_mixed_content():
    source = (
        "@{comment: A test}\n"
        "@{voice: calm}\n"
        "@{speed: 0.85}\n"
        "\n"
        "Hello world.\n"
        "\n"
        "@{pause: 3s}\n"
        "Goodbye."
    )
    tokens = lex(source)
    types = [t.type for t in tokens]
    assert types == [
        TokenType.DIRECTIVE,
        TokenType.DIRECTIVE,
        TokenType.DIRECTIVE,
        TokenType.BLANK,
        TokenType.TEXT,
        TokenType.BLANK,
        TokenType.DIRECTIVE,
        TokenType.TEXT,
    ]
