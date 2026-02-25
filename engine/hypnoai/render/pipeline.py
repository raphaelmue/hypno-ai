"""Sequential render pipeline — Phase 1 implementation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from ..parser.ast_nodes import (
    Block,
    CommentBlock,
    PauseBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
    UnknownDirectiveBlock,
    VoiceChangeBlock,
)
from ..tts.base import TTSEngine


def _generate_silence(duration_s: float, sample_rate: int, output_path: Path) -> None:
    """Write a mono silent WAV file of the given duration."""
    n_samples = int(round(duration_s * sample_rate))
    data = np.zeros(n_samples, dtype=np.float32)
    sf.write(str(output_path), data, sample_rate)


@dataclass
class RenderJob:
    """Result of a single render run."""

    job_id: str
    chunk_paths: list[Path] = field(default_factory=list)
    # Each entry: (chunk_index_before_section, section_title)
    sections: list[tuple[int, str]] = field(default_factory=list)


class RenderPipeline:
    """Sequential render pipeline (Phase 1).

    Iterates over AST blocks in order and generates WAV chunk files.
    Paragraphs are rendered one at a time; concurrency is a Phase 2 concern.

    Voice and speed are carried as mutable state across the block list —
    a ``@{voice}`` or ``@{speed}`` directive changes the state for every
    subsequent ``TextBlock``.
    """

    def __init__(self, engine: TTSEngine, sample_rate: int = 22050) -> None:
        self.engine = engine
        self.sample_rate = sample_rate

    def render(
        self,
        blocks: list[Block],
        output_dir: Path,
        initial_voice: str,
        initial_speed: float = 1.0,
        job_id: str = "render",
    ) -> RenderJob:
        """Render all blocks to numbered WAV chunks inside *output_dir*.

        Returns a :class:`RenderJob` whose ``chunk_paths`` list is in
        playback order.  The caller is responsible for assembling them.

        Args:
            blocks: Ordered list of AST blocks from the parser.
            output_dir: Directory for chunk WAV files (created if missing).
            initial_voice: Voice ID to use before any @{voice} directive.
            initial_speed: Speed multiplier before any @{speed} directive.
            job_id: Human-readable identifier for the job.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        job = RenderJob(job_id=job_id)
        current_voice = initial_voice
        current_speed = initial_speed
        chunk_idx = 0

        for block in blocks:
            if isinstance(block, TextBlock):
                chunk_path = output_dir / f"{chunk_idx:03d}.wav"
                self.engine.generate(
                    text=block.text,
                    voice=current_voice,
                    speed=current_speed,
                    output_path=chunk_path,
                )
                job.chunk_paths.append(chunk_path)
                chunk_idx += 1

            elif isinstance(block, PauseBlock):
                chunk_path = output_dir / f"{chunk_idx:03d}.wav"
                _generate_silence(block.duration_s, self.sample_rate, chunk_path)
                job.chunk_paths.append(chunk_path)
                chunk_idx += 1

            elif isinstance(block, VoiceChangeBlock):
                current_voice = block.voice_id

            elif isinstance(block, SpeedChangeBlock):
                current_speed = block.speed

            elif isinstance(block, SectionBlock):
                # Record where this section starts in the chunk sequence
                job.sections.append((chunk_idx, block.title))

            elif isinstance(block, (CommentBlock, UnknownDirectiveBlock)):
                pass  # silently skip

        return job
