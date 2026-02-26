"""StyleTTS 2 engine stub — not yet implemented."""
from __future__ import annotations

from pathlib import Path

from .base import VoiceInfo

try:
    import styletts2 as _styletts2  # type: ignore[import-untyped]

    _HAS_STYLETTS2 = True
except ImportError:
    _HAS_STYLETTS2 = False

_STYLETTS2_EMOTIONS = [
    "neutral",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgusted",
    "surprised",
]

_DEFAULT_SAMPLE_RATE = 24000


class StyleTTSEngine:
    """Adapter stub for the StyleTTS 2 engine.

    StyleTTS 2 supports voice cloning via reference .wav clips and a rich set
    of emotion controls. ``generate()`` raises :exc:`NotImplementedError` —
    full synthesis support is planned for a future phase.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        if not _HAS_STYLETTS2:
            raise ImportError(
                "StyleTTS2 is not installed. "
                "Install it with: pip install styletts2"
            )
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu

    @property
    def name(self) -> str:
        return "styletts2"

    @property
    def vram_estimate_mb(self) -> int:
        return 3072

    @property
    def max_workers(self) -> int:
        return 1

    @property
    def requires_gpu(self) -> bool:
        return True

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    def supports_prosody_reference(self) -> bool:
        return False

    def supports_voice_cloning(self) -> bool:
        return True

    def supported_emotions(self) -> list[str]:
        return _STYLETTS2_EMOTIONS

    def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        prosody_reference: Path | None = None,
    ) -> None:
        raise NotImplementedError("StyleTTSEngine.generate() is not yet implemented.")

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
                    engine="styletts2",
                    sample_rate=_DEFAULT_SAMPLE_RATE,
                    size_mb=round(wav.stat().st_size / (1024 * 1024), 1),
                    is_custom=True,
                )
            )
        return voices
