"""Parser that converts HypnoScript tokens into an AST of Blocks."""
from __future__ import annotations

import warnings

from .ast_nodes import (
    Block,
    CommentBlock,
    PauseBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
    UnknownDirectiveBlock,
    VoiceChangeBlock,
)
from .lexer import Token, TokenType, lex

# Directives known but not yet implemented (Phase 2+): suppress "unknown" noise.
_FUTURE_DIRECTIVES = frozenset({"music", "binaural", "breath", "volume"})


def _parse_duration(value: str) -> float:
    """Parse a duration string like '3s' or '500ms' into seconds."""
    v = value.strip()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    raise ValueError(f"Invalid duration {value!r}. Expected format: '3s' or '500ms'.")


def _is_simple_voice_id(value: str) -> bool:
    """Return True if value looks like a bare voice ID (no key=value params)."""
    return "=" not in value


def _parse_directive(token: Token) -> Block:
    """Convert a single DIRECTIVE token into the appropriate AST Block."""
    key = token.key.lower()
    value = token.value

    if key == "pause":
        try:
            duration = _parse_duration(value)
        except ValueError as exc:
            warnings.warn(f"Line {token.line}: {exc}", SyntaxWarning, stacklevel=4)
            return UnknownDirectiveBlock(line=token.line, key=key, value=value)
        return PauseBlock(line=token.line, duration_s=duration)

    if key == "voice":
        if _is_simple_voice_id(value):
            return VoiceChangeBlock(line=token.line, voice_id=value)
        # Complex voice params (pitch, emotion) — Phase 6 feature
        warnings.warn(
            f"Line {token.line}: Complex @{{voice}} parameters are not yet supported "
            f"(got: {value!r}). Directive ignored.",
            UserWarning,
            stacklevel=4,
        )
        return UnknownDirectiveBlock(line=token.line, key=key, value=value)

    if key == "speed":
        try:
            speed = float(value)
        except ValueError:
            warnings.warn(
                f"Line {token.line}: Invalid speed value {value!r}. Expected a float.",
                SyntaxWarning,
                stacklevel=4,
            )
            return UnknownDirectiveBlock(line=token.line, key=key, value=value)
        if not (0.1 <= speed <= 5.0):
            warnings.warn(
                f"Line {token.line}: Speed {speed} is outside the recommended range [0.1, 5.0].",
                UserWarning,
                stacklevel=4,
            )
        return SpeedChangeBlock(line=token.line, speed=speed)

    if key == "section":
        return SectionBlock(line=token.line, title=value)

    if key == "comment":
        return CommentBlock(line=token.line, text=value)

    if key not in _FUTURE_DIRECTIVES:
        warnings.warn(
            f"Line {token.line}: Unknown directive @{{{key}}}. Ignored.",
            UserWarning,
            stacklevel=4,
        )
    return UnknownDirectiveBlock(line=token.line, key=key, value=value)


def parse_tokens(tokens: list[Token]) -> list[Block]:
    """Convert a flat token list into an ordered list of AST Blocks."""
    blocks: list[Block] = []
    text_lines: list[str] = []
    text_start_line: int = 0

    def flush_text() -> None:
        if text_lines:
            blocks.append(TextBlock(line=text_start_line, text="\n".join(text_lines)))
            text_lines.clear()

    for token in tokens:
        if token.type == TokenType.TEXT:
            if not text_lines:
                text_start_line = token.line
            text_lines.append(token.text)
        elif token.type == TokenType.BLANK:
            flush_text()
        elif token.type == TokenType.DIRECTIVE:
            flush_text()
            blocks.append(_parse_directive(token))

    flush_text()
    return blocks


def parse(source: str) -> list[Block]:
    """Parse a HypnoScript source string into an ordered list of AST Blocks."""
    return parse_tokens(lex(source))
