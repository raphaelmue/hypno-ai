"""Tests for the audio effects module."""
from __future__ import annotations

import sys

import numpy as np
import pytest
from hypnoai.audio.effects import crossfade_concat, pitch_shift, warmth_eq


# ---------------------------------------------------------------------------
# crossfade_concat
# ---------------------------------------------------------------------------


class TestCrossfadeConcat:
    def test_empty_input_returns_empty_float32(self):
        result = crossfade_concat([], 22050)
        assert result.shape == (0,)
        assert result.dtype == np.float32

    def test_single_chunk_returned_as_float32(self):
        data = np.ones(100, dtype=np.float32) * 0.5
        result = crossfade_concat([data], 22050)
        np.testing.assert_array_almost_equal(result, data)
        assert result.dtype == np.float32

    def test_two_chunks_no_crossfade_simple_concat(self):
        a = np.ones(100, dtype=np.float32)
        b = np.ones(100, dtype=np.float32) * 0.5
        result = crossfade_concat([a, b], 22050, fade_ms=0)
        assert len(result) == 200

    def test_crossfade_output_length(self):
        sr = 22050
        fade_ms = 30
        fade_samples = int(fade_ms * sr / 1000)
        a = np.ones(1000, dtype=np.float32)
        b = np.ones(1000, dtype=np.float32)
        result = crossfade_concat([a, b], sr, fade_ms=fade_ms)
        assert len(result) == len(a) + len(b) - fade_samples

    def test_crossfade_blend_values_at_boundary(self):
        sr = 22050
        fade_ms = 10
        fade_samples = int(fade_ms * sr / 1000)
        # a=1.0, b=0.0 — overlap should fade from 1 to 0
        a = np.ones(500, dtype=np.float32)
        b = np.zeros(500, dtype=np.float32)
        result = crossfade_concat([a, b], sr, fade_ms=fade_ms)
        overlap_start = len(a) - fade_samples
        assert result[overlap_start] == pytest.approx(1.0, abs=1e-4)
        assert result[overlap_start + fade_samples - 1] == pytest.approx(0.0, abs=1e-4)

    def test_three_chunks_merged_successfully(self):
        sr = 22050
        chunks = [np.ones(500, dtype=np.float32) * float(i) for i in range(3)]
        result = crossfade_concat(chunks, sr, fade_ms=10)
        assert result.ndim == 1
        assert len(result) > 0

    def test_chunk_shorter_than_fade_falls_back_to_concat(self):
        # fade_ms=100 at 22050 Hz = 2205 samples; chunks are 50 samples
        a = np.ones(50, dtype=np.float32)
        b = np.ones(50, dtype=np.float32) * 0.5
        result = crossfade_concat([a, b], 22050, fade_ms=100)
        assert len(result) == 100

    def test_stereo_chunks_concatenated(self):
        a = np.ones((100, 2), dtype=np.float32)
        b = np.ones((100, 2), dtype=np.float32) * 0.5
        result = crossfade_concat([a, b], 22050, fade_ms=0)
        assert result.shape == (200, 2)

    def test_stereo_crossfade_preserves_channel_count(self):
        sr = 22050
        a = np.ones((1000, 2), dtype=np.float32)
        b = np.ones((1000, 2), dtype=np.float32) * 0.5
        result = crossfade_concat([a, b], sr, fade_ms=30)
        assert result.ndim == 2
        assert result.shape[1] == 2

    def test_output_is_float32(self):
        # Float64 input should produce float32 output
        a = np.ones(100, dtype=np.float64)
        result = crossfade_concat([a], 22050)
        assert result.dtype == np.float32


# ---------------------------------------------------------------------------
# warmth_eq
# ---------------------------------------------------------------------------


class TestWarmthEq:
    def test_zero_boost_returns_unchanged(self):
        data = np.random.default_rng(42).random(22050).astype(np.float32)
        result = warmth_eq(data, 22050, boost_db=0.0)
        np.testing.assert_array_equal(result, data)

    def test_shape_preserved(self):
        data = np.random.default_rng(0).random(22050).astype(np.float32)
        result = warmth_eq(data, 22050, boost_db=2.0)
        assert result.shape == data.shape

    def test_output_clipped_to_unit_range(self):
        data = np.ones(22050, dtype=np.float32) * 10.0
        result = warmth_eq(data, 22050, boost_db=6.0)
        assert np.all(result >= -1.0)
        assert np.all(result <= 1.0)

    def test_output_is_float32(self):
        data = np.random.default_rng(1).random(22050).astype(np.float32)
        result = warmth_eq(data, 22050, boost_db=2.0)
        assert result.dtype == np.float32

    def test_silent_signal_unchanged(self):
        data = np.zeros(22050, dtype=np.float32)
        result = warmth_eq(data, 22050, boost_db=3.0)
        np.testing.assert_array_equal(result, data)

    def test_positive_boost_changes_signal(self):
        rng = np.random.default_rng(99)
        data = rng.random(22050).astype(np.float32) * 0.5
        result = warmth_eq(data, 22050, boost_db=3.0)
        assert not np.allclose(result, data)


# ---------------------------------------------------------------------------
# pitch_shift
# ---------------------------------------------------------------------------


class TestPitchShift:
    def test_zero_semitones_returns_unchanged(self):
        data = np.ones(100, dtype=np.float32)
        result = pitch_shift(data, 22050, semitones=0.0)
        np.testing.assert_array_equal(result, data)

    def test_zero_semitones_identity_does_not_import_librosa(self):
        # With semitones=0, function short-circuits before touching librosa
        original = sys.modules.get("librosa")
        sys.modules["librosa"] = None  # type: ignore[assignment]
        try:
            data = np.ones(100, dtype=np.float32)
            result = pitch_shift(data, 22050, semitones=0.0)
            np.testing.assert_array_equal(result, data)
        finally:
            if original is None:
                sys.modules.pop("librosa", None)
            else:
                sys.modules["librosa"] = original

    def test_missing_librosa_raises_import_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "librosa", None)  # type: ignore[arg-type]
        with pytest.raises(ImportError, match="librosa"):
            pitch_shift(np.ones(100, dtype=np.float32), 22050, semitones=2.0)
