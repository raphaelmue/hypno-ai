"""Coqui XTTS v2 engine adapter."""
from __future__ import annotations

from pathlib import Path

from .base import VoiceInfo
from ._torch_compat import register_safe_globals

try:
    from TTS.api import TTS as _CoquiTTS  # type: ignore[import-untyped]

    _HAS_COQUI = True
except ImportError:
    _HAS_COQUI = False
    _CoquiTTS = None  # type: ignore[assignment]

_DEFAULT_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
_DEFAULT_LANGUAGE = "en"
_DEFAULT_SAMPLE_RATE = 24000


class CoquiEngine:
    """Adapter for Coqui XTTS v2.

    XTTS v2 supports voice cloning via a reference WAV file and prosody
    continuity through the same mechanism — passing the tail of the previous
    paragraph's audio as *prosody_reference* keeps tonal energy consistent.

    Voice resolution order:
    1. *prosody_reference* (takes priority when set — used for prosody chaining)
    2. ``<voices_dir>/<voice_id>.wav``  — pre-recorded reference clip
    3. Raises ``FileNotFoundError``

    The model is loaded lazily on the first call to :meth:`generate`.
    """

    def __init__(
        self,
        voices_dir: Path,
        model_name: str = _DEFAULT_MODEL,
        language: str = _DEFAULT_LANGUAGE,
        use_gpu: bool = True,
    ) -> None:
        global _HAS_COQUI, _CoquiTTS  # noqa: PLW0603
        if not _HAS_COQUI:
            import importlib
            import sys
            importlib.invalidate_caches()
            for key in [k for k in sys.modules if k == "TTS" or k.startswith("TTS.")]:
                del sys.modules[key]
            from ..resources.engine_manager import _ensure_managed_path
            _ensure_managed_path()
            try:
                from TTS.api import TTS as _CoquiTTS  # type: ignore[import-untyped]
                _HAS_COQUI = True
            except ImportError as exc:
                raise ImportError(
                    f"Coqui TTS is not installed. "
                    f"Install it with: pip install TTS ({exc})"
                ) from exc
        self.voices_dir = voices_dir
        self.model_name = model_name
        self.language = language
        self.use_gpu = use_gpu
        self._tts: "_CoquiTTS | None" = None

    # ------------------------------------------------------------------
    # Protocol properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "coqui"

    @property
    def vram_estimate_mb(self) -> int:
        return 4096  # XTTS v2 requires ~4 GB VRAM

    @property
    def max_workers(self) -> int:
        return 1  # GPU model — serialise to avoid OOM

    @property
    def requires_gpu(self) -> bool:
        return self.use_gpu

    @property
    def supported_languages(self) -> list[str]:
        return ["multilingual"]

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
        """Synthesise *text* using XTTS v2 and write the WAV to *output_path*.

        Args:
            prosody_reference: When provided, this WAV clip is used as the
                speaker reference instead of the stored voice file. This is the
                mechanism behind prosody continuity (§6.2).
        """
        self._ensure_loaded()
        ref = self._resolve_voice(voice, prosody_reference)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._tts.tts_to_file(  # type: ignore[union-attr]
            text=text,
            file_path=str(output_path),
            speaker_wav=str(ref),
            language=self.language,
            speed=speed,
        )

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
                    language="multilingual",
                    quality="excellent",
                    engine="coqui",
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
        if self._tts is None:
            register_safe_globals()
            self._tts = _CoquiTTS(self.model_name, gpu=self.use_gpu)

    def _resolve_voice(self, voice: str, prosody_ref: Path | None) -> Path:
        """Return the WAV file to use as the speaker reference."""
        if prosody_ref is not None and prosody_ref.exists():
            return prosody_ref
        ref = self.voices_dir / f"{voice}.wav"
        if ref.exists():
            return ref
        raise FileNotFoundError(
            f"Coqui voice reference not found: {ref}. "
            f"Place a '{voice}.wav' clip in {self.voices_dir}."
        )
