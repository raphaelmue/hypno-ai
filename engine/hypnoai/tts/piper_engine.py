"""Piper TTS engine adapter."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .base import VoiceInfo


class PiperEngine:
    """Adapter for the Piper TTS engine.

    Piper is invoked as a subprocess::

        echo "text" | piper --model <model.onnx> --output_file <out.wav>

    Voice models are pairs of ``<id>.onnx`` + ``<id>.onnx.json`` files
    stored inside *voices_dir*.
    """

    def __init__(self, voices_dir: Path, piper_bin: str = "piper") -> None:
        self.voices_dir = voices_dir
        self.piper_bin = piper_bin

    @property
    def name(self) -> str:
        return "piper"

    @property
    def vram_estimate_mb(self) -> int:
        return 0  # CPU-only

    @property
    def max_workers(self) -> int:
        return 4  # subprocess-based, safe to parallelise

    @property
    def requires_gpu(self) -> bool:
        return False  # CPU-only

    @property
    def supported_languages(self) -> list[str]:
        return sorted({v.language for v in self.list_voices()})

    def supports_prosody_reference(self) -> bool:
        return False  # Piper doesn't accept reference audio

    def supports_voice_cloning(self) -> bool:
        return False  # Piper uses catalog models only

    def supported_emotions(self) -> list[str]:
        return []

    def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        prosody_reference: Path | None = None,  # ignored for Piper
    ) -> None:
        """Synthesize *text* using Piper and write the WAV to *output_path*.

        Raises:
            FileNotFoundError: if the voice model files are missing.
            RuntimeError: if piper exits with a non-zero return code.
        """
        model_path = self.voices_dir / f"{voice}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper model not found: {model_path}. "
                f"Run 'hypnoai models download {voice}' to install it."
            )

        # Piper's --length_scale: 1.0 = normal, >1.0 = slower.
        # Our API uses speed where higher = faster, so length_scale = 1/speed.
        length_scale = 1.0 / max(speed, 0.01)

        cmd = [
            self.piper_bin,
            "--model", str(model_path),
            "--output_file", str(output_path),
            "--length_scale", f"{length_scale:.4f}",
            "--noise_scale", "0.667",
            "--noise_w", "0.8",
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Piper passes text to espeak-ng for phonemisation. espeak-ng uses the
        # process locale to decode input bytes. If LANG=C (ASCII-only, common
        # when the sidecar is spawned by Electron without a full user locale),
        # multi-byte UTF-8 sequences for characters like ä, ö, ü, ß are split
        # into individual bytes and mispronounced or silenced. Force C.UTF-8
        # when no UTF-8 locale is already present in the environment.
        env = dict(os.environ)
        if not any(
            (env.get(v) or "").upper().endswith(("UTF-8", "UTF8"))
            for v in ("LC_ALL", "LC_CTYPE", "LANG")
        ):
            env["LC_ALL"] = "C.UTF-8"

        try:
            result = subprocess.run(
                cmd, input=text.encode("utf-8"), capture_output=True, env=env
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Piper executable not found: {self.piper_bin!r}. "
                "Install piper-tts ('pip install piper-tts') or set 'piper_bin' "
                "in hypnoai.toml to the full path of the piper binary."
            )
        if result.returncode != 0:
            raise RuntimeError(
                f"Piper failed (exit {result.returncode}): "
                f"{result.stderr.decode('utf-8', errors='replace')}"
            )

    def list_voices(self) -> list[VoiceInfo]:
        """Discover voices by scanning *voices_dir* for .onnx + .onnx.json pairs."""
        if not self.voices_dir.exists():
            return []
        voices: list[VoiceInfo] = []
        for onnx_path in sorted(self.voices_dir.glob("*.onnx")):
            json_path = onnx_path.with_suffix(".onnx.json")
            if not json_path.exists():
                continue
            voice_id = onnx_path.stem  # e.g. "en_US-amy-medium"
            try:
                meta = json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}

            # Derive human-readable fields from the voice ID convention:
            #   <language>-<name>-<quality>  e.g.  en_US-amy-medium
            parts = voice_id.split("-")
            language = parts[0] if len(parts) >= 1 else "unknown"
            name = parts[1].capitalize() if len(parts) >= 2 else voice_id
            quality = parts[2] if len(parts) >= 3 else "medium"
            sample_rate = meta.get("audio", {}).get("sample_rate", 22050)
            size_mb = round(onnx_path.stat().st_size / (1024 * 1024), 1)

            voices.append(
                VoiceInfo(
                    id=voice_id,
                    name=name,
                    language=language,
                    quality=quality,
                    engine="piper",
                    sample_rate=sample_rate,
                    size_mb=size_mb,
                )
            )
        return voices
