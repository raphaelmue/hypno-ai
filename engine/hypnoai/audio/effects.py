"""Audio effects — pitch shift, warmth EQ, crossfade concatenation."""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Pitch shifting
# ---------------------------------------------------------------------------


def pitch_shift(data: np.ndarray, sample_rate: int, semitones: float) -> np.ndarray:
    """Shift pitch by *semitones* semitones without changing duration.

    Requires ``librosa`` (``pip install librosa``).  For stereo audio each
    channel is processed independently.

    Args:
        data: Float32 audio array, shape ``(N,)`` or ``(N, channels)``.
        sample_rate: Sample rate in Hz.
        semitones: Pitch shift in semitones (positive = up, negative = down).

    Returns:
        Pitch-shifted float32 array with the same shape as *data*.

    Raises:
        ImportError: if librosa is not installed.
    """
    if semitones == 0.0:
        return data

    try:
        import librosa  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Pitch shifting requires librosa: pip install librosa"
        ) from exc

    data = data.astype(np.float32)
    if data.ndim == 1:
        return librosa.effects.pitch_shift(data, sr=sample_rate, n_steps=semitones).astype(
            np.float32
        )
    # Stereo / multi-channel: process each channel
    channels = [
        librosa.effects.pitch_shift(data[:, ch], sr=sample_rate, n_steps=semitones)
        for ch in range(data.shape[1])
    ]
    return np.stack(channels, axis=1).astype(np.float32)


# ---------------------------------------------------------------------------
# Warmth EQ
# ---------------------------------------------------------------------------


def warmth_eq(data: np.ndarray, sample_rate: int, boost_db: float = 2.0) -> np.ndarray:
    """Apply a gentle low-mid boost (150–400 Hz) for a warmer, more soothing tone.

    Requires ``scipy``.

    Args:
        data: Float32 audio array.
        sample_rate: Sample rate in Hz.
        boost_db: Amount of boost in dB (default 2.0 dB).

    Returns:
        EQ-processed float32 array clipped to [-1, 1].
    """
    if boost_db == 0.0:
        return data

    from scipy.signal import butter, sosfilt  # type: ignore[import-untyped]

    nyq = sample_rate / 2.0
    low = 150.0 / nyq
    high = min(400.0 / nyq, 0.99)

    sos = butter(2, [low, high], btype="bandpass", output="sos")
    d64 = data.astype(np.float64)
    warm = sosfilt(sos, d64)
    gain = 10.0 ** (boost_db / 20.0) - 1.0
    return np.clip(d64 + warm * gain, -1.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Crossfade concatenation
# ---------------------------------------------------------------------------


def crossfade_concat(
    chunks: list[np.ndarray],
    sample_rate: int,
    fade_ms: int = 30,
) -> np.ndarray:
    """Concatenate audio chunks with a linear crossfade between each pair.

    The crossfade length is ``fade_ms`` milliseconds.  If a chunk is shorter
    than the crossfade window the chunks are concatenated without crossfade.

    Args:
        chunks: List of float32 audio arrays (must share channel count).
        sample_rate: Sample rate in Hz.
        fade_ms: Crossfade duration in milliseconds (default 30 ms).

    Returns:
        Concatenated float32 array.
    """
    if not chunks:
        return np.array([], dtype=np.float32)
    if len(chunks) == 1:
        return chunks[0].astype(np.float32)

    fade_samples = int(fade_ms * sample_rate / 1000)

    result = chunks[0].astype(np.float32)
    for chunk in chunks[1:]:
        chunk = chunk.astype(np.float32)

        if fade_samples == 0 or len(result) < fade_samples or len(chunk) < fade_samples:
            result = np.concatenate([result, chunk], axis=0)
            continue

        ramp_down = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
        ramp_up = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)

        # Broadcast ramps for multi-channel audio
        if result.ndim == 2:
            ramp_down = ramp_down[:, np.newaxis]
            ramp_up = ramp_up[:, np.newaxis]

        overlap = result[-fade_samples:] * ramp_down + chunk[:fade_samples] * ramp_up
        result = np.concatenate([result[:-fade_samples], overlap, chunk[fade_samples:]], axis=0)

    return result
