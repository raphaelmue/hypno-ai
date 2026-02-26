"""HypnoAI command-line interface."""
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .audio.post_processor import PostProcessConfig, PostProcessor
from .config import Config
from .parser import find_variables, inject_variables, parse
from .parser.ast_nodes import (
    PauseBlock,
    PitchChangeBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
    VoiceChangeBlock,
)
from .render.cache import RenderCache
from .render.pipeline import RenderPipeline
from .tts.piper_engine import PiperEngine
from .tts.voice_registry import VoiceRegistry

app = typer.Typer(
    name="hypnoai",
    help="AI-Powered Local TTS Engine for Hypnosis & Meditation Scripts.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

# Sub-app for model management
models_app = typer.Typer(
    name="models",
    help="Manage TTS engine voice packs (download, list, remove, info).",
    no_args_is_help=True,
)
app.add_typer(models_app, name="models")


def _load_config(config_path: Optional[Path]) -> Config:
    return Config.load(config_path)


def _build_engine(engine: str, cfg: Config):
    if engine == "piper":
        return PiperEngine(cfg.voices_dir, piper_bin=cfg.piper_bin)
    if engine == "coqui":
        from .tts.coqui_engine import CoquiEngine

        return CoquiEngine(cfg.voices_dir, model_name=cfg.coqui_model, use_gpu=cfg.use_gpu)
    return None


@app.command()
def render(
    script: Path = typer.Argument(..., help="Path to a .hypno script file."),
    output: Path = typer.Option(Path("output.wav"), "--output", "-o", help="Output WAV file."),
    voice: Optional[str] = typer.Option(None, "--voice", "-v", help="Voice ID to use."),
    engine: str = typer.Option("piper", "--engine", "-e", help="TTS engine (piper, coqui)."),
    speed: Optional[float] = typer.Option(None, "--speed", "-s", help="Speech speed (1.0 = normal)."),
    pitch: Optional[float] = typer.Option(None, "--pitch", "-p", help="Pitch shift in semitones."),
    var: list[str] = typer.Option([], "--var", help="Variable: NAME=VALUE (repeatable)."),
    workers: Optional[int] = typer.Option(None, "--workers", "-j", help="Worker pool size."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable paragraph render cache."),
    crossfade: Optional[int] = typer.Option(None, "--crossfade-ms", help="Crossfade in ms (default 30)."),
    warmth: Optional[float] = typer.Option(None, "--warmth", help="Warmth EQ boost in dB."),
    no_normalize: bool = typer.Option(False, "--no-normalize", help="Disable loudness normalisation."),
    no_limit: bool = typer.Option(False, "--no-limit", help="Disable brick-wall limiter."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Render a .hypno script to an audio file."""
    cfg = _load_config(config_path)

    if not script.exists():
        err_console.print(f"[red]Error:[/red] Script not found: {script}")
        raise typer.Exit(1)

    # Parse --var NAME=VALUE pairs
    variables: dict[str, str] = {}
    for v in var:
        if "=" not in v:
            err_console.print(
                f"[red]Error:[/red] Invalid --var format: {v!r}. Expected NAME=VALUE."
            )
            raise typer.Exit(1)
        k, val = v.split("=", 1)
        variables[k.strip()] = val.strip()

    source = script.read_text(encoding="utf-8")

    # Variable injection runs before parsing (§2.4)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        source = inject_variables(source, variables)
        blocks = parse(source)

    for w in caught:
        console.print(f"[yellow]Warning:[/yellow] {w.message}")

    active_voice = voice or cfg.default_voice
    active_speed = speed if speed is not None else cfg.default_speed
    active_pitch = pitch if pitch is not None else 0.0

    # Build TTS engine
    tts_engine = _build_engine(engine, cfg)
    if tts_engine is None:
        err_console.print(
            f"[red]Error:[/red] Unknown engine '{engine}'. Available: piper, coqui."
        )
        raise typer.Exit(1)

    # Build cache
    cache: RenderCache | None = None
    if cfg.cache_enabled and not no_cache:
        cache = RenderCache(cfg.cache_dir)

    # Resolve worker count
    active_workers = workers if workers is not None else min(cfg.max_workers, tts_engine.max_workers)

    pipeline = RenderPipeline(
        tts_engine,
        sample_rate=cfg.sample_rate,
        cache=cache,
        max_workers=active_workers,
    )

    # Build post-processor config
    pp_cfg = PostProcessConfig(
        crossfade_ms=crossfade if crossfade is not None else cfg.crossfade_ms,
        warmth_db=warmth if warmth is not None else cfg.warmth_db,
        normalize=not no_normalize and cfg.normalize,
        target_lufs=cfg.target_lufs,
        limit=not no_limit and cfg.limit,
        limit_db=cfg.limit_db,
    )

    with tempfile.TemporaryDirectory(prefix="hypnoai-") as tmp:
        chunks_dir = Path(tmp) / "chunks"
        console.print(
            f"Rendering [bold]{script.name}[/bold] · "
            f"engine=[cyan]{engine}[/cyan] · "
            f"voice=[cyan]{active_voice}[/cyan] · "
            f"speed=[cyan]{active_speed}[/cyan]"
            + (f" · pitch=[cyan]{active_pitch:+.1f}st[/cyan]" if active_pitch else "")
        )
        try:
            job = pipeline.render(
                blocks=blocks,
                output_dir=chunks_dir,
                initial_voice=active_voice,
                initial_speed=active_speed,
                initial_pitch=active_pitch,
            )
        except FileNotFoundError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        except RuntimeError as exc:
            err_console.print(f"[red]Render failed:[/red] {exc}")
            raise typer.Exit(1)

        if not job.chunk_paths:
            console.print("[yellow]Warning:[/yellow] No audio generated (empty script?).")
            raise typer.Exit(0)

        pp = PostProcessor(pp_cfg, sample_rate=cfg.sample_rate)
        try:
            pp.process(job.chunk_paths, output)
        except Exception as exc:
            err_console.print(f"[red]Post-processing failed:[/red] {exc}")
            raise typer.Exit(1)

    console.print(f"[green]Done![/green] Saved to [bold]{output}[/bold]")


@app.command()
def lint(
    script: Path = typer.Argument(..., help="Path to a .hypno script file."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Validate a .hypno script and report statistics."""
    if not script.exists():
        err_console.print(f"[red]Error:[/red] Script not found: {script}")
        raise typer.Exit(1)

    source = script.read_text(encoding="utf-8")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        blocks = parse(source)

    # Gather counts
    text_blocks = [b for b in blocks if isinstance(b, TextBlock)]
    pause_blocks = [b for b in blocks if isinstance(b, PauseBlock)]
    section_blocks = [b for b in blocks if isinstance(b, SectionBlock)]
    voice_changes = [b for b in blocks if isinstance(b, VoiceChangeBlock)]
    speed_changes = [b for b in blocks if isinstance(b, SpeedChangeBlock)]
    pitch_changes = [b for b in blocks if isinstance(b, PitchChangeBlock)]
    variables_used = sorted(set(find_variables(source)))

    # Rough duration estimate: 130 WPM baseline, adjusted by speed directives
    current_speed = 1.0
    estimated_s = 0.0
    for block in blocks:
        if isinstance(block, SpeedChangeBlock):
            current_speed = block.speed
        elif isinstance(block, TextBlock):
            word_count = len(block.text.split())
            estimated_s += (word_count / (130 * current_speed)) * 60
        elif isinstance(block, PauseBlock):
            estimated_s += block.duration_s

    minutes, seconds = divmod(int(estimated_s), 60)

    console.print(f"\n[bold]Script:[/bold] {script}")
    console.print(f"  Paragraphs:    {len(text_blocks)}")
    console.print(f"  Pauses:        {len(pause_blocks)}")
    console.print(f"  Sections:      {len(section_blocks)}")
    console.print(f"  Voice changes: {len(voice_changes)}")
    console.print(f"  Speed changes: {len(speed_changes)}")
    console.print(f"  Pitch changes: {len(pitch_changes)}")
    console.print(f"  Est. duration: {minutes}m {seconds}s")
    if variables_used:
        console.print(f"  Variables:     {', '.join(variables_used)}")

    if caught:
        console.print(f"\n[yellow]Warnings ({len(caught)}):[/yellow]")
        for w in caught:
            console.print(f"  [yellow]·[/yellow] {w.message}")
    else:
        console.print("\n[green]✓ No issues found.[/green]")


@app.command()
def voices(
    engine: str = typer.Option("piper", "--engine", "-e", help="TTS engine to list voices for."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """List available TTS voices."""
    cfg = _load_config(config_path)
    registry = VoiceRegistry(voices_dir=cfg.voices_dir, piper_bin=cfg.piper_bin)
    engine_filter = None if engine == "all" else engine
    voice_list = registry.list_voices(engine=engine_filter)

    if not voice_list:
        console.print(f"[yellow]No voices installed for engine '{engine}'.[/yellow]")
        console.print(f"Place .onnx and .onnx.json model files in: {cfg.voices_dir}")
        return

    table = Table(title=f"Available Voices — {engine}")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Language")
    table.add_column("Quality")
    table.add_column("Sample Rate", justify="right")
    table.add_column("Size (MB)", justify="right")

    for v in voice_list:
        table.add_row(
            v.id,
            v.name,
            v.language,
            v.quality,
            f"{v.sample_rate} Hz",
            f"{v.size_mb:.1f}",
        )
    console.print(table)


@app.command()
def cache(
    action: str = typer.Argument("stats", help="Action: stats | clear"),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Manage the paragraph render cache."""
    cfg = _load_config(config_path)
    rc = RenderCache(cfg.cache_dir)

    if action == "stats":
        console.print(f"Cache directory: {cfg.cache_dir}")
        console.print(f"Size: {rc.size_mb():.1f} MB")
    elif action == "clear":
        n = rc.clear()
        console.print(f"[green]Cleared {n} cached file(s).[/green]")
    else:
        err_console.print(f"[red]Unknown action:[/red] {action!r}. Use 'stats' or 'clear'.")
        raise typer.Exit(1)


@app.command()
def generate(
    template: str = typer.Option("custom", "--template", "-t", help="Template ID (see 'generate --list-templates')."),
    language: str = typer.Option("en", "--language", "-l", help="Script language: en | de."),
    duration: int = typer.Option(20, "--duration", "-d", help="Target duration in minutes."),
    theme: str = typer.Option("relaxation", "--theme", help="Session theme or description."),
    var: list[str] = typer.Option([], "--var", help="Template variable: NAME=VALUE (repeatable)."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider override: ollama | openai | anthropic."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save generated script to this path."),
    list_templates: bool = typer.Option(False, "--list-templates", help="List available templates and exit."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Generate a HypnoScript using an LLM provider."""
    from .ai.template_loader import list_templates as _list_templates, AVAILABLE_TEMPLATES

    if list_templates:
        tbl = Table(title="Available Templates")
        tbl.add_column("ID", style="cyan")
        tbl.add_column("Name")
        tbl.add_column("Category")
        for t in _list_templates():
            tbl.add_row(t["id"], t["name"], t["category"])
        console.print(tbl)
        raise typer.Exit(0)

    if template not in AVAILABLE_TEMPLATES:
        err_console.print(
            f"[red]Error:[/red] Unknown template {template!r}. "
            f"Use --list-templates to see available options."
        )
        raise typer.Exit(1)

    # Parse --var NAME=VALUE pairs
    variables: dict[str, str] = {}
    for v in var:
        if "=" not in v:
            err_console.print(
                f"[red]Error:[/red] Invalid --var format: {v!r}. Expected NAME=VALUE."
            )
            raise typer.Exit(1)
        k, val = v.split("=", 1)
        variables[k.strip()] = val.strip()

    cfg = _load_config(config_path)
    active_provider = provider or cfg.llm_provider

    # Build the LLM provider
    try:
        llm = _build_llm_provider(active_provider, cfg)
    except ValueError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if not llm.is_available():
        err_console.print(
            f"[red]Error:[/red] LLM provider '{active_provider}' is not available. "
            "Check that Ollama is running or that your API key is configured."
        )
        raise typer.Exit(1)

    from .ai.base import ScriptGenerationRequest
    from .ai.script_studio import ScriptStudio

    request = ScriptGenerationRequest(
        template_id=template,
        language=language,
        duration_minutes=duration,
        theme=theme,
        variables=variables,
    )

    console.print(
        f"Generating [bold]{template}[/bold] · "
        f"lang=[cyan]{language}[/cyan] · "
        f"provider=[cyan]{active_provider}[/cyan] · "
        f"~[cyan]{duration}min[/cyan]"
    )

    try:
        result = ScriptStudio(llm).generate(request)
    except RuntimeError as exc:
        err_console.print(f"[red]Generation failed:[/red] {exc}")
        raise typer.Exit(1)

    if result.warnings:
        console.print(f"\n[yellow]Post-processing warnings ({len(result.warnings)}):[/yellow]")
        for w in result.warnings:
            console.print(f"  [yellow]·[/yellow] {w}")

    console.print(
        f"\n[green]Estimated duration:[/green] {result.estimated_duration_minutes:.1f} min"
    )

    if output:
        output.write_text(result.script, encoding="utf-8")
        console.print(f"[green]Saved to[/green] [bold]{output}[/bold]")
    else:
        console.print("\n[bold]--- Generated Script ---[/bold]")
        console.print(result.script)


def _build_llm_provider(provider_name: str, cfg: "Config"):
    """Instantiate an LLM provider from config."""
    from .ai.ollama_provider import OllamaProvider
    from .ai.openai_provider import OpenAIProvider
    from .ai.anthropic_provider import AnthropicProvider

    if provider_name == "ollama":
        return OllamaProvider(base_url=cfg.ollama_url, model=cfg.ollama_model)
    if provider_name == "openai":
        if not cfg.openai_api_key:
            raise ValueError(
                "OpenAI API key not configured. "
                "Set 'openai_api_key' in hypnoai.toml or use --provider ollama."
            )
        return OpenAIProvider(
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            base_url=cfg.openai_base_url,
        )
    if provider_name == "anthropic":
        if not cfg.anthropic_api_key:
            raise ValueError(
                "Anthropic API key not configured. "
                "Set 'anthropic_api_key' in hypnoai.toml or use --provider ollama."
            )
        return AnthropicProvider(
            api_key=cfg.anthropic_api_key,
            model=cfg.anthropic_model,
        )
    raise ValueError(
        f"Unknown LLM provider: {provider_name!r}. "
        "Available: ollama, openai, anthropic."
    )


# ---------------------------------------------------------------------------
# models sub-app
# ---------------------------------------------------------------------------


@models_app.command("list")
def models_list(
    available: bool = typer.Option(False, "--available", help="Show downloadable catalog instead of installed."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """List installed (or available) TTS voice packs."""
    from .resources.model_downloader import ModelDownloader

    cfg = _load_config(config_path)
    downloader = ModelDownloader(cfg.voices_dir)

    if available:
        console.print("Fetching catalog from HuggingFace…")
        try:
            catalog = downloader.get_catalog(force_refresh=True)
        except RuntimeError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        models = sorted(catalog.values(), key=lambda m: m.id)
        tbl = Table(title="Available Voice Packs — Piper")
        tbl.add_column("ID", style="cyan", no_wrap=True)
        tbl.add_column("Language")
        tbl.add_column("Quality")
        tbl.add_column("Size (MB)", justify="right")
        tbl.add_column("License")
        for m in models:
            tbl.add_row(m.id, m.language, m.quality, f"{m.size_mb:.1f}", m.license)
        console.print(tbl)
    else:
        installed = downloader.list_installed()
        if not installed:
            console.print("[yellow]No voice packs installed.[/yellow]")
            console.print(f"Voice directory: {cfg.voices_dir}")
            console.print("Run 'hypnoai models list --available' to browse downloadable packs.")
            return
        tbl = Table(title="Installed Voice Packs")
        tbl.add_column("ID", style="cyan", no_wrap=True)
        tbl.add_column("Engine")
        tbl.add_column("Language")
        tbl.add_column("Quality")
        tbl.add_column("Size (MB)", justify="right")
        for m in installed:
            tbl.add_row(m.id, m.engine, m.language, m.quality, f"{m.size_mb:.1f}")
        console.print(tbl)


@models_app.command("download")
def models_download(
    voice_id: str = typer.Argument(..., help="Voice pack ID, e.g. en_US-amy-medium."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Download a Piper voice pack."""
    from .resources.model_downloader import ModelDownloader

    cfg = _load_config(config_path)
    downloader = ModelDownloader(cfg.voices_dir)

    console.print(f"Downloading [bold]{voice_id}[/bold]…")
    last_pct = [-1]

    def _progress(downloaded: int, total: int) -> None:
        if total > 0:
            pct = int(downloaded * 100 / total)
            if pct != last_pct[0] and pct % 10 == 0:
                console.print(f"  {pct}%  ({downloaded // 1024} KB / {total // 1024} KB)")
                last_pct[0] = pct

    try:
        downloader.download(voice_id, progress=_progress)
    except (ValueError, RuntimeError) as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]Done![/green] {voice_id} installed in {cfg.voices_dir}")


@models_app.command("remove")
def models_remove(
    voice_id: str = typer.Argument(..., help="Voice pack ID to remove."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Remove an installed voice pack."""
    from .resources.model_downloader import ModelDownloader

    cfg = _load_config(config_path)
    downloader = ModelDownloader(cfg.voices_dir)

    removed = downloader.remove(voice_id)
    if removed:
        console.print(f"[green]Removed[/green] {voice_id}")
    else:
        err_console.print(f"[yellow]Not installed:[/yellow] {voice_id}")
        raise typer.Exit(1)


@models_app.command("info")
def models_info(
    voice_id: str = typer.Argument(..., help="Voice pack ID."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Show information about a voice pack."""
    from .resources.model_downloader import ModelDownloader

    cfg = _load_config(config_path)
    downloader = ModelDownloader(cfg.voices_dir)
    info = downloader.info(voice_id)

    if info is None:
        err_console.print(f"[red]Not found:[/red] {voice_id}")
        raise typer.Exit(1)

    console.print(f"\n[bold]{info.id}[/bold]")
    console.print(f"  Engine:    {info.engine}")
    console.print(f"  Language:  {info.language}")
    console.print(f"  Quality:   {info.quality}")
    console.print(f"  Size:      {info.size_mb:.1f} MB")
    console.print(f"  License:   {info.license}")
    console.print(f"  Installed: {'yes' if info.installed else 'no'}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
