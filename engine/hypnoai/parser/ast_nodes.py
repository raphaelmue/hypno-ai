"""AST node definitions for HypnoScript."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    TEXT = "text"
    PAUSE = "pause"
    VOICE_CHANGE = "voice_change"
    SPEED_CHANGE = "speed_change"
    SECTION = "section"
    COMMENT = "comment"
    UNKNOWN_DIRECTIVE = "unknown_directive"


@dataclass
class Block:
    """Base class for all AST blocks."""

    line: int


@dataclass
class TextBlock(Block):
    """A paragraph of text to be spoken by the TTS engine."""

    text: str
    block_type: BlockType = field(default=BlockType.TEXT, init=False, repr=False)


@dataclass
class PauseBlock(Block):
    """Insert silence of the given duration."""

    duration_s: float
    block_type: BlockType = field(default=BlockType.PAUSE, init=False, repr=False)


@dataclass
class VoiceChangeBlock(Block):
    """Switch the TTS voice for subsequent text."""

    voice_id: str
    block_type: BlockType = field(default=BlockType.VOICE_CHANGE, init=False, repr=False)


@dataclass
class SpeedChangeBlock(Block):
    """Change the speech rate (1.0 = normal, 0.85 is typical for hypnosis)."""

    speed: float
    block_type: BlockType = field(default=BlockType.SPEED_CHANGE, init=False, repr=False)


@dataclass
class SectionBlock(Block):
    """Named chapter marker for navigation and audio metadata."""

    title: str
    block_type: BlockType = field(default=BlockType.SECTION, init=False, repr=False)


@dataclass
class CommentBlock(Block):
    """Author note; ignored during rendering."""

    text: str
    block_type: BlockType = field(default=BlockType.COMMENT, init=False, repr=False)


@dataclass
class UnknownDirectiveBlock(Block):
    """A directive not recognized or not yet implemented."""

    key: str
    value: str
    block_type: BlockType = field(default=BlockType.UNKNOWN_DIRECTIVE, init=False, repr=False)
