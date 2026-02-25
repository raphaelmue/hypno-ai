"""Shared fixtures for HypnoAI tests."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from hypnoai.tts.base import VoiceInfo


class MockTTSEngine:
    """Minimal TTSEngine that records calls and writes silent WAV chunks."""

    name = "mock"
    vram_estimate_mb = 0
    max_workers = 4

    def __init__(self, sample_rate: int = 22050, chunk_duration_s: float = 0.1) -> None:
        self.sample_rate = sample_rate
        self.chunk_duration_s = chunk_duration_s
        self.calls: list[tuple[str, str, float]] = []

    def generate(
        self,
        text: str,
        voice: str,
        speed: float,
        output_path: Path,
        prosody_reference: Path | None = None,
    ) -> None:
        self.calls.append((text, voice, speed))
        n = int(self.sample_rate * self.chunk_duration_s)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), np.zeros(n, dtype=np.float32), self.sample_rate, subtype="FLOAT")

    def supports_prosody_reference(self) -> bool:
        return False

    def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(id="mock-voice", name="Mock", language="en", quality="low", engine="mock")
        ]


@pytest.fixture
def mock_engine() -> MockTTSEngine:
    return MockTTSEngine()


@pytest.fixture
def voices_dir(tmp_path: Path) -> Path:
    vd = tmp_path / "voices"
    vd.mkdir()
    return vd


@pytest.fixture
def fake_voice(voices_dir: Path) -> str:
    """Create a fake en_US-amy-medium voice pair in voices_dir."""
    (voices_dir / "en_US-amy-medium.onnx").write_bytes(b"\x00" * 1024)
    (voices_dir / "en_US-amy-medium.onnx.json").write_text(
        json.dumps({"audio": {"sample_rate": 22050}})
    )
    return "en_US-amy-medium"
