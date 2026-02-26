"""Model downloader — manages TTS engine voice packs for HypnoAI."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

PIPER_VOICES_INDEX_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/voices.json"
)
PIPER_VOICES_BASE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
)

ProgressCallback = Callable[[int, int], None]  # (downloaded_bytes, total_bytes)


@dataclass
class ModelInfo:
    """Metadata for a downloadable or installed TTS model/voice."""

    id: str
    name: str
    engine: str
    language: str
    quality: str
    size_mb: float
    license: str = "unknown"
    files: list[str] = field(default_factory=list)
    installed: bool = False


class ModelDownloader:
    """Downloads and manages Piper TTS voice packs.

    Voice files are stored in *voices_dir* as ``{voice_id}.onnx`` and
    ``{voice_id}.onnx.json`` pairs, matching the layout expected by
    :class:`~hypnoai.tts.piper_engine.PiperEngine`.
    """

    def __init__(self, voices_dir: Path) -> None:
        self._voices_dir = Path(voices_dir)
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        self._catalog: dict[str, ModelInfo] | None = None

    # ------------------------------------------------------------------
    # Catalog

    def fetch_catalog(self) -> dict[str, ModelInfo]:
        """Fetch the Piper voices catalog from HuggingFace and return it."""
        try:
            req = urllib.request.Request(
                PIPER_VOICES_INDEX_URL,
                headers={"User-Agent": "HypnoAI/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to fetch voice catalog: {exc}") from exc

        catalog: dict[str, ModelInfo] = {}
        for voice_id, info in raw.items():
            files_meta = info.get("files", {})
            file_list = list(files_meta.keys())
            total_bytes = sum(
                f.get("size_bytes", 0)
                for f in files_meta.values()
                if isinstance(f, dict)
            )
            catalog[voice_id] = ModelInfo(
                id=voice_id,
                name=info.get("name", voice_id),
                engine="piper",
                language=info.get("language", {}).get("code", ""),
                quality=info.get("quality", ""),
                size_mb=total_bytes / (1024 * 1024),
                license=info.get("license", "unknown"),
                files=file_list,
            )
        self._catalog = catalog
        return catalog

    def get_catalog(self, force_refresh: bool = False) -> dict[str, ModelInfo]:
        """Return the catalog, fetching it from the network if not yet cached."""
        if self._catalog is None or force_refresh:
            self.fetch_catalog()
        assert self._catalog is not None
        return self._catalog

    # ------------------------------------------------------------------
    # Installed voices

    def list_installed(self) -> list[ModelInfo]:
        """Return voice packs currently installed in *voices_dir*."""
        installed: list[ModelInfo] = []
        seen: set[str] = set()
        for onnx_file in sorted(self._voices_dir.glob("*.onnx")):
            voice_id = onnx_file.stem
            if voice_id in seen:
                continue
            seen.add(voice_id)
            json_file = onnx_file.with_suffix(".onnx.json")
            # Parse language/quality from voice_id, e.g. "en_US-amy-medium"
            parts = voice_id.split("-")
            lang = parts[0] if parts else ""
            quality = parts[-1] if len(parts) >= 3 else ""
            size_bytes = onnx_file.stat().st_size
            if json_file.exists():
                size_bytes += json_file.stat().st_size
            installed.append(
                ModelInfo(
                    id=voice_id,
                    name=voice_id,
                    engine="piper",
                    language=lang,
                    quality=quality,
                    size_mb=size_bytes / (1024 * 1024),
                    installed=True,
                )
            )
        return installed

    # ------------------------------------------------------------------
    # Download

    def download(
        self,
        voice_id: str,
        progress: ProgressCallback | None = None,
    ) -> None:
        """Download a Piper voice pack by ID.

        Downloads ``{voice_id}.onnx`` and ``{voice_id}.onnx.json`` from the
        HuggingFace rhasspy/piper-voices repository into *voices_dir*.

        Args:
            voice_id: E.g. ``"en_US-amy-medium"`` or ``"de_DE-thorsten-medium"``.
            progress:  Optional callback ``(downloaded_bytes, total_bytes)`` for
                       progress reporting. *total_bytes* may be 0 if unknown.

        Raises:
            ValueError: If *voice_id* cannot be parsed or is not in the catalog.
            RuntimeError: On network or I/O errors.
        """
        # Validate against the catalog if reachable.
        try:
            catalog = self.get_catalog()
            if voice_id not in catalog:
                raise ValueError(
                    f"Unknown voice: {voice_id!r}. "
                    "Run 'hypnoai models list --available' to browse the catalog."
                )
        except RuntimeError:
            # Catalog fetch failed — proceed with URL construction anyway.
            pass

        # Parse voice_id → path components.
        # Format: {lang_code}-{voice_name}-{quality}
        # e.g.   en_US-amy-medium → lang=en/en_US, name=amy, quality=medium
        parts = voice_id.split("-")
        if len(parts) < 3:
            raise ValueError(
                f"Cannot parse voice ID {voice_id!r}. "
                "Expected format: {lang_code}-{name}-{quality}"
            )
        lang_code = parts[0]          # e.g. "en_US"
        voice_name = parts[1]         # e.g. "amy"
        quality = parts[2]            # e.g. "medium"
        lang_dir = f"{lang_code.split("_")[0]}/{lang_code}"  # "en/en_US"

        base = f"{PIPER_VOICES_BASE_URL}/{lang_dir}/{voice_name}/{quality}"
        files_to_download = [
            (f"{base}/{voice_id}.onnx", self._voices_dir / f"{voice_id}.onnx"),
            (f"{base}/{voice_id}.onnx.json", self._voices_dir / f"{voice_id}.onnx.json"),
        ]
        for url, dest in files_to_download:
            self._download_file(url, dest, progress)

    def _download_file(
        self,
        url: str,
        dest: Path,
        progress: ProgressCallback | None,
    ) -> None:
        req = urllib.request.Request(url, headers={"User-Agent": "HypnoAI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536
                with open(dest, "wb") as f:
                    while chunk := resp.read(chunk_size):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress:
                            progress(downloaded, total)
        except urllib.error.URLError as exc:
            dest.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to download {url}: {exc}") from exc

    # ------------------------------------------------------------------
    # Remove

    def remove(self, voice_id: str) -> bool:
        """Remove an installed voice pack.

        Returns:
            True if at least one file was removed, False if nothing was found.
        """
        removed = False
        for ext in (".onnx", ".onnx.json"):
            p = self._voices_dir / f"{voice_id}{ext}"
            if p.exists():
                p.unlink()
                removed = True
        return removed

    # ------------------------------------------------------------------
    # Info

    def info(self, voice_id: str) -> ModelInfo | None:
        """Return metadata for *voice_id* (installed or from catalog)."""
        installed = {m.id: m for m in self.list_installed()}
        if voice_id in installed:
            return installed[voice_id]
        try:
            return self.get_catalog().get(voice_id)
        except RuntimeError:
            return None
