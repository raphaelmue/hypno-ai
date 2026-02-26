"""Kokoro TTS engine adapter."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf

from .base import VoiceInfo

try:
    from kokoro import KPipeline  # type: ignore[import-untyped]

    _HAS_KOKORO = True
except ImportError:
    _HAS_KOKORO = False
    KPipeline = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    pass

# Built-in voice presets bundled with the kokoro checkpoint.
# Prefix convention: a* = American English, b* = British English.
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

# Map our language codes to kokoro's internal lang_code letters.
_LANG_CODE_MAP: dict[str, str] = {
    "en-us": "a",
    "en-gb": "b",
    "de-de": "d",
    "fr-fr": "f",
    "ja": "j",
    "ko": "k",
    "zh": "z",
}

_SAMPLE_RATE = 24000


class KokoroEngine:
    """Adapter for the Kokoro TTS engine.

    Kokoro uses a single ~300 MB checkpoint with built-in voice presets.
    Synthesis is handled by ``KPipeline`` which yields audio chunks as
    float32 numpy arrays at 24 000 Hz.

    Pipelines are cached per ``lang_code`` so that switching between
    American and British English voices on the same engine instance does
    not reload the model.
    """

    def __init__(self, voices_dir: Path, use_gpu: bool = True) -> None:
        if not _HAS_KOKORO:
            raise ImportError(
                "Kokoro is not installed. "
                "Install it with: pip install kokoro"
            )
        self.voices_dir = voices_dir
        self.use_gpu = use_gpu
        self._pipelines: dict[str, "KPipeline"] = {}

    # ------------------------------------------------------------------
    # Protocol properties
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

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
        prosody_reference: Path | None = None,  # ignored — Kokoro has no reference audio
    ) -> None:
        """Synthesise *text* using Kokoro and write the WAV to *output_path*.

        The appropriate ``KPipeline`` is selected based on the voice prefix:
        ``af_*`` / ``am_*`` → American English, ``bf_*`` / ``bm_*`` → British
        English.  Any other prefix falls back to American English.

        Args:
            prosody_reference: Ignored — Kokoro preset voices have no reference
                audio mechanism.
        """
        lang_code = self._lang_code_for_voice(voice)
        pipeline = self._get_pipeline(lang_code)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chunks: list[np.ndarray] = []
        for _gs, _ps, audio in pipeline(text, voice=voice, speed=speed):
            if audio is not None and len(audio) > 0:
                chunks.append(np.asarray(audio, dtype=np.float32))

        if not chunks:
            raise RuntimeError(
                f"Kokoro produced no audio for voice={voice!r}. "
                "Check that the voice ID is valid."
            )
        sf.write(str(output_path), np.concatenate(chunks), _SAMPLE_RATE)

    def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(
                id=v,
                name=v.replace("_", " ").title(),
                language=self._language_for_voice(v),
                quality="high",
                engine="kokoro",
            )
            for v in _KOKORO_VOICES
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lang_code_for_voice(self, voice: str) -> str:
        """Return the kokoro lang_code for a given voice ID."""
        if voice.startswith("af") or voice.startswith("am"):
            return "a"  # American English
        if voice.startswith("bf") or voice.startswith("bm"):
            return "b"  # British English
        return "a"  # safe default

    def _language_for_voice(self, voice: str) -> str:
        """Return the BCP-47-style language tag for a given voice ID."""
        if voice.startswith("af") or voice.startswith("am"):
            return "en-us"
        if voice.startswith("bf") or voice.startswith("bm"):
            return "en-gb"
        return "en-us"

    def _get_pipeline(self, lang_code: str) -> "KPipeline":
        """Return a cached ``KPipeline`` for *lang_code*, creating it if needed."""
        if lang_code not in self._pipelines:
            device = "cuda" if self.use_gpu else "cpu"
            self._pipelines[lang_code] = KPipeline(lang_code=lang_code, device=device)
        return self._pipelines[lang_code]
