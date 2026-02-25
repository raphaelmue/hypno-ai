"""Audio post-processing pipeline — chains crossfade, EQ, normalization, limiter (§9)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from .assembler import assemble
from .effects import crossfade_concat, warmth_eq
from .limiter import brick_wall_limiter
from .normalize import normalize_loudness


@dataclass
class PostProcessConfig:
    """Configuration for the audio post-processing chain."""

    # Crossfade between adjacent chunks (ms). 0 = hard cuts.
    crossfade_ms: int = 30

    # Warmth EQ: gentle low-mid boost in dB. 0 = disabled.
    warmth_db: float = 0.0

    # Loudness normalisation
    normalize: bool = True
    target_lufs: float = -16.0

    # Brick-wall limiter
    limit: bool = True
    limit_db: float = -1.0


class PostProcessor:
    """Assembles and processes ordered WAV chunks into the final output file.

    Processing order (§9):
      1. Crossfade concatenation
      2. Warmth EQ (optional)
      3. Loudness normalisation (optional)
      4. Brick-wall limiter (optional)
      5. Write float32 WAV

    Usage::

        cfg = PostProcessConfig(crossfade_ms=30, normalize=True, limit=True)
        pp = PostProcessor(cfg, sample_rate=22050)
        pp.process(chunk_paths, output_path)
    """

    def __init__(self, config: PostProcessConfig, sample_rate: int = 22050) -> None:
        self.config = config
        self.sample_rate = sample_rate

    def process(self, chunk_paths: list[Path], output_path: Path) -> None:
        """Assemble *chunk_paths* and apply the full processing chain."""
        if not chunk_paths:
            raise ValueError("No chunks to process.")

        cfg = self.config

        # 1. Load chunks and concatenate with optional crossfade
        chunks: list[np.ndarray] = []
        sr: int | None = None
        for path in chunk_paths:
            data, file_sr = sf.read(str(path), dtype="float32", always_2d=False)
            if sr is None:
                sr = file_sr
            elif file_sr != sr:
                raise ValueError(
                    f"Sample rate mismatch in {path.name}: "
                    f"expected {sr} Hz, got {file_sr} Hz."
                )
            chunks.append(data)

        if sr is None:
            sr = self.sample_rate

        if cfg.crossfade_ms > 0:
            combined = crossfade_concat(chunks, sr, fade_ms=cfg.crossfade_ms)
        else:
            combined = np.concatenate(chunks, axis=0)

        # 2. Warmth EQ
        if cfg.warmth_db > 0.0:
            combined = warmth_eq(combined, sr, cfg.warmth_db)

        # 3. Loudness normalisation
        if cfg.normalize:
            combined = normalize_loudness(combined, sr, cfg.target_lufs)

        # 4. Brick-wall limiter
        if cfg.limit:
            combined = brick_wall_limiter(combined, cfg.limit_db)

        # 5. Write
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), combined, sr, subtype="FLOAT")
