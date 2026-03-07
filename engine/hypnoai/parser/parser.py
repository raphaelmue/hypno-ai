"""Parser that converts HypnoScript tokens into an AST of Blocks."""
from __future__ import annotations

import re
import warnings

from .ast_nodes import (
    Block,
    CommentBlock,
    PauseBlock,
    PitchChangeBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
    UnknownDirectiveBlock,
    VoiceChangeBlock,
)
from .lexer import Token, TokenType, lex

# Directives known but not yet implemented (Phase 3+): suppress "unknown" noise.
_FUTURE_DIRECTIVES = frozenset({"music", "binaural", "breath", "volume"})

# Regex for pitch param: pitch=-2st or pitch=+1.5st
_PITCH_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)st$")


def _parse_duration(value: str) -> float:
    """Parse a duration string like '3s' or '500ms' into seconds."""
    v = value.strip()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    raise ValueError(f"Invalid duration {value!r}. Expected format: '3s' or '500ms'.")


def _parse_voice_directive(token: Token) -> list[Block]:
    """Parse @{voice: ...} which can combine a voice ID, pitch, and emotion."""
    value = token.value
    line = token.line

    # Split on commas to get individual params
    parts = [p.strip() for p in value.split(",") if p.strip()]

    voice_id: str | None = None
    pitch_semitones: float | None = None

    for part in parts:
        if "=" not in part:
            # Bare word — treat as voice ID
            if voice_id is None:
                voice_id = part
            else:
                warnings.warn(
                    f"Line {line}: Multiple bare voice IDs in @{{voice}}: {value!r}. "
                    f"Using first: {voice_id!r}.",
                    UserWarning,
                    stacklevel=5,
                )
        else:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k == "pitch":
                m = _PITCH_RE.match(v)
                if m:
                    pitch_semitones = float(m.group(1))
                else:
                    warnings.warn(
                        f"Line {line}: Invalid pitch value {v!r}. "
                        "Expected format like '-2st' or '+1.5st'. Ignored.",
                        SyntaxWarning,
                        stacklevel=5,
                    )
            elif k == "emotion":
                # Phase 6 feature — silently accept, no block emitted yet
                pass
            else:
                warnings.warn(
                    f"Line {line}: Unknown @{{voice}} parameter {k!r}. Ignored.",
                    UserWarning,
                    stacklevel=5,
                )

    blocks: list[Block] = []
    if voice_id is not None:
        blocks.append(VoiceChangeBlock(line=line, voice_id=voice_id))
    if pitch_semitones is not None:
        blocks.append(PitchChangeBlock(line=line, semitones=pitch_semitones))

    if not blocks:
        # Nothing parsed — emit unknown directive
        warnings.warn(
            f"Line {line}: @{{voice}} directive produced no recognisable parameters "
            f"(got: {value!r}). Ignored.",
            UserWarning,
            stacklevel=5,
        )
        return [UnknownDirectiveBlock(line=line, key="voice", value=value)]

    return blocks


def _parse_directive(token: Token) -> list[Block]:
    """Convert a single DIRECTIVE token into a list of AST Blocks."""
    key = token.key.lower()
    value = token.value

    if key == "pause":
        try:
            duration = _parse_duration(value)
        except ValueError as exc:
            warnings.warn(f"Line {token.line}: {exc}", SyntaxWarning, stacklevel=4)
            return [UnknownDirectiveBlock(line=token.line, key=key, value=value)]
        return [PauseBlock(line=token.line, duration_s=duration)]

    if key == "voice":
        return _parse_voice_directive(token)

    if key == "speed":
        try:
            speed = float(value)
        except ValueError:
            warnings.warn(
                f"Line {token.line}: Invalid speed value {value!r}. Expected a float.",
                SyntaxWarning,
                stacklevel=4,
            )
            return [UnknownDirectiveBlock(line=token.line, key=key, value=value)]
        if not (0.1 <= speed <= 5.0):
            warnings.warn(
                f"Line {token.line}: Speed {speed} is outside the recommended range [0.1, 5.0].",
                UserWarning,
                stacklevel=4,
            )
        return [SpeedChangeBlock(line=token.line, speed=speed)]

    if key == "section":
        return [SectionBlock(line=token.line, title=value)]

    if key == "comment":
        return [CommentBlock(line=token.line, text=value)]

    if key not in _FUTURE_DIRECTIVES:
        warnings.warn(
            f"Line {token.line}: Unknown directive @{{{key}}}. Ignored.",
            UserWarning,
            stacklevel=4,
        )
    return [UnknownDirectiveBlock(line=token.line, key=key, value=value)]


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
            blocks.extend(_parse_directive(token))

    flush_text()
    return blocks


def parse(source: str) -> list[Block]:
    """Parse a HypnoScript source string into an ordered list of AST Blocks."""
    return parse_tokens(lex(source))
