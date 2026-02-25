"""Render pipeline — sequential (with prosody chain) and parallel paths (§6.3)."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from ..parser.ast_nodes import (
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
from ..tts.base import TTSEngine
from .cache import RenderCache
from .worker import WorkItem, WorkerPool, _apply_pitch_shift

# How many seconds of previous-paragraph audio to pass as prosody reference (§6.2)
PROSODY_TAIL_SECONDS: float = 3.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_silence(duration_s: float, sample_rate: int, output_path: Path) -> None:
    """Write a mono silent WAV file of the given duration."""
    n_samples = int(round(duration_s * sample_rate))
    data = np.zeros(n_samples, dtype=np.float32)
    sf.write(str(output_path), data, sample_rate, subtype="FLOAT")


def _extract_prosody_tail(source: Path, tail_s: float, tail_dir: Path) -> Path:
    """Extract the last *tail_s* seconds of *source* to a temporary file."""
    data, sr = sf.read(str(source), dtype="float32", always_2d=False)
    n = int(tail_s * sr)
    tail_data = data[-n:] if len(data) > n else data
    tail_path = tail_dir / f"{source.stem}_tail.wav"
    sf.write(str(tail_path), tail_data, sr, subtype="FLOAT")
    return tail_path


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class RenderJob:
    """Result of a single render pass."""

    job_id: str
    chunk_paths: list[Path] = field(default_factory=list)
    # (chunk_index_at_section_start, section_title)
    sections: list[tuple[int, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class RenderPipeline:
    """Render pipeline with two execution strategies.

    * **Parallel** (``max_workers > 1``, engine doesn't support prosody):
      All text paragraphs are submitted to a :class:`~.worker.WorkerPool`
      concurrently.  Silence for pause blocks is generated inline (fast).

    * **Sequential with prosody chain** (any engine, ``max_workers == 1``, or
      engine supports prosody reference):
      Paragraphs are rendered one at a time.  For engines that support
      ``prosody_reference`` (e.g. Coqui XTTS v2), the tail audio of each
      paragraph is passed as the reference for the next, maintaining tonal
      continuity across paragraph boundaries.

    Both paths integrate the paragraph-level :class:`~.cache.RenderCache`.
    Pitch shifting is applied per-chunk after TTS generation.
    """

    def __init__(
        self,
        engine: TTSEngine,
        sample_rate: int = 22050,
        cache: RenderCache | None = None,
        max_workers: int = 1,
    ) -> None:
        self.engine = engine
        self.sample_rate = sample_rate
        self.cache = cache
        # Honour engine recommendation but cap at config value
        self.max_workers = max(1, max_workers)

    def render(
        self,
        blocks: list[Block],
        output_dir: Path,
        initial_voice: str,
        initial_speed: float = 1.0,
        initial_pitch: float = 0.0,
        job_id: str = "render",
    ) -> RenderJob:
        """Render all blocks to WAV chunks inside *output_dir*.

        Args:
            blocks: Ordered AST blocks from the parser.
            output_dir: Directory for chunk WAV files (created if missing).
            initial_voice: Voice ID before any ``@{voice}`` directive.
            initial_speed: Speed multiplier before any ``@{speed}`` directive.
            initial_pitch: Pitch offset in semitones before any ``@{voice: pitch=}``
                           directive.
            job_id: Human-readable identifier for logging.

        Returns:
            :class:`RenderJob` whose ``chunk_paths`` list is in playback order.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        use_parallel = (
            self.max_workers > 1
            and not self.engine.supports_prosody_reference()
        )

        if use_parallel:
            return self._render_parallel(
                blocks, output_dir, initial_voice, initial_speed, initial_pitch, job_id
            )
        return self._render_sequential(
            blocks, output_dir, initial_voice, initial_speed, initial_pitch, job_id
        )

    # ------------------------------------------------------------------
    # Sequential path (with optional prosody chaining)
    # ------------------------------------------------------------------

    def _render_sequential(
        self,
        blocks: list[Block],
        output_dir: Path,
        initial_voice: str,
        initial_speed: float,
        initial_pitch: float,
        job_id: str,
    ) -> RenderJob:
        job = RenderJob(job_id=job_id)
        current_voice = initial_voice
        current_speed = initial_speed
        current_pitch = initial_pitch
        chunk_idx = 0
        prosody_ref: Path | None = None
        prosody_dir = output_dir / "_prosody"
        supports_prosody = self.engine.supports_prosody_reference()

        for block in blocks:
            if isinstance(block, TextBlock):
                chunk_path = output_dir / f"{chunk_idx:03d}.wav"
                cache_key = (
                    self.cache.cache_key(
                        block.text, current_voice, current_speed, current_pitch
                    )
                    if self.cache
                    else None
                )

                cache_hit = False
                if self.cache and cache_key:
                    cache_hit = self.cache.copy_to(cache_key, chunk_path)

                if not cache_hit:
                    self.engine.generate(
                        text=block.text,
                        voice=current_voice,
                        speed=current_speed,
                        output_path=chunk_path,
                        prosody_reference=prosody_ref if supports_prosody else None,
                    )
                    if current_pitch != 0.0:
                        _apply_pitch_shift(chunk_path, current_pitch)
                    if self.cache and cache_key:
                        self.cache.put(cache_key, chunk_path)

                # Update prosody tail for next paragraph
                if supports_prosody and chunk_path.exists():
                    prosody_dir.mkdir(exist_ok=True)
                    prosody_ref = _extract_prosody_tail(
                        chunk_path, PROSODY_TAIL_SECONDS, prosody_dir
                    )

                job.chunk_paths.append(chunk_path)
                chunk_idx += 1

            elif isinstance(block, PauseBlock):
                chunk_path = output_dir / f"{chunk_idx:03d}.wav"
                _generate_silence(block.duration_s, self.sample_rate, chunk_path)
                job.chunk_paths.append(chunk_path)
                chunk_idx += 1
                # Pause doesn't break prosody — keep prosody_ref as-is

            elif isinstance(block, VoiceChangeBlock):
                current_voice = block.voice_id
                prosody_ref = None  # voice switch resets prosody chain

            elif isinstance(block, SpeedChangeBlock):
                current_speed = block.speed

            elif isinstance(block, PitchChangeBlock):
                current_pitch = block.semitones

            elif isinstance(block, SectionBlock):
                job.sections.append((chunk_idx, block.title))

            elif isinstance(block, (CommentBlock, UnknownDirectiveBlock)):
                pass  # silently skip

        return job

    # ------------------------------------------------------------------
    # Parallel path (for non-prosody engines, e.g. Piper)
    # ------------------------------------------------------------------

    def _render_parallel(
        self,
        blocks: list[Block],
        output_dir: Path,
        initial_voice: str,
        initial_speed: float,
        initial_pitch: float,
        job_id: str,
    ) -> RenderJob:
        job = RenderJob(job_id=job_id)
        current_voice = initial_voice
        current_speed = initial_speed
        current_pitch = initial_pitch
        chunk_idx = 0

        # --- Phase 1: scan blocks, build execution plan ---
        # Each entry: ("text", chunk_idx, WorkItem) | ("pause", chunk_idx, duration_s)
        #           | ("section", chunk_idx, title)
        plan: list[tuple[str, int, object]] = []
        text_items: list[WorkItem] = []

        for block in blocks:
            if isinstance(block, TextBlock):
                cache_key = (
                    self.cache.cache_key(
                        block.text, current_voice, current_speed, current_pitch
                    )
                    if self.cache
                    else None
                )
                item = WorkItem(
                    index=chunk_idx,
                    text=block.text,
                    voice=current_voice,
                    speed=current_speed,
                    pitch_semitones=current_pitch,
                    output_path=output_dir / f"{chunk_idx:03d}.wav",
                    cache_key=cache_key,
                )
                text_items.append(item)
                plan.append(("text", chunk_idx, item))
                chunk_idx += 1

            elif isinstance(block, PauseBlock):
                plan.append(("pause", chunk_idx, block.duration_s))
                chunk_idx += 1

            elif isinstance(block, SectionBlock):
                plan.append(("section", chunk_idx, block.title))

            elif isinstance(block, VoiceChangeBlock):
                current_voice = block.voice_id

            elif isinstance(block, SpeedChangeBlock):
                current_speed = block.speed

            elif isinstance(block, PitchChangeBlock):
                current_pitch = block.semitones

            elif isinstance(block, (CommentBlock, UnknownDirectiveBlock)):
                pass

        # --- Phase 2: submit text items to worker pool ---
        pool = WorkerPool(self.engine, self.max_workers, self.cache)
        pool.submit(text_items)

        # --- Phase 3: generate silences (fast, inline) ---
        for kind, idx, val in plan:
            if kind == "pause":
                pause_path = output_dir / f"{idx:03d}.wav"
                _generate_silence(float(val), self.sample_rate, pause_path)

        # --- Phase 4: assemble results in plan order ---
        for kind, idx, val in plan:
            if kind == "text":
                job.chunk_paths.append(val.output_path)  # type: ignore[union-attr]
            elif kind == "pause":
                job.chunk_paths.append(output_dir / f"{idx:03d}.wav")
            elif kind == "section":
                job.sections.append((len(job.chunk_paths), str(val)))

        return job
