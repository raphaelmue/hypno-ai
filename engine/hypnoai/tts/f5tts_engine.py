"""F5-TTS engine stub — not yet implemented."""
from __future__ import annotations

from pathlib import Path

from .base import VoiceInfo

try:
    import f5_tts as _f5_tts  # type: ignore[import-untyped]

    _HAS_F5TTS = True
except ImportError:
    _HAS_F5TTS = False

_DEFAULT_SAMPLE_RATE = 24000


class F5TTSEngine:
    """Adapter stub for the F5-TTS engine.

    F5-TTS supports voice cloning via reference .wav clips and prosody
    continuity via reference audio. ``generate()`` raises :exc:`NotImplementedError`
    — full synthesis support is planned for a future phase.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        if not _HAS_F5TTS:
            raise ImportError(
                "F5-TTS is not installed. "
                "Install it with: pip install f5-tts"
            )
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu

    @property
    def name(self) -> str:
        return "f5tts"

    @property
    def vram_estimate_mb(self) -> int:
        return 4096

    @property
    def max_workers(self) -> int:
        return 1

    @property
    def requires_gpu(self) -> bool:
        return True

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "zh"]

    def supports_prosody_reference(self) -> bool:
        return True

    def supports_voice_cloning(self) -> bool:
        return True

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
        raise NotImplementedError("F5TTSEngine.generate() is not yet implemented.")

    def list_voices(self) -> list[VoiceInfo]:
        """Discover cloned voices from .wav reference files in *voices_dir*."""
        if not self.voices_dir.exists():
            return []
        voices: list[VoiceInfo] = []
        for wav in sorted(self.voices_dir.glob("*.wav")):
            voices.append(
                VoiceInfo(
                    id=wav.stem,
                    name=wav.stem.replace("_", " ").title(),
                    language="en",
                    quality="excellent",
                    engine="f5tts",
                    sample_rate=_DEFAULT_SAMPLE_RATE,
                    size_mb=round(wav.stat().st_size / (1024 * 1024), 1),
                    is_custom=True,
                )
            )
        return voices
