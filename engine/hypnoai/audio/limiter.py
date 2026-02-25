"""Brick-wall limiter — prevents digital clipping in the final mix (§9)."""
from __future__ import annotations

import numpy as np


def brick_wall_limiter(
    data: np.ndarray,
    ceiling_db: float = -1.0,
) -> np.ndarray:
    """Apply a hard brick-wall limiter at *ceiling_db* dBFS.

    This is the last stage in the audio chain, placed after loudness
    normalisation.  It catches any peaks that normalization or compression
    missed — essential when speech, music, and binaural tones are summed.

    A value of -1.0 dBFS leaves a single dB of headroom to avoid inter-sample
    peaks during encoding.

    Args:
        data: Float32 audio array.
        ceiling_db: Hard ceiling in dBFS (default -1.0 dBFS).

    Returns:
        Hard-clipped float32 array.
    """
    ceiling = 10.0 ** (ceiling_db / 20.0)
    return np.clip(data, -ceiling, ceiling).astype(np.float32)
