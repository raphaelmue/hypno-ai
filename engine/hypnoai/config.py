"""Configuration management for HypnoAI."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Application configuration loaded from hypnoai.toml."""

    # ------------------------------------------------------------------ Phase 1
    voices_dir: Path = field(default_factory=lambda: Path("engine/voices"))
    cache_dir: Path = field(default_factory=lambda: Path("engine/cache"))
    default_engine: str = "piper"
    default_voice: str = "en_US-amy-medium"
    default_speed: float = 1.0
    piper_bin: str = "piper"
    sample_rate: int = 22050

    # ------------------------------------------------------------------ Phase 2
    # Worker pool
    max_workers: int = 4            # parallel TTS workers (CPU engines only)

    # Paragraph-level render cache
    cache_enabled: bool = True

    # Post-processing chain
    crossfade_ms: int = 30          # crossfade between adjacent chunks
    warmth_db: float = 0.0          # warmth EQ boost in dB (0 = disabled)
    normalize: bool = True          # enable loudness normalisation
    target_lufs: float = -16.0      # normalisation target
    limit: bool = True              # enable brick-wall limiter
    limit_db: float = -1.0          # limiter ceiling in dBFS

    # Coqui XTTS v2
    coqui_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    use_gpu: bool = True

    # ------------------------------------------------------------------ Phase 3
    # LLM providers for AI script generation
    llm_provider: str = "ollama"                    # ollama | openai | anthropic | openai_compat
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

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
