"""Audio assembler — concatenates ordered WAV chunks into the final output file."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def assemble(chunk_paths: list[Path], output_path: Path) -> None:
    """Concatenate WAV chunks into a single output file.

    All chunks must share the same sample rate; a :exc:`ValueError` is
    raised on mismatch.  The output is written as a 32-bit float WAV.

    Args:
        chunk_paths: Ordered list of WAV chunk files.
        output_path: Destination path for the assembled output.

    Raises:
        ValueError: If *chunk_paths* is empty or sample rates don't match.
        FileNotFoundError: If a chunk file is missing.
    """
    if not chunk_paths:
        raise ValueError("No chunks to assemble.")

    chunks: list[np.ndarray] = []
    sample_rate: int | None = None

    for path in chunk_paths:
        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
        if sample_rate is None:
            sample_rate = sr
        elif sr != sample_rate:
            raise ValueError(
                f"Sample rate mismatch in {path.name}: "
                f"expected {sample_rate} Hz, got {sr} Hz."
            )
        chunks.append(data)

    combined = np.concatenate(chunks, axis=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), combined, sample_rate, subtype="FLOAT")
