"""Tests for the WorkerPool and WorkItem."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from hypnoai.render.cache import RenderCache
from hypnoai.render.worker import WorkItem, WorkerPool


def _wav(path: Path, n: int = 100, sr: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(n, dtype=np.float32), sr, subtype="FLOAT")


class TestWorkItem:
    def test_cache_key_defaults_to_none(self, tmp_path):
        item = WorkItem(
            index=0,
            text="hello",
            voice="v",
            speed=1.0,
            pitch_semitones=0.0,
            output_path=tmp_path / "out.wav",
        )
        assert item.cache_key is None

    def test_fields_stored(self, tmp_path):
        path = tmp_path / "out.wav"
        item = WorkItem(index=3, text="hi", voice="vox", speed=0.9, pitch_semitones=-1.0, output_path=path, cache_key="abc")
        assert item.index == 3
        assert item.text == "hi"
        assert item.voice == "vox"
        assert item.speed == pytest.approx(0.9)
        assert item.pitch_semitones == pytest.approx(-1.0)
        assert item.output_path == path
        assert item.cache_key == "abc"


class TestWorkerPool:
    def test_empty_items_returns_empty_dict(self, mock_engine):
        pool = WorkerPool(mock_engine)
        assert pool.submit([]) == {}

    def test_single_item_generates_file(self, mock_engine, tmp_path):
        pool = WorkerPool(mock_engine)
        item = WorkItem(index=0, text="hello", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / "out.wav")
        result = pool.submit([item])
        assert 0 in result
        assert result[0].exists()

    def test_engine_receives_correct_args(self, mock_engine, tmp_path):
        pool = WorkerPool(mock_engine)
        item = WorkItem(index=0, text="deep breath", voice="en_US-amy", speed=0.85, pitch_semitones=0.0, output_path=tmp_path / "out.wav")
        pool.submit([item])
        assert mock_engine.calls[0] == ("deep breath", "en_US-amy", 0.85)

    def test_multiple_items_all_returned(self, mock_engine, tmp_path):
        pool = WorkerPool(mock_engine, max_workers=2)
        items = [
            WorkItem(index=i, text=f"chunk {i}", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / f"out{i}.wav")
            for i in range(5)
        ]
        result = pool.submit(items)
        assert set(result.keys()) == {0, 1, 2, 3, 4}
        for path in result.values():
            assert path.exists()

    def test_result_index_matches_work_item(self, mock_engine, tmp_path):
        pool = WorkerPool(mock_engine)
        item = WorkItem(index=42, text="text", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / "out42.wav")
        result = pool.submit([item])
        assert 42 in result

    def test_output_dir_created_if_missing(self, mock_engine, tmp_path):
        pool = WorkerPool(mock_engine)
        nested = tmp_path / "deep" / "nested"
        item = WorkItem(index=0, text="hi", voice="v", speed=1.0, pitch_semitones=0.0, output_path=nested / "out.wav")
        pool.submit([item])
        assert (nested / "out.wav").exists()

    def test_max_workers_clamped_to_one(self, mock_engine):
        pool = WorkerPool(mock_engine, max_workers=0)
        assert pool.max_workers == 1

    def test_cache_hit_skips_engine(self, mock_engine, tmp_path):
        cache = RenderCache(tmp_path / "cache")
        src = tmp_path / "source.wav"
        _wav(src)
        key = cache.cache_key("hello", "v", 1.0)
        cache.put(key, src)

        pool = WorkerPool(mock_engine, cache=cache)
        item = WorkItem(index=0, text="hello", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / "out.wav", cache_key=key)
        pool.submit([item])
        assert mock_engine.calls == []

    def test_cache_miss_stores_result_for_reuse(self, mock_engine, tmp_path):
        cache = RenderCache(tmp_path / "cache")
        key = cache.cache_key("hello", "v", 1.0)

        pool = WorkerPool(mock_engine, cache=cache)
        item1 = WorkItem(index=0, text="hello", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / "out1.wav", cache_key=key)
        pool.submit([item1])

        # Second call with same key should hit cache
        mock_engine.calls.clear()
        item2 = WorkItem(index=1, text="hello", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / "out2.wav", cache_key=key)
        pool.submit([item2])
        assert mock_engine.calls == []  # served from cache

    def test_no_cache_key_skips_cache_lookup(self, mock_engine, tmp_path):
        cache = RenderCache(tmp_path / "cache")
        pool = WorkerPool(mock_engine, cache=cache)
        # item without cache_key — engine should always be called
        item = WorkItem(index=0, text="hello", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / "out.wav", cache_key=None)
        pool.submit([item])
        assert len(mock_engine.calls) == 1

    def test_pitch_zero_skips_pitch_shift(self, mock_engine, tmp_path):
        """pitch_semitones=0 should NOT call _apply_pitch_shift."""
        pool = WorkerPool(mock_engine)
        item = WorkItem(index=0, text="hi", voice="v", speed=1.0, pitch_semitones=0.0, output_path=tmp_path / "out.wav")
        with patch("hypnoai.render.worker._apply_pitch_shift") as mock_shift:
            pool.submit([item])
        mock_shift.assert_not_called()

    def test_nonzero_pitch_calls_pitch_shift(self, mock_engine, tmp_path):
        """pitch_semitones != 0 should call _apply_pitch_shift."""
        pool = WorkerPool(mock_engine)
        item = WorkItem(index=0, text="hi", voice="v", speed=1.0, pitch_semitones=-2.0, output_path=tmp_path / "out.wav")
        with patch("hypnoai.render.worker._apply_pitch_shift") as mock_shift:
            pool.submit([item])
        mock_shift.assert_called_once_with(tmp_path / "out.wav", -2.0)
