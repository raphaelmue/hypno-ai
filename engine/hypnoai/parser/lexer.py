"""Lexer for HypnoScript markup files."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    DIRECTIVE = "DIRECTIVE"
    TEXT = "TEXT"
    BLANK = "BLANK"


@dataclass
class Token:
    type: TokenType
    line: int
    text: str = ""   # for TEXT tokens
    key: str = ""    # for DIRECTIVE tokens
    value: str = ""  # for DIRECTIVE tokens


# Matches @{key} or @{key: value} with optional surrounding whitespace
_DIRECTIVE_RE = re.compile(r"^@\{([^}:]+?)(?::\s*(.*?))?\}\s*$")


def lex(source: str) -> list[Token]:
    """Tokenize a HypnoScript source string into a flat list of tokens."""
    tokens: list[Token] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            tokens.append(Token(type=TokenType.BLANK, line=line_no))
            continue
        m = _DIRECTIVE_RE.match(stripped)
        if m:
            key = m.group(1).strip()
            value = (m.group(2) or "").strip()
            tokens.append(Token(type=TokenType.DIRECTIVE, line=line_no, key=key, value=value))
        else:
            tokens.append(Token(type=TokenType.TEXT, line=line_no, text=stripped))
    return tokens
