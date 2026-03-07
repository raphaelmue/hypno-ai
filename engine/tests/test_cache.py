"""Tests for the paragraph render cache."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from hypnoai.render.cache import RenderCache


def _wav(path: Path, n: int = 100, sr: int = 22050) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.zeros(n, dtype=np.float32), sr, subtype="FLOAT")


class TestRenderCache:
    def test_get_miss(self, tmp_path):
        rc = RenderCache(tmp_path / "cache")
        key = rc.cache_key("hello", "voice", 1.0)
        assert rc.get(key) is None

    def test_put_and_get(self, tmp_path):
        rc = RenderCache(tmp_path / "cache")
        src = tmp_path / "chunk.wav"
        _wav(src)
        key = rc.cache_key("hello", "voice", 1.0)
        rc.put(key, src)
        result = rc.get(key)
        assert result is not None
        assert result.exists()

    def test_copy_to_miss(self, tmp_path):
        rc = RenderCache(tmp_path / "cache")
        key = rc.cache_key("x", "v", 1.0)
        dest = tmp_path / "out.wav"
        assert rc.copy_to(key, dest) is False
        assert not dest.exists()

    def test_copy_to_hit(self, tmp_path):
        rc = RenderCache(tmp_path / "cache")
        src = tmp_path / "chunk.wav"
        _wav(src)
        key = rc.cache_key("hello", "voice", 1.0)
        rc.put(key, src)
        dest = tmp_path / "out.wav"
        assert rc.copy_to(key, dest) is True
        assert dest.exists()

    def test_cache_key_differs_by_text(self, tmp_path):
        rc = RenderCache(tmp_path)
        k1 = rc.cache_key("hello", "v", 1.0)
        k2 = rc.cache_key("world", "v", 1.0)
        assert k1 != k2

    def test_cache_key_differs_by_voice(self, tmp_path):
        rc = RenderCache(tmp_path)
        k1 = rc.cache_key("text", "voice-a", 1.0)
        k2 = rc.cache_key("text", "voice-b", 1.0)
        assert k1 != k2

    def test_cache_key_differs_by_speed(self, tmp_path):
        rc = RenderCache(tmp_path)
        k1 = rc.cache_key("text", "v", 1.0)
        k2 = rc.cache_key("text", "v", 0.85)
        assert k1 != k2

    def test_cache_key_differs_by_pitch(self, tmp_path):
        rc = RenderCache(tmp_path)
        k1 = rc.cache_key("text", "v", 1.0, pitch_semitones=0.0)
        k2 = rc.cache_key("text", "v", 1.0, pitch_semitones=-2.0)
        assert k1 != k2

    def test_cache_key_differs_by_prosody_ref(self, tmp_path):
        rc = RenderCache(tmp_path)
        k1 = rc.cache_key("text", "v", 1.0, prosody_ref_hash="")
        k2 = rc.cache_key("text", "v", 1.0, prosody_ref_hash="abc123")
        assert k1 != k2

    def test_cache_key_is_deterministic(self, tmp_path):
        rc = RenderCache(tmp_path)
        k1 = rc.cache_key("text", "voice", 0.9, pitch_semitones=-1.0, prosody_ref_hash="xyz")
        k2 = rc.cache_key("text", "voice", 0.9, pitch_semitones=-1.0, prosody_ref_hash="xyz")
        assert k1 == k2

    def test_cache_key_is_hex_string(self, tmp_path):
        rc = RenderCache(tmp_path)
        key = rc.cache_key("hello", "v", 1.0)
        assert len(key) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in key)

    def test_clear_removes_files(self, tmp_path):
        rc = RenderCache(tmp_path / "cache")
        for i in range(3):
            src = tmp_path / f"chunk{i}.wav"
            _wav(src)
            key = rc.cache_key(str(i), "v", 1.0)
            rc.put(key, src)
        deleted = rc.clear()
        assert deleted == 3
        assert rc.size_bytes() == 0

    def test_size_bytes_zero_initially(self, tmp_path):
        rc = RenderCache(tmp_path / "cache")
        assert rc.size_bytes() == 0

    def test_size_bytes_grows_after_put(self, tmp_path):
        rc = RenderCache(tmp_path / "cache")
        src = tmp_path / "chunk.wav"
        _wav(src, n=4410)  # ~0.2s at 22050 Hz
        key = rc.cache_key("text", "v", 1.0)
        rc.put(key, src)
        assert rc.size_bytes() > 0

    def test_file_hash(self, tmp_path):
        f = tmp_path / "test.wav"
        f.write_bytes(b"hello world")
        h1 = RenderCache.file_hash(f)
        h2 = RenderCache.file_hash(f)
        assert h1 == h2
        assert len(h1) == 64

    def test_cache_dir_created(self, tmp_path):
        cache_dir = tmp_path / "nested" / "cache"
        assert not cache_dir.exists()
        RenderCache(cache_dir)
        assert cache_dir.exists()
