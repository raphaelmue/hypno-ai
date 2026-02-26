"""Tests for loudness normalisation."""
from __future__ import annotations

import numpy as np
from hypnoai.audio.normalize import normalize_loudness

SR = 22050


def _sine(duration_s: float = 1.0, amplitude: float = 0.1, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    return (np.sin(2 * np.pi * 440 * t) * amplitude).astype(np.float32)


class TestNormalizeLoudness:
    def test_silent_signal_returned_unchanged(self):
        data = np.zeros(SR, dtype=np.float32)
        result = normalize_loudness(data, SR)
        np.testing.assert_array_equal(result, data)

    def test_too_short_signal_returned_unchanged(self):
        # < 0.4 s — below the minimum measurement window
        short = _sine(duration_s=0.2)
        result = normalize_loudness(short, SR)
        np.testing.assert_array_equal(result, short)

    def test_shape_preserved(self):
        data = _sine(duration_s=1.0)
        result = normalize_loudness(data, SR)
        assert result.shape == data.shape

    def test_output_is_float32(self):
        data = _sine(duration_s=1.0)
        result = normalize_loudness(data, SR)
        assert result.dtype == np.float32

    def test_loud_signal_is_attenuated(self):
        # A very loud signal (0.9 amplitude) should be brought down toward -16 LUFS
        data = _sine(duration_s=1.0, amplitude=0.9)
        result = normalize_loudness(data, SR, target_lufs=-16.0)
        assert np.max(np.abs(result)) < np.max(np.abs(data))

    def test_normalization_changes_level(self):
        data = _sine(duration_s=1.0, amplitude=0.5)
        result = normalize_loudness(data, SR, target_lufs=-16.0)
        # The result should differ from input (level was changed)
        assert not np.allclose(result, data)

    def test_custom_target_lufs_applied(self):
        """Normalising to a louder target should produce a louder result."""
        data = _sine(duration_s=1.0, amplitude=0.1)
        louder = normalize_loudness(data, SR, target_lufs=-10.0)
        quieter = normalize_loudness(data, SR, target_lufs=-20.0)
        assert np.max(np.abs(louder)) > np.max(np.abs(quieter))
