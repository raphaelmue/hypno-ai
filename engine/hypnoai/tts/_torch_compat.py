"""PyTorch compatibility helpers.

PyTorch 2.6 changed ``torch.load`` to default to ``weights_only=True``.
Third-party TTS libraries that serialise NumPy scalars into their checkpoints
will fail with::

    WeightsUnpickler error: Unsupported global: GLOBAL numpy.core.multiarray.scalar

Call ``register_safe_globals()`` once before loading any such model.
``add_safe_globals`` is idempotent, so repeated calls are safe.
"""
from __future__ import annotations


def register_safe_globals() -> None:
    """Allow numpy scalar globals in ``torch.load`` (PyTorch ≥ 2.6)."""
    try:
        import torch
        import numpy.core.multiarray as _npcma  # noqa: F401

        torch.serialization.add_safe_globals(
            [_npcma.scalar]  # type: ignore[attr-defined]
        )
    except Exception:  # torch or numpy not installed — no-op
        pass
