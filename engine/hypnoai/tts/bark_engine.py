"""Bark TTS engine adapter."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import soundfile as sf

from .base import VoiceInfo
from ._torch_compat import register_safe_globals

try:
    from bark import generate_audio, preload_models  # type: ignore[import-untyped]
    from bark import SAMPLE_RATE as _BARK_SAMPLE_RATE  # type: ignore[import-untyped]

    _HAS_BARK = True
except ImportError:
    _HAS_BARK = False
    generate_audio = None  # type: ignore[assignment]
    preload_models = None  # type: ignore[assignment]
    _BARK_SAMPLE_RATE = 24000

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
    """Adapter for the Bark TTS engine.

    Bark uses a ~6 GB multi-file checkpoint with built-in speaker presets.
    Models are loaded lazily on the first call to :meth:`generate`.

    Speed adjustment is performed via scipy resampling after generation, since
    Bark itself has no native speed control.  This changes pitch slightly (like
    a tape-speed effect) — acceptable for hypnosis/meditation material.

    GPU control: set ``use_gpu=False`` to force CPU inference by hiding CUDA
    devices before the Bark models are initialised.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        if not _HAS_BARK:
            raise ImportError(
                "Bark is not installed. "
                "Install it with: pip install suno-bark"
            )
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu
        self._loaded = False

    # ------------------------------------------------------------------
    # Protocol properties
    # ------------------------------------------------------------------

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
        return self.use_gpu

    @property
    def supported_languages(self) -> list[str]:
        return _BARK_LANGUAGES

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

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
        prosody_reference: Path | None = None,  # ignored
    ) -> None:
        """Synthesise *text* using Bark and write the WAV to *output_path*.

        Args:
            voice: Bark speaker preset, e.g. ``"v2/en_speaker_3"``.
            prosody_reference: Ignored — Bark preset voices have no reference
                audio mechanism.
        """
        self._ensure_loaded()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        audio: np.ndarray = generate_audio(text, history_prompt=voice)
        audio = audio.astype(np.float32)

        if abs(speed - 1.0) > 1e-3:
            audio = _resample_speed(audio, speed)

        sf.write(str(output_path), audio, _BARK_SAMPLE_RATE)

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            register_safe_globals()
            if not self.use_gpu:
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
            preload_models(
                text_use_gpu=self.use_gpu,
                coarse_use_gpu=self.use_gpu,
                fine_use_gpu=self.use_gpu,
                codec_use_gpu=self.use_gpu,
            )
            self._loaded = True


def _resample_speed(audio: np.ndarray, speed: float) -> np.ndarray:
    """Adjust *audio* duration by *speed* using scipy resampling."""
    from scipy.signal import resample as _scipy_resample

    target_len = max(1, int(len(audio) / speed))
    return _scipy_resample(audio, target_len).astype(np.float32)
