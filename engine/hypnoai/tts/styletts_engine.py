"""StyleTTS 2 engine adapter."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from .base import VoiceInfo
from ._torch_compat import register_safe_globals

try:
    from styletts2 import tts as _stts2  # type: ignore[import-untyped]

    _HAS_STYLETTS2 = True
except ImportError:
    _HAS_STYLETTS2 = False
    _stts2 = None  # type: ignore[assignment]

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
    """Adapter for the StyleTTS 2 engine.

    StyleTTS 2 supports voice cloning via reference WAV clips and a rich set of
    emotion controls.  The model is loaded lazily on the first call to
    :meth:`generate`.

    Speed adjustment is performed via scipy resampling after generation, since
    StyleTTS 2 has no native speed parameter.

    Voice resolution: a ``<voices_dir>/<voice_id>.wav`` reference clip is
    required.  Unlike Coqui/F5-TTS, there is no prosody-chain mechanism.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        global _HAS_STYLETTS2, _stts2  # noqa: PLW0603
        if not _HAS_STYLETTS2:
            import importlib
            import sys
            importlib.invalidate_caches()
            for key in [k for k in sys.modules if k == "styletts2" or k.startswith("styletts2.")]:
                del sys.modules[key]
            from ..resources.engine_manager import _ensure_managed_path
            _ensure_managed_path()
            try:
                from styletts2 import tts as _stts2  # type: ignore[import-untyped]
                _HAS_STYLETTS2 = True
            except ImportError as exc:
                raise ImportError(
                    f"StyleTTS2 is not installed. "
                    f"Install it with: pip install styletts2 ({exc})"
                ) from exc
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu
        self._model: "_stts2.StyleTTS2 | None" = None

    # ------------------------------------------------------------------
    # Protocol properties
    # ------------------------------------------------------------------

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
        return self.use_gpu

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

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
        prosody_reference: Path | None = None,  # ignored — StyleTTS 2 has no prosody chain
    ) -> None:
        """Synthesise *text* using StyleTTS 2 and write the WAV to *output_path*.

        Args:
            voice: Voice ID whose corresponding ``<voices_dir>/<voice_id>.wav``
                is used as the style reference.
            prosody_reference: Ignored — StyleTTS 2 uses the voice's own
                reference WAV for style; prosody chaining is not supported.
        """
        self._ensure_loaded()
        ref = self._resolve_voice(voice)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wav = self._model.inference(  # type: ignore[union-attr]
            text,
            target_voice_path=str(ref),
            diffusion_steps=10,
            embedding_scale=1.0,
        )

        wav = np.asarray(wav, dtype=np.float32)

        if abs(speed - 1.0) > 1e-3:
            wav = _resample_speed(wav, speed)

        sf.write(str(output_path), wav, _DEFAULT_SAMPLE_RATE)

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._model is None:
            register_safe_globals()
            self._model = _stts2.StyleTTS2()

    def _resolve_voice(self, voice: str) -> Path:
        """Return the WAV file to use as the style reference."""
        ref = self.voices_dir / f"{voice}.wav"
        if ref.exists():
            return ref
        raise FileNotFoundError(
            f"StyleTTS2 voice reference not found: {ref}. "
            f"Place a '{voice}.wav' clip in {self.voices_dir}."
        )


def _resample_speed(audio: np.ndarray, speed: float) -> np.ndarray:
    """Adjust *audio* duration by *speed* using scipy resampling."""
    from scipy.signal import resample as _scipy_resample

    target_len = max(1, int(len(audio) / speed))
    return _scipy_resample(audio, target_len).astype(np.float32)
