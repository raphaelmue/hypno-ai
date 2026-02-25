"""TTS engine protocol and shared data structures."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class VoiceInfo:
    """Metadata describing a single TTS voice."""

    id: str
    name: str
    language: str
    quality: str
    engine: str
    sample_rate: int = 22050
    size_mb: float = 0.0


@runtime_checkable
class TTSEngine(Protocol):
    """Protocol that all TTS engine adapters must satisfy."""

    @property
    def name(self) -> str:
        """Canonical engine name, e.g. 'piper'."""
        ...

    @property
    def vram_estimate_mb(self) -> int:
        """Estimated VRAM required in MiB (0 for CPU-only engines)."""
        ...

    @property
    def max_workers(self) -> int:
        """Recommended worker-pool size for concurrent paragraph rendering.

        CPU-only engines can safely use multiple workers; GPU engines should
        return 1 to avoid memory contention.
        """
        ...

    def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        prosody_reference: Path | None = None,
    ) -> None:
        """Synthesize *text* and write the result to *output_path* as a WAV file.

        Args:
            text: The text to synthesize.
            voice: Voice identifier (engine-specific).
            speed: Playback speed multiplier (1.0 = normal, 0.85 typical for hypnosis).
            output_path: Destination path for the output WAV file.
            prosody_reference: Optional path to a reference WAV for prosody continuity.
                               Engines that don't support this ignore the argument.
        """
        ...

    def supports_prosody_reference(self) -> bool:
        """Return True if this engine can use a prosody reference audio clip."""
        ...

    def list_voices(self) -> list[VoiceInfo]:
        """Return all voices available for this engine."""
        ...
