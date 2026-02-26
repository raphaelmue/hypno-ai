"""F5-TTS engine adapter."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from .base import VoiceInfo

try:
    from f5_tts.api import F5TTS as _F5TTS  # type: ignore[import-untyped]

    _HAS_F5TTS = True
except ImportError:
    _HAS_F5TTS = False
    _F5TTS = None  # type: ignore[assignment]

_DEFAULT_SAMPLE_RATE = 24000


class F5TTSEngine:
    """Adapter for the F5-TTS engine.

    F5-TTS supports zero-shot voice cloning via a reference WAV clip.  The
    model is loaded lazily on the first call to :meth:`generate`.

    Voice resolution order:
    1. *prosody_reference* (when provided — used for prosody chaining)
    2. ``<voices_dir>/<voice_id>.wav``  — pre-recorded reference clip
    3. Raises ``FileNotFoundError``

    ``ref_text`` is intentionally left empty; F5-TTS (≥ 1.1) can auto-
    transcribe the reference audio via its built-in ASR step.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        if not _HAS_F5TTS:
            raise ImportError(
                "F5-TTS is not installed. "
                "Install it with: pip install f5-tts"
            )
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu
        self._model: "_F5TTS | None" = None

    # ------------------------------------------------------------------
    # Protocol properties
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

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
        """Synthesise *text* using F5-TTS and write the WAV to *output_path*.

        Args:
            prosody_reference: When provided, this WAV clip is used as the
                speaker reference instead of the stored voice file.
        """
        self._ensure_loaded()
        ref = self._resolve_voice(voice, prosody_reference)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wav, sr, _spect = self._model.infer(  # type: ignore[union-attr]
            ref_file=str(ref),
            ref_text="",  # let F5-TTS auto-transcribe the reference
            gen_text=text,
            speed=speed,
            show_info=False,
        )

        wav = np.asarray(wav, dtype=np.float32)
        sf.write(str(output_path), wav, sr)

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._model is None:
            device = "cuda" if self.use_gpu else "cpu"
            self._model = _F5TTS(model_type="F5-TTS", device=device)

    def _resolve_voice(self, voice: str, prosody_ref: Path | None) -> Path:
        """Return the WAV file to use as the speaker reference."""
        if prosody_ref is not None and prosody_ref.exists():
            return prosody_ref
        ref = self.voices_dir / f"{voice}.wav"
        if ref.exists():
            return ref
        raise FileNotFoundError(
            f"F5-TTS voice reference not found: {ref}. "
            f"Place a '{voice}.wav' clip in {self.voices_dir}."
        )
