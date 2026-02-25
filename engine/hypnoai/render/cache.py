"""Paragraph-level SHA-256 render cache (§6.5)."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

# Bump this version string whenever the cache format or key schema changes.
_CACHE_VERSION = "v1"


class RenderCache:
    """File-based cache for rendered paragraph WAV files.

    Cache keys incorporate text, voice, speed, pitch, and an optional
    prosody-reference hash so each unique combination is stored separately.

    With prosody chaining active (XTTS / F5-TTS), editing paragraph N
    changes every downstream prosody reference, invalidating paragraphs
    N+1, N+2, … — the caller is responsible for recomputing those keys.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    def cache_key(
        self,
        text: str,
        voice: str,
        speed: float,
        pitch_semitones: float = 0.0,
        prosody_ref_hash: str = "",
    ) -> str:
        """Compute a deterministic cache key for the given render parameters."""
        payload = (
            f"{_CACHE_VERSION}|{text}|{voice}|"
            f"{speed:.6f}|{pitch_semitones:.4f}|{prosody_ref_hash}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def file_hash(path: Path) -> str:
        """Return the SHA-256 hex digest of a file's contents."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> Path | None:
        """Return the cached WAV path for *key*, or None on a miss."""
        path = self.cache_dir / f"{key}.wav"
        return path if path.exists() else None

    def put(self, key: str, source: Path) -> None:
        """Copy *source* WAV into the cache under *key*."""
        dest = self.cache_dir / f"{key}.wav"
        shutil.copy2(str(source), str(dest))

    def copy_to(self, key: str, dest: Path) -> bool:
        """Copy cached item to *dest*. Returns True on hit, False on miss."""
        cached = self.get(key)
        if cached is None:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(cached), str(dest))
        return True

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self) -> int:
        """Delete all cached files. Returns number of files removed."""
        count = 0
        for f in self.cache_dir.glob("*.wav"):
            f.unlink()
            count += 1
        return count

    def size_bytes(self) -> int:
        """Return total size of all cached files in bytes."""
        return sum(f.stat().st_size for f in self.cache_dir.glob("*.wav"))

    def size_mb(self) -> float:
        return round(self.size_bytes() / (1024 * 1024), 1)
