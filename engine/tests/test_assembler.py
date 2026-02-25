"""Tests for the audio assembler."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from hypnoai.audio.assembler import assemble


def _write_wav(path: Path, data: np.ndarray, sample_rate: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), data.astype(np.float32), sample_rate, subtype="FLOAT")


class TestAssemble:
    def test_empty_chunks_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No chunks"):
            assemble([], tmp_path / "out.wav")

    def test_single_chunk_copied(self, tmp_path):
        data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        chunk = tmp_path / "000.wav"
        _write_wav(chunk, data)
        out = tmp_path / "out.wav"
        assemble([chunk], out)
        result, sr = sf.read(str(out))
        np.testing.assert_allclose(result, data, atol=1e-5)
        assert sr == 22050

    def test_concatenates_multiple_chunks(self, tmp_path):
        chunks = []
        for i, values in enumerate([[0.1, 0.2], [0.3, 0.4], [0.5]]):
            p = tmp_path / f"{i:03d}.wav"
            _write_wav(p, np.array(values))
            chunks.append(p)
        out = tmp_path / "out.wav"
        assemble(chunks, out)
        result, _ = sf.read(str(out))
        np.testing.assert_allclose(result, [0.1, 0.2, 0.3, 0.4, 0.5], atol=1e-5)

    def test_sample_rate_mismatch_raises(self, tmp_path):
        c1 = tmp_path / "000.wav"
        c2 = tmp_path / "001.wav"
        _write_wav(c1, np.zeros(100), sample_rate=22050)
        _write_wav(c2, np.zeros(100), sample_rate=16000)
        with pytest.raises(ValueError, match="Sample rate mismatch"):
            assemble([c1, c2], tmp_path / "out.wav")

    def test_output_parent_created(self, tmp_path):
        chunk = tmp_path / "000.wav"
        _write_wav(chunk, np.zeros(100))
        out = tmp_path / "nested" / "deep" / "out.wav"
        assemble([chunk], out)
        assert out.exists()

    def test_output_file_created(self, tmp_path):
        chunk = tmp_path / "000.wav"
        _write_wav(chunk, np.zeros(50))
        out = tmp_path / "result.wav"
        assemble([chunk], out)
        assert out.exists()

    def test_silence_chunk_preserved(self, tmp_path):
        data = np.zeros(22050, dtype=np.float32)  # 1s of silence
        chunk = tmp_path / "silence.wav"
        _write_wav(chunk, data)
        out = tmp_path / "out.wav"
        assemble([chunk], out)
        result, sr = sf.read(str(out))
        assert sr == 22050
        assert len(result) == 22050
        assert np.all(result == 0.0)

    def test_stereo_chunks(self, tmp_path):
        data = np.random.rand(100, 2).astype(np.float32)
        chunk = tmp_path / "000.wav"
        _write_wav(chunk, data)
        out = tmp_path / "out.wav"
        assemble([chunk], out)
        result, _ = sf.read(str(out))
        assert result.shape == (100, 2)

    def test_total_length_equals_sum_of_chunks(self, tmp_path):
        lengths = [100, 200, 300]
        chunks = []
        for i, n in enumerate(lengths):
            p = tmp_path / f"{i:03d}.wav"
            _write_wav(p, np.zeros(n))
            chunks.append(p)
        out = tmp_path / "out.wav"
        assemble(chunks, out)
        result, _ = sf.read(str(out))
        assert len(result) == sum(lengths)

    def test_custom_sample_rate_preserved(self, tmp_path):
        chunk = tmp_path / "000.wav"
        _write_wav(chunk, np.zeros(16000), sample_rate=16000)
        out = tmp_path / "out.wav"
        assemble([chunk], out)
        _, sr = sf.read(str(out))
        assert sr == 16000
