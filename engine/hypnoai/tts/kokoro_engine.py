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
# Prefix convention: first letter = language (a=en-us, b=en-gb, e=es, f=fr,
#   h=hi, i=it, j=ja, p=pt, z=zh), second letter = gender (f/m).
_KOKORO_VOICES = [
    # American English
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
    "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck",
    # British English
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    # Other languages
    "ef_dora", "em_alex",
    "ff_siwis",
    "hf_alpha", "hf_beta", "hm_omega", "hm_psi",
    "if_sara", "im_nicola",
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo",
    "pf_dora", "pm_alex",
    "zf_xiaobei", "zf_xiaoni", "zf_xiaoxiao", "zf_xiaoyi",
]

_KOKORO_LANGUAGES = ["en-us", "en-gb", "es", "fr-fr", "hi", "it", "ja", "pt", "zh"]

# Map kokoro's internal lang_code letter to our language tag.
_LANG_CODE_MAP: dict[str, str] = {
    "a": "en-us",
    "b": "en-gb",
    "e": "es",
    "f": "fr-fr",
    "h": "hi",
    "i": "it",
    "j": "ja",
    "p": "pt",
    "z": "zh",
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
        global _HAS_KOKORO, KPipeline  # noqa: PLW0603
        if not _HAS_KOKORO:
            # Re-attempt import — the package may have been installed at
            # runtime after the module was first loaded.
            import importlib
            import sys
            importlib.invalidate_caches()
            # Remove any cached failed import entries
            for key in [k for k in sys.modules if k == "kokoro" or k.startswith("kokoro.")]:
                del sys.modules[key]
            # Re-register managed site-packages & DLL dirs
            from ..resources.engine_manager import _ensure_managed_path
            _ensure_managed_path()
            try:
                from kokoro import KPipeline  # type: ignore[import-untyped]
                _HAS_KOKORO = True
            except ImportError as exc:
                raise ImportError(
                    f"Kokoro is not installed. "
                    f"Install it with: pip install kokoro ({exc})"
                ) from exc
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
    def sample_rate(self) -> int:
        return _SAMPLE_RATE

    @property
    def vram_estimate_mb(self) -> int:
        return 2048

    @property
    def max_workers(self) -> int:
        return 2

    @property
    def requires_gpu(self) -> bool:
        return self.use_gpu

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
        """Return the kokoro lang_code letter for a given voice ID."""
        prefix = voice[0] if voice else "a"
        return prefix if prefix in _LANG_CODE_MAP else "a"

    def _language_for_voice(self, voice: str) -> str:
        """Return the BCP-47-style language tag for a given voice ID."""
        return _LANG_CODE_MAP.get(voice[0] if voice else "a", "en-us")

    def _get_pipeline(self, lang_code: str) -> "KPipeline":
        """Return a cached ``KPipeline`` for *lang_code*, creating it if needed."""
        if lang_code not in self._pipelines:
            if self.use_gpu:
                try:
                    import torch
                    use_cuda = torch.cuda.is_available()
                except ImportError:
                    use_cuda = False
            else:
                use_cuda = False
            device = "cuda" if use_cuda else "cpu"
            self._pipelines[lang_code] = KPipeline(lang_code=lang_code, device=device)
        return self._pipelines[lang_code]
