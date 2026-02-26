"""Kokoro TTS engine stub — not yet implemented."""
from __future__ import annotations

from pathlib import Path

from .base import VoiceInfo

try:
    import kokoro as _kokoro  # type: ignore[import-untyped]

    _HAS_KOKORO = True
except ImportError:
    _HAS_KOKORO = False

_KOKORO_VOICES = [
    "af",
    "af_bella",
    "af_sarah",
    "af_sky",
    "af_nicole",
    "am_adam",
    "am_michael",
    "bf_emma",
    "bf_isabella",
    "bm_george",
    "bm_lewis",
]

_KOKORO_LANGUAGES = ["en-us", "en-gb", "fr-fr", "de-de", "ja", "ko", "zh"]


class KokoroEngine:
    """Adapter stub for the Kokoro TTS engine.

    Kokoro uses a single ~300 MB checkpoint with built-in voice presets.
    ``generate()`` raises :exc:`NotImplementedError` — full synthesis support
    is planned for a future phase.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        if not _HAS_KOKORO:
            raise ImportError(
                "Kokoro is not installed. "
                "Install it with: pip install kokoro"
            )
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu

    @property
    def name(self) -> str:
        return "kokoro"

    @property
    def vram_estimate_mb(self) -> int:
        return 2048

    @property
    def max_workers(self) -> int:
        return 2

    @property
    def requires_gpu(self) -> bool:
        return True

    @property
    def supported_languages(self) -> list[str]:
        return _KOKORO_LANGUAGES

    def supports_prosody_reference(self) -> bool:
        return False

    def supports_voice_cloning(self) -> bool:
        return False

    def supported_emotions(self) -> list[str]:
        return []

    def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        prosody_reference: Path | None = None,
    ) -> None:
        raise NotImplementedError("KokoroEngine.generate() is not yet implemented.")

    def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(
                id=v,
                name=v.replace("_", " ").title(),
                language="en-us",
                quality="high",
                engine="kokoro",
            )
            for v in _KOKORO_VOICES
        ]
