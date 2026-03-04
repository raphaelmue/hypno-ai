"""Tests for engine_manager — registry, is_installed, install, uninstall."""
from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from hypnoai.resources.engine_manager import (
    ENGINES,
    EngineSpec,
    _check_not_frozen,
    _run_pip,
    install,
    is_installed,
    uninstall,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestEnginesRegistry:
    def test_all_expected_engines_present(self):
        for name in ("piper", "coqui", "kokoro", "styletts2", "f5tts", "bark"):
            assert name in ENGINES

    def test_each_spec_has_required_fields(self):
        for name, spec in ENGINES.items():
            assert isinstance(spec, EngineSpec)
            assert spec.name == name
            assert spec.pip_package
            assert spec.pip_extra
            assert spec.import_name
            assert spec.voice_type in ("catalog", "preset", "clone")
            assert isinstance(spec.languages, list)
            assert spec.license

    def test_piper_is_cpu_only(self):
        assert ENGINES["piper"].vram_mb == 0

    def test_bark_has_largest_model(self):
        bark_gb = ENGINES["bark"].model_size_gb
        assert all(
            spec.model_size_gb <= bark_gb
            for name, spec in ENGINES.items()
            if name != "bark"
        )

    def test_clone_engines_support_cloning(self):
        for name in ("coqui", "styletts2", "f5tts"):
            assert ENGINES[name].supports_cloning

    def test_preset_engines_do_not_support_cloning(self):
        for name in ("kokoro", "bark"):
            assert not ENGINES[name].supports_cloning

    def test_styletts2_has_emotions(self):
        spec = ENGINES["styletts2"]
        assert spec.supports_emotions
        assert len(spec.emotions) > 0


# ---------------------------------------------------------------------------
# is_installed
# ---------------------------------------------------------------------------


class TestIsInstalled:
    def test_unknown_engine_returns_false(self):
        assert is_installed("nonexistent_engine_xyz") is False

    def test_uses_find_spec_not_import(self):
        """is_installed must not trigger a heavy import."""
        with patch("importlib.util.find_spec", return_value=None) as mock_spec:
            result = is_installed("bark")
        # find_spec should be called with the bark import name
        mock_spec.assert_called_once_with("bark")
        assert result is False

    def test_returns_true_when_spec_found(self):
        fake_spec = MagicMock()
        with patch("importlib.util.find_spec", return_value=fake_spec):
            assert is_installed("kokoro") is True

    def test_returns_false_when_spec_none(self):
        with patch("importlib.util.find_spec", return_value=None):
            assert is_installed("kokoro") is False


# ---------------------------------------------------------------------------
# install / uninstall
# ---------------------------------------------------------------------------


class TestInstall:
    def test_unknown_engine_raises_key_error(self):
        with pytest.raises(KeyError):
            install("totally_unknown")

    def test_raises_environment_error_when_frozen(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        with pytest.raises(EnvironmentError, match="packaged app"):
            install("bark")

    def test_runs_pip_install_without_callback(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            install("kokoro")
        cmd = mock_run.call_args[0][0]
        assert sys.executable in cmd
        assert "-m" in cmd
        assert "pip" in cmd
        assert "install" in cmd
        assert ENGINES["kokoro"].pip_package in cmd

    def test_captures_lines_via_callback(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        collected: list[str] = []

        fake_proc = MagicMock()
        fake_proc.stdout = iter(["line1\n", "line2\n"])
        fake_proc.returncode = 0

        with patch("subprocess.Popen", return_value=fake_proc):
            install("kokoro", line_callback=collected.append)

        assert "line1" in collected
        assert "line2" in collected

    def test_raises_runtime_error_on_nonzero_exit(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            with pytest.raises(RuntimeError, match="pip exited"):
                install("kokoro")


class TestUninstall:
    def test_unknown_engine_raises_key_error(self):
        with pytest.raises(KeyError):
            uninstall("totally_unknown")

    def test_runs_pip_uninstall(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            uninstall("kokoro")
        cmd = mock_run.call_args[0][0]
        assert "uninstall" in cmd
        assert ENGINES["kokoro"].pip_package in cmd
        assert "-y" in cmd


# ---------------------------------------------------------------------------
# _check_not_frozen
# ---------------------------------------------------------------------------


class TestCheckNotFrozen:
    def test_raises_when_frozen(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        with pytest.raises(EnvironmentError):
            _check_not_frozen()

    def test_passes_when_not_frozen(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        _check_not_frozen()  # should not raise
