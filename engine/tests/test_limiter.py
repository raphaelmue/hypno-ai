"""Tests for the brick-wall limiter."""
from __future__ import annotations

import numpy as np
import pytest
from hypnoai.audio.limiter import brick_wall_limiter


class TestBrickWallLimiter:
    def test_quiet_signal_passes_through_unchanged(self):
        # Signal well below ceiling — should not be touched
        data = np.ones(1000, dtype=np.float32) * 0.5
        result = brick_wall_limiter(data, ceiling_db=-1.0)
        np.testing.assert_array_almost_equal(result, data)

    def test_loud_signal_clipped_to_ceiling(self):
        ceiling_db = -1.0
        ceiling = 10.0 ** (ceiling_db / 20.0)
        data = np.ones(1000, dtype=np.float32) * 2.0  # way above ceiling
        result = brick_wall_limiter(data, ceiling_db=ceiling_db)
        assert np.all(result <= ceiling + 1e-6)
        assert np.allclose(result, ceiling)

    def test_negative_peaks_clipped(self):
        ceiling_db = -1.0
        ceiling = 10.0 ** (ceiling_db / 20.0)
        data = np.ones(1000, dtype=np.float32) * -2.0
        result = brick_wall_limiter(data, ceiling_db=ceiling_db)
        assert np.all(result >= -ceiling - 1e-6)

    def test_ceiling_zero_db(self):
        # ceiling_db=0 → ceiling=1.0
        data = np.ones(100, dtype=np.float32) * 1.5
        result = brick_wall_limiter(data, ceiling_db=0.0)
        assert np.allclose(result, 1.0)

    def test_custom_ceiling_respected(self):
        ceiling_db = -6.0
        ceiling = 10.0 ** (ceiling_db / 20.0)
        data = np.ones(100, dtype=np.float32) * 1.0
        result = brick_wall_limiter(data, ceiling_db=ceiling_db)
        assert np.allclose(result, ceiling)

    def test_output_is_float32(self):
        data = np.random.default_rng(7).random(1000).astype(np.float32)
        result = brick_wall_limiter(data)
        assert result.dtype == np.float32

    def test_shape_preserved(self):
        data = np.random.default_rng(8).random((100, 2)).astype(np.float32)
        result = brick_wall_limiter(data)
        assert result.shape == data.shape

    def test_mixed_signal_only_peaks_clipped(self):
        ceiling_db = -6.0
        ceiling = 10.0 ** (ceiling_db / 20.0)
        data = np.array([-2.0, -0.1, 0.0, 0.1, 2.0], dtype=np.float32)
        result = brick_wall_limiter(data, ceiling_db=ceiling_db)
        assert result[0] == pytest.approx(-ceiling)
        assert result[1] == pytest.approx(-0.1)  # below ceiling, unchanged
        assert result[2] == pytest.approx(0.0)
        assert result[3] == pytest.approx(0.1)   # below ceiling, unchanged
        assert result[4] == pytest.approx(ceiling)
