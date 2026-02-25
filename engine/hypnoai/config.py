"""Configuration management for HypnoAI."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Application configuration loaded from hypnoai.toml."""

    voices_dir: Path = field(default_factory=lambda: Path("engine/voices"))
    cache_dir: Path = field(default_factory=lambda: Path("engine/cache"))
    default_engine: str = "piper"
    default_voice: str = "en_US-amy-medium"
    default_speed: float = 1.0
    piper_bin: str = "piper"
    sample_rate: int = 22050

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load configuration from a TOML file. Returns defaults if not found."""
        if path is None:
            path = Path("hypnoai.toml")
        if not path.exists():
            return cls()
        with open(path, "rb") as f:
            data = tomllib.load(f)
        for key in ("voices_dir", "cache_dir"):
            if key in data:
                data[key] = Path(data[key])
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})
