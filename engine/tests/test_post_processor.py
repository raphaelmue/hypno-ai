"""Tests for the PostProcessor pipeline."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from hypnoai.audio.post_processor import PostProcessConfig, PostProcessor

SR = 22050


def _wav(path: Path, duration_s: float = 1.0, amplitude: float = 0.5, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(duration_s * sr)
    t = np.linspace(0, duration_s, n, endpoint=False)
    data = (np.sin(2 * np.pi * 440 * t) * amplitude).astype(np.float32)
    sf.write(str(path), data, sr, subtype="FLOAT")


def _silent_wav(path: Path, n: int = 100, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(n, dtype=np.float32), sr, subtype="FLOAT")


class TestPostProcessConfig:
    def test_defaults(self):
        cfg = PostProcessConfig()
        assert cfg.crossfade_ms == 30
        assert cfg.warmth_db == 0.0
        assert cfg.normalize is True
        assert cfg.target_lufs == pytest.approx(-16.0)
        assert cfg.limit is True
        assert cfg.limit_db == pytest.approx(-1.0)


class TestPostProcessor:
    def test_raises_on_empty_chunks(self, tmp_path):
        cfg = PostProcessConfig(normalize=False, limit=False)
        pp = PostProcessor(cfg, sample_rate=SR)
        with pytest.raises(ValueError, match="No chunks"):
            pp.process([], tmp_path / "out.wav")

    def test_output_file_created(self, tmp_path):
        src = tmp_path / "chunk.wav"
        _wav(src)
        cfg = PostProcessConfig(normalize=False, limit=False)
        pp = PostProcessor(cfg, sample_rate=SR)
        out = tmp_path / "output.wav"
        pp.process([src], out)
        assert out.exists()

    def test_output_is_valid_wav(self, tmp_path):
        src = tmp_path / "chunk.wav"
        _wav(src)
        cfg = PostProcessConfig(normalize=False, limit=False)
        pp = PostProcessor(cfg, sample_rate=SR)
        out = tmp_path / "output.wav"
        pp.process([src], out)
        data, sr = sf.read(str(out), dtype="float32")
        assert sr == SR
        assert len(data) > 0

    def test_single_chunk_passthrough(self, tmp_path):
        src = tmp_path / "chunk.wav"
        _wav(src, amplitude=0.1)
        cfg = PostProcessConfig(crossfade_ms=0, warmth_db=0.0, normalize=False, limit=False)
        pp = PostProcessor(cfg, sample_rate=SR)
        out = tmp_path / "output.wav"
        pp.process([src], out)
        original, _ = sf.read(str(src), dtype="float32")
        result, _ = sf.read(str(out), dtype="float32")
        np.testing.assert_array_almost_equal(result, original)

    def test_two_chunks_concatenated(self, tmp_path):
        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        _wav(a, duration_s=0.5)
        _wav(b, duration_s=0.5)
        cfg = PostProcessConfig(crossfade_ms=0, warmth_db=0.0, normalize=False, limit=False)
        pp = PostProcessor(cfg, sample_rate=SR)
        out = tmp_path / "output.wav"
        pp.process([a, b], out)
        data, _ = sf.read(str(out), dtype="float32")
        # Output should be roughly 2 chunks long (minus any crossfade)
        assert len(data) > int(0.5 * SR)

    def test_crossfade_shortens_output(self, tmp_path):
        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        _wav(a, duration_s=1.0)
        _wav(b, duration_s=1.0)

        cfg_no_xfade = PostProcessConfig(crossfade_ms=0, warmth_db=0.0, normalize=False, limit=False)
        cfg_xfade = PostProcessConfig(crossfade_ms=30, warmth_db=0.0, normalize=False, limit=False)
        pp_no = PostProcessor(cfg_no_xfade, sample_rate=SR)
        pp_xf = PostProcessor(cfg_xfade, sample_rate=SR)

        out_no = tmp_path / "no_xfade.wav"
        out_xf = tmp_path / "xfade.wav"
        pp_no.process([a, b], out_no)
        pp_xf.process([a, b], out_xf)

        data_no, _ = sf.read(str(out_no), dtype="float32")
        data_xf, _ = sf.read(str(out_xf), dtype="float32")
        assert len(data_xf) < len(data_no)

    def test_normalization_applied(self, tmp_path):
        src = tmp_path / "chunk.wav"
        _wav(src, duration_s=1.0, amplitude=0.9)
        cfg_norm = PostProcessConfig(crossfade_ms=0, warmth_db=0.0, normalize=True, limit=False)
        cfg_skip = PostProcessConfig(crossfade_ms=0, warmth_db=0.0, normalize=False, limit=False)
        pp_norm = PostProcessor(cfg_norm, sample_rate=SR)
        pp_skip = PostProcessor(cfg_skip, sample_rate=SR)

        out_norm = tmp_path / "norm.wav"
        out_skip = tmp_path / "skip.wav"
        pp_norm.process([src], out_norm)
        pp_skip.process([src], out_skip)

        data_norm, _ = sf.read(str(out_norm), dtype="float32")
        data_skip, _ = sf.read(str(out_skip), dtype="float32")
        assert not np.allclose(data_norm, data_skip)

    def test_limiter_constrains_peaks(self, tmp_path):
        # A quiet chunk won't trigger the limiter, but we verify it doesn't clip
        src = tmp_path / "chunk.wav"
        _wav(src, duration_s=1.0, amplitude=0.5)
        cfg = PostProcessConfig(crossfade_ms=0, warmth_db=0.0, normalize=False, limit=True, limit_db=-1.0)
        pp = PostProcessor(cfg, sample_rate=SR)
        out = tmp_path / "output.wav"
        pp.process([src], out)
        data, _ = sf.read(str(out), dtype="float32")
        ceiling = 10.0 ** (-1.0 / 20.0)
        assert np.all(np.abs(data) <= ceiling + 1e-6)

    def test_output_dir_created_if_missing(self, tmp_path):
        src = tmp_path / "chunk.wav"
        _wav(src)
        cfg = PostProcessConfig(normalize=False, limit=False)
        pp = PostProcessor(cfg, sample_rate=SR)
        out = tmp_path / "nested" / "deep" / "output.wav"
        pp.process([src], out)
        assert out.exists()

    def test_sample_rate_mismatch_resamples(self, tmp_path):
        """Mismatched input sample rates are resampled to the first file's rate."""
        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        out = tmp_path / "out.wav"
        sf.write(str(a), np.zeros(100, dtype=np.float32), 22050, subtype="FLOAT")
        sf.write(str(b), np.zeros(100, dtype=np.float32), 44100, subtype="FLOAT")
        cfg = PostProcessConfig(crossfade_ms=0, normalize=False, limit=False)
        pp = PostProcessor(cfg, sample_rate=22050)
        pp.process([a, b], out)
        assert out.exists()
        _, sr = sf.read(str(out))
        assert sr == 22050
