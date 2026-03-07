"""PyTorch compatibility helpers.

PyTorch 2.6 changed ``torch.load`` to default to ``weights_only=True``.
Third-party TTS libraries that serialise NumPy data into their checkpoints
fail unless we either whitelist the specific globals or patch torch.load.

Two strategies are provided:

* ``register_safe_globals()`` — whitelist known numpy globals via
  ``torch.serialization.add_safe_globals``.  Works for libraries that only
  embed a small set of numpy types (Coqui, StyleTTS2, F5-TTS).

* ``patch_torch_load()`` — monkey-patch ``torch.load`` to pass
  ``weights_only=False`` by default.  Used for Bark, whose checkpoints embed
  a wider variety of numpy objects that would require an exhaustive allowlist.
  The patch is applied at most once (idempotent).
"""
from __future__ import annotations

_LOAD_PATCHED = False


def register_safe_globals() -> None:
    """Allow numpy scalar globals in ``torch.load`` (PyTorch ≥ 2.6)."""
    try:
        import torch
        import numpy.core.multiarray as _npcma  # noqa: F401
        import numpy as _np

        torch.serialization.add_safe_globals(
            [
                _npcma.scalar,          # type: ignore[attr-defined]
                _np.dtype,
                _np.ndarray,
            ]
        )
    except Exception:  # torch or numpy not installed — no-op
        pass


def patch_torch_load() -> None:
    """Monkey-patch ``torch.load`` to default to ``weights_only=False``.

    Safe to call multiple times — the patch is only applied once.
    """
    global _LOAD_PATCHED
    if _LOAD_PATCHED:
        return
    try:
        import torch

        _original_load = torch.load

        def _patched_load(*args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("weights_only", False)
            return _original_load(*args, **kwargs)

        torch.load = _patched_load  # type: ignore[attr-defined]
        _LOAD_PATCHED = True
    except Exception:
        pass
