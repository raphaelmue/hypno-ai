"""Backward-compatibility shim — use :mod:`model_manager` for new code.

All imports from this module continue to work unchanged so that existing code
and tests are unaffected.
"""
from .model_manager import (  # noqa: F401
    ModelInfo,
    PiperModelManager as ModelDownloader,
    ProgressCallback,
)

__all__ = ["ModelDownloader", "ModelInfo", "ProgressCallback"]
