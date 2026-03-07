"""Concurrent paragraph worker pool (§6.3)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import soundfile as sf

from .cache import RenderCache
from ..tts.base import TTSEngine

ProgressCallback = Callable[[int, int], None]  # (completed, total)


@dataclass
class WorkItem:
    """A single TTS generation task."""

    index: int
    text: str
    voice: str
    speed: float
    pitch_semitones: float
    output_path: Path
    cache_key: str | None = field(default=None)


def _apply_pitch_shift(path: Path, semitones: float) -> None:
    """Apply a pitch shift in-place to *path* (requires librosa)."""
    from ..audio.effects import pitch_shift  # lazy import

    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    shifted = pitch_shift(data, sr, semitones)
    sf.write(str(path), shifted, sr, subtype="FLOAT")


class WorkerPool:
    """Run TTS work items with bounded concurrency.

    Each item is processed as follows:

    1. Cache lookup — if hit, copy cached WAV to ``item.output_path`` and skip TTS.
    2. TTS generation — call ``engine.generate()``.
    3. Pitch shift — if ``item.pitch_semitones != 0``, apply post-processing.
    4. Cache store — write the result into the cache for future reuse.

    Results are returned as a ``{index: output_path}`` dict.  The caller is
    responsible for assembling them in the correct order.
    """

    def __init__(
        self,
        engine: TTSEngine,
        max_workers: int = 4,
        cache: RenderCache | None = None,
    ) -> None:
        self.engine = engine
        self.max_workers = max(1, max_workers)
        self.cache = cache

    def submit(
        self,
        items: list[WorkItem],
        on_progress: ProgressCallback | None = None,
    ) -> dict[int, Path]:
        """Execute all items and return a mapping of index → output path.

        Args:
            items: Work items to process concurrently.
            on_progress: Optional ``(completed, total)`` callback fired in the
                calling thread after each item finishes.
        """
        if not items:
            return {}

        results: dict[int, Path] = {}
        total = len(items)
        done = 0

        def execute(item: WorkItem) -> tuple[int, Path]:
            item.output_path.parent.mkdir(parents=True, exist_ok=True)

            # 1. Cache hit
            if self.cache and item.cache_key:
                if self.cache.copy_to(item.cache_key, item.output_path):
                    return item.index, item.output_path

            # 2. TTS generation
            self.engine.generate(
                text=item.text,
                voice=item.voice,
                speed=item.speed,
                output_path=item.output_path,
            )

            # 3. Pitch shift
            if item.pitch_semitones != 0.0:
                _apply_pitch_shift(item.output_path, item.pitch_semitones)

            # 4. Cache store
            if self.cache and item.cache_key:
                self.cache.put(item.cache_key, item.output_path)

            return item.index, item.output_path

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(execute, item): item for item in items}
            for future in as_completed(futures):
                idx, path = future.result()
                results[idx] = path
                done += 1
                if on_progress:
                    on_progress(done, total)

        return results
