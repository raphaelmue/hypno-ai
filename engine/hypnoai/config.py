"""Configuration management for HypnoAI."""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# User data directory — all runtime data lives here
_HYPNOAI_DIR = Path.home() / ".hypnoai"
_STATE_FILE = _HYPNOAI_DIR / "state.json"


def _ensure_hypnoai_dir() -> None:
    """Create ~/.hypnoai/ and its subdirectories if they don't exist."""
    _HYPNOAI_DIR.mkdir(parents=True, exist_ok=True)
    (_HYPNOAI_DIR / "voices").mkdir(exist_ok=True)
    (_HYPNOAI_DIR / "cache").mkdir(exist_ok=True)


@dataclass
class Config:
    """Application configuration loaded from hypnoai.toml."""

    # ------------------------------------------------------------------ Phase 1
    voices_dir: Path = field(default_factory=lambda: Path.home() / ".hypnoai" / "voices")
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".hypnoai" / "cache")
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
        """Load configuration from a TOML file. Returns defaults if not found.

        Runtime state (active_engine) stored in ``hypnoai_state.json`` takes
        precedence over the static ``default_engine`` in the TOML so that
        ``hypnoai engines use <name>`` survives across invocations without
        requiring the user to edit their config file.
        """
        _ensure_hypnoai_dir()
        if path is None:
            path = Path("hypnoai.toml")
        if not path.exists():
            cfg = cls()
        else:
            with open(path, "rb") as f:
                data = tomllib.load(f)
            for key in ("voices_dir", "cache_dir"):
                if key in data:
                    data[key] = Path(data[key])
            known = set(cls.__dataclass_fields__)
            cfg = cls(**{k: v for k, v in data.items() if k in known})

        # Override with runtime state (persisted by `engines use`)
        active = cls.load_state("active_engine")
        if active:
            cfg.default_engine = active
        return cfg

    # ------------------------------------------------------------------
    # Runtime state helpers — thin JSON store for mutable settings

    @classmethod
    def load_state(cls, key: str, default=None):
        """Read a single key from the runtime state file."""
        try:
            with open(_STATE_FILE) as f:
                return json.load(f).get(key, default)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return default

    @classmethod
    def save_state(cls, key: str, value) -> None:
        """Persist a single key into the runtime state file."""
        _ensure_hypnoai_dir()
        state: dict = {}
        try:
            with open(_STATE_FILE) as f:
                state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        state[key] = value
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
