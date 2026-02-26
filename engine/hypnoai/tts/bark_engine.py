"""Bark TTS engine stub — not yet implemented."""
from __future__ import annotations

from pathlib import Path

from .base import VoiceInfo

try:
    import bark as _bark  # type: ignore[import-untyped]

    _HAS_BARK = True
except ImportError:
    _HAS_BARK = False

_BARK_LANGUAGES = [
    "en", "de", "fr", "es", "it", "ja", "ko", "pl", "pt", "ru", "tr", "zh",
]

# Built-in speaker presets (English + other languages, 10 speakers each)
_BARK_EN_SPEAKERS = [f"v2/en_speaker_{i}" for i in range(10)]
_BARK_OTHER_SPEAKERS = [
    f"v2/{lang}_speaker_{i}"
    for lang in ["de", "fr", "es", "it", "ja", "ko", "pl", "pt", "ru", "tr", "zh"]
    for i in range(10)
]
_BARK_ALL_SPEAKERS = _BARK_EN_SPEAKERS + _BARK_OTHER_SPEAKERS


class BarkEngine:
    """Adapter stub for the Bark TTS engine.

    Bark uses a single ~6 GB multi-file checkpoint with built-in speaker
    presets. ``generate()`` raises :exc:`NotImplementedError` — full synthesis
    support is planned for a future phase.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        if not _HAS_BARK:
            raise ImportError(
                "Bark is not installed. "
                "Install it with: pip install suno-bark"
            )
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu

    @property
    def name(self) -> str:
        return "bark"

    @property
    def vram_estimate_mb(self) -> int:
        return 6144

    @property
    def max_workers(self) -> int:
        return 1

    @property
    def requires_gpu(self) -> bool:
        return True

    @property
    def supported_languages(self) -> list[str]:
        return _BARK_LANGUAGES

    def supports_prosody_reference(self) -> bool:
        return False

    def supports_voice_cloning(self) -> bool:
        return False

    def supported_emotions(self) -> list[str]:
        return ["neutral"]

    def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        prosody_reference: Path | None = None,
    ) -> None:
        raise NotImplementedError("BarkEngine.generate() is not yet implemented.")

    def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(
                id=speaker,
                name=speaker,
                language=speaker.split("/")[1].split("_")[0] if "/" in speaker else "en",
                quality="high",
                engine="bark",
            )
            for speaker in _BARK_ALL_SPEAKERS
        ]
