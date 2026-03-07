"""Loudness normalisation — ITU-R BS.1770 via pyloudnorm."""
from __future__ import annotations

import numpy as np

TARGET_LUFS: float = -16.0

# pyloudnorm needs at least ~0.4 s of audio to integrate a meaningful LUFS.
_MIN_DURATION_S: float = 0.4


def normalize_loudness(
    data: np.ndarray,
    sample_rate: int,
    target_lufs: float = TARGET_LUFS,
) -> np.ndarray:
    """Normalise *data* to *target_lufs* LUFS (ITU-R BS.1770-4).

    If the signal is too short, silent, or integrated loudness cannot be
    measured, the original array is returned unchanged.

    Requires ``pyloudnorm`` (``pip install pyloudnorm``).

    Args:
        data: Float32 audio array, shape ``(N,)`` or ``(N, channels)``.
        sample_rate: Sample rate in Hz.
        target_lufs: Target integrated loudness in LUFS (default -16 LUFS).

    Returns:
        Loudness-normalised float32 array.
    """
    try:
        import pyloudnorm as pyln  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Loudness normalisation requires pyloudnorm: pip install pyloudnorm"
        ) from exc

    n_samples = data.shape[0]
    if n_samples < int(_MIN_DURATION_S * sample_rate):
        return data  # too short to measure

    meter = pyln.Meter(sample_rate)
    try:
        loudness = meter.integrated_loudness(data.astype(np.float64))
    except Exception:
        return data

    if not np.isfinite(loudness):
        return data  # silence or unmeasurable

    normalised = pyln.normalize.loudness(
        data.astype(np.float64), loudness, target_lufs
    )
    return normalised.astype(np.float32)
