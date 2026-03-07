"""HypnoAI command-line interface."""
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
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

# Sub-app for voice management
voices_app = typer.Typer(
    name="voices",
    help="List, add, and remove TTS voices.",
    no_args_is_help=True,
)
app.add_typer(voices_app, name="voices")

# Sub-app for engine management
engines_app = typer.Typer(
    name="engines",
    help="Manage the active TTS engine (list, use, active).",
    no_args_is_help=True,
)
app.add_typer(engines_app, name="engines")


def _load_config(config_path: Optional[Path]) -> Config:
    return Config.load(config_path)


def _build_engine(engine: str, cfg: Config):
    if engine == "piper":
        return PiperEngine(cfg.voices_dir, piper_bin=cfg.piper_bin)
    if engine == "coqui":
        try:
            from .tts.coqui_engine import CoquiEngine
            return CoquiEngine(cfg.voices_dir, model_name=cfg.coqui_model, use_gpu=cfg.use_gpu)
        except ImportError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            return None
    if engine == "kokoro":
        try:
            from .tts.kokoro_engine import KokoroEngine
            return KokoroEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
        except ImportError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            return None
    if engine == "styletts2":
        try:
            from .tts.styletts_engine import StyleTTSEngine
            return StyleTTSEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
        except ImportError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            return None
    if engine == "f5tts":
        try:
            from .tts.f5tts_engine import F5TTSEngine
            return F5TTSEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
        except ImportError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            return None
    if engine == "bark":
        try:
            from .tts.bark_engine import BarkEngine
            return BarkEngine(cfg.voices_dir, use_gpu=cfg.use_gpu)
        except ImportError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            return None
    return None


def _build_voice_manager(engine: str, cfg: Config):
    """Build the appropriate VoiceManager for *engine*."""
    from .resources.voice_manager import CloneVoiceManager, PiperVoiceManager, PresetVoiceManager
    from .tts.kokoro_engine import _KOKORO_VOICES
    from .tts.bark_engine import _BARK_ALL_SPEAKERS
    from .tts.base import VoiceInfo

    if engine == "piper":
        return PiperVoiceManager(cfg.voices_dir, piper_bin=cfg.piper_bin)
    if engine in ("coqui", "f5tts", "styletts2"):
        return CloneVoiceManager(engine, cfg.voices_dir)
    if engine == "kokoro":
        voices = [
            VoiceInfo(id=v, name=v.replace("_", " ").title(), language="en-us",
                      quality="high", engine="kokoro")
            for v in _KOKORO_VOICES
        ]
        return PresetVoiceManager("kokoro", voices)
    if engine == "bark":
        voices = [
            VoiceInfo(
                id=s, name=s,
                language=s.split("/")[1].split("_")[0] if "/" in s else "en",
                quality="high", engine="bark",
            )
            for s in _BARK_ALL_SPEAKERS
        ]
        return PresetVoiceManager("bark", voices)
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
            f"[red]Error:[/red] Unknown engine '{engine}'. "
            "Available: piper, coqui, kokoro, styletts2, f5tts, bark."
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

    from .parser.ast_nodes import TextBlock as _TextBlock, PauseBlock as _PauseBlock

    total_audio_blocks = sum(1 for b in blocks if isinstance(b, (_TextBlock, _PauseBlock)))

    console.print(
        f"Rendering [bold]{script.name}[/bold] · "
        f"engine=[cyan]{engine}[/cyan] · "
        f"voice=[cyan]{active_voice}[/cyan] · "
        f"speed=[cyan]{active_speed}[/cyan]"
        + (f" · pitch=[cyan]{active_pitch:+.1f}st[/cyan]" if active_pitch else "")
    )

    with tempfile.TemporaryDirectory(prefix="hypnoai-") as tmp:
        chunks_dir = Path(tmp) / "chunks"

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            render_task = progress.add_task(
                "Rendering…",
                total=total_audio_blocks if total_audio_blocks > 0 else None,
            )

            def _render_progress(done: int, total: int) -> None:
                progress.update(render_task, completed=done, total=total)

            try:
                job = pipeline.render(
                    blocks=blocks,
                    output_dir=chunks_dir,
                    initial_voice=active_voice,
                    initial_speed=active_speed,
                    initial_pitch=active_pitch,
                    on_progress=_render_progress,
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

            progress.update(render_task, description="[green]Rendered")
            pp_task = progress.add_task("Post-processing…", total=None)

            pp = PostProcessor(pp_cfg, sample_rate=cfg.sample_rate)
            try:
                pp.process(job.chunk_paths, output)
            except Exception as exc:
                err_console.print(f"[red]Post-processing failed:[/red] {exc}")
                raise typer.Exit(1)

            progress.update(pp_task, description="[green]Post-processed", completed=1, total=1)

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

    token_count = [0]

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
        console=console,
    ) as progress:
        gen_task = progress.add_task("Waiting for LLM…", total=None)

        def _on_token(token: str) -> None:
            token_count[0] += 1
            if token_count[0] % 20 == 0:
                progress.update(gen_task, description=f"Generating… ({token_count[0]} tokens)")

        try:
            result = ScriptStudio(llm).generate(request, stream_callback=_on_token)
        except RuntimeError as exc:
            err_console.print(f"[red]Generation failed:[/red] {exc}")
            raise typer.Exit(1)

    console.print(f"[dim]Generated {token_count[0]} tokens.[/dim]")

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
# voices sub-app
# ---------------------------------------------------------------------------

_SUPPORTED_ENGINES = ["piper", "coqui", "kokoro", "styletts2", "f5tts", "bark"]


@voices_app.command("list")
def voices_list(
    engine: str = typer.Option("piper", "--engine", "-e", help="TTS engine to list voices for (or 'all')."),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language code."),
    available: bool = typer.Option(False, "--available", help="(Piper) Browse downloadable voices from the HuggingFace catalog."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """List installed TTS voices, or browse the Piper download catalog with --available."""
    cfg = _load_config(config_path)

    if available:
        if engine not in ("piper", "all"):
            console.print(
                f"[yellow]Note:[/yellow] --available only applies to Piper. "
                f"Engine '{engine}' ships with fixed built-in voices."
            )
            return
        from .resources.model_manager import PiperModelManager
        console.print("Fetching Piper catalog from HuggingFace…")
        mm = PiperModelManager(cfg.voices_dir)
        try:
            catalog = mm.get_catalog(force_refresh=True)
        except RuntimeError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        entries = sorted(catalog.values(), key=lambda m: m.id)
        if language:
            entries = [m for m in entries if m.language.startswith(language)]
        title = "Available Piper Voices"
        if language:
            title += f" (language: {language})"
        tbl = Table(title=title)
        tbl.add_column("ID", style="cyan", no_wrap=True)
        tbl.add_column("Language")
        tbl.add_column("Quality")
        tbl.add_column("Size (MB)", justify="right")
        tbl.add_column("License")
        for m in entries:
            tbl.add_row(m.id, m.language, m.quality, f"{m.size_mb:.1f}", m.license)
        console.print(tbl)
        return

    engines_to_query = _SUPPORTED_ENGINES if engine == "all" else [engine]

    # Collect voices from all requested engines using their VoiceManagers.
    # This correctly handles each engine's voice model:
    #   piper    — installed ONNX files (catalog-downloaded)
    #   kokoro   — fixed built-in presets (no install needed to list)
    #   bark     — fixed built-in speaker presets
    #   coqui /  f5tts / styletts2 — user .wav reference clips
    voice_list = []
    for eng in engines_to_query:
        vm = _build_voice_manager(eng, cfg)
        if vm is not None:
            voices = vm.list_voices()
            if language:
                voices = [
                    v for v in voices
                    if v.language.startswith(language) or v.language == "multilingual"
                ]
            voice_list.extend(voices)

    if not voice_list:
        if engine in ("piper", "all"):
            console.print("[yellow]No Piper voices installed.[/yellow]")
            console.print("Run 'hypnoai voices list --available' to browse the catalog.")
            console.print("Run 'hypnoai voices add <voice_id>' to download a voice.")
        else:
            eng_obj = _build_engine(engine, cfg)
            if eng_obj is None:
                console.print(
                    f"[yellow]Engine '{engine}' is not installed.[/yellow] "
                    f"Check 'hypnoai engines' for install instructions."
                )
            else:
                console.print(f"[yellow]No voices found for engine '{engine}'.[/yellow]")
        return

    title = f"Installed Voices — {engine}"
    if language:
        title += f" (language: {language})"
    table = Table(title=title)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Language")
    table.add_column("Quality")
    table.add_column("Sample Rate", justify="right")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Custom")

    for v in voice_list:
        table.add_row(
            v.id,
            v.name,
            v.language,
            v.quality,
            f"{v.sample_rate} Hz",
            f"{v.size_mb:.1f}",
            "yes" if v.is_custom else "no",
        )
    console.print(table)


@voices_app.command("add")
def voices_add(
    name: str = typer.Argument(..., help="Voice name / voice_id to add."),
    reference: Optional[Path] = typer.Argument(
        None, help="Reference .wav clip (required for cloning engines: coqui, f5tts, styletts2)."
    ),
    engine: str = typer.Option("piper", "--engine", "-e", help="TTS engine."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Add a new voice.

    For Piper: name is the catalog voice_id (e.g. en_US-amy-medium); downloads ONNX.
    For cloning engines (coqui, f5tts, styletts2): provide a reference .wav clip.
    For preset engines (kokoro, bark): raises an error — no custom voices.
    """
    cfg = _load_config(config_path)
    vm = _build_voice_manager(engine, cfg)

    if vm is None:
        err_console.print(
            f"[red]Error:[/red] Unknown engine '{engine}'. "
            f"Available: {', '.join(_SUPPORTED_ENGINES)}."
        )
        raise typer.Exit(1)

    if engine == "piper":
        # Piper voices are downloaded from HuggingFace — show a download bar.
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            dl_task = progress.add_task(f"Downloading {name}…", total=None)

            def _dl_progress(downloaded: int, total: int) -> None:
                progress.update(
                    dl_task,
                    completed=downloaded,
                    total=total if total > 0 else None,
                )

            try:
                from .resources.voice_manager import PiperVoiceManager
                assert isinstance(vm, PiperVoiceManager)
                voice = vm.add_voice(name, reference, progress=_dl_progress)
            except NotImplementedError as exc:
                err_console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(1)
            except (ValueError, RuntimeError) as exc:
                err_console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(1)
    else:
        try:
            voice = vm.add_voice(name, reference)
        except NotImplementedError as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
        except (ValueError, RuntimeError) as exc:
            err_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    console.print(f"[green]Added voice:[/green] {voice.id} ({engine})")


@voices_app.command("remove")
def voices_remove(
    voice_id: str = typer.Argument(..., help="Voice ID to remove."),
    engine: str = typer.Option("piper", "--engine", "-e", help="TTS engine."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Remove an installed voice."""
    cfg = _load_config(config_path)
    vm = _build_voice_manager(engine, cfg)

    if vm is None:
        err_console.print(
            f"[red]Error:[/red] Unknown engine '{engine}'. "
            f"Available: {', '.join(_SUPPORTED_ENGINES)}."
        )
        raise typer.Exit(1)

    try:
        removed = vm.remove_voice(voice_id)
    except NotImplementedError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if removed:
        console.print(f"[green]Removed:[/green] {voice_id} ({engine})")
    else:
        err_console.print(f"[yellow]Not found:[/yellow] {voice_id} ({engine})")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# engines sub-app
# ---------------------------------------------------------------------------


@engines_app.command("list")
def engines_list() -> None:
    """List all supported TTS engines, their capabilities, and install status."""
    from .resources.engine_manager import ENGINES, is_installed

    tbl = Table(title="TTS Engines")
    tbl.add_column("Engine", style="cyan", no_wrap=True)
    tbl.add_column("Installed", justify="center")
    tbl.add_column("Voice Type")
    tbl.add_column("VRAM (MB)", justify="right")
    tbl.add_column("Model (GB)", justify="right")
    tbl.add_column("Languages")
    tbl.add_column("Cloning", justify="center")
    tbl.add_column("License")

    for spec in ENGINES.values():
        installed = is_installed(spec.name)
        tbl.add_row(
            spec.name,
            "[green]yes[/green]" if installed else "no",
            spec.voice_type,
            str(spec.vram_mb) if spec.vram_mb else "—",
            f"{spec.model_size_gb:.1f}" if spec.model_size_gb else "—",
            ", ".join(spec.languages),
            "yes" if spec.supports_cloning else "no",
            spec.license,
        )
    console.print(tbl)


@engines_app.command("install")
def engines_install(
    engine: str = typer.Argument(..., help="Engine to install (e.g. kokoro, bark, coqui)."),
) -> None:
    """Install a TTS engine's Python package via pip."""
    from .resources.engine_manager import ENGINES, install, is_installed

    if engine not in ENGINES:
        err_console.print(
            f"[red]Unknown engine:[/red] {engine!r}. "
            f"Valid: {', '.join(ENGINES)}"
        )
        raise typer.Exit(1)

    if is_installed(engine):
        console.print(f"[yellow]{engine}[/yellow] is already installed.")
        return

    spec = ENGINES[engine]
    console.print(
        f"Installing [cyan]{engine}[/cyan] "
        f"([dim]{spec.pip_package}[/dim], ~{spec.model_size_gb:.1f} GB model on first use)…"
    )
    try:
        install(engine)
    except EnvironmentError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    except RuntimeError as exc:
        err_console.print(f"[red]Installation failed:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]Installed[/green] {engine}.")
    if spec.model_size_gb > 0:
        console.print(
            f"[dim]Note: the ~{spec.model_size_gb:.1f} GB model weights will be "
            "downloaded automatically on first render.[/dim]"
        )


@engines_app.command("uninstall")
def engines_uninstall(
    engine: str = typer.Argument(..., help="Engine to uninstall."),
) -> None:
    """Uninstall a TTS engine's Python package via pip."""
    from .resources.engine_manager import ENGINES, uninstall, is_installed

    if engine not in ENGINES:
        err_console.print(
            f"[red]Unknown engine:[/red] {engine!r}. "
            f"Valid: {', '.join(ENGINES)}"
        )
        raise typer.Exit(1)

    if not is_installed(engine):
        console.print(f"[yellow]{engine}[/yellow] is not installed.")
        return

    spec = ENGINES[engine]
    console.print(f"Uninstalling [cyan]{engine}[/cyan] ([dim]{spec.pip_package}[/dim])…")
    try:
        uninstall(engine)
    except EnvironmentError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    except RuntimeError as exc:
        err_console.print(f"[red]Uninstall failed:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]Uninstalled[/green] {engine}.")


@engines_app.command("active")
def engines_active(
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Show the currently active TTS engine."""
    cfg = _load_config(config_path)
    console.print(f"Active engine: [cyan]{cfg.default_engine}[/cyan]")


@engines_app.command("use")
def engines_use(
    engine: str = typer.Argument(..., help="Engine to activate."),
    config_path: Optional[Path] = typer.Option(None, "--config", help="Path to hypnoai.toml."),
) -> None:
    """Set the active TTS engine (persists to runtime state file)."""
    from .resources.engine_manager import ENGINES

    if engine not in ENGINES:
        err_console.print(
            f"[red]Unknown engine:[/red] {engine!r}. "
            f"Valid: {', '.join(ENGINES)}"
        )
        raise typer.Exit(1)
    Config.save_state("active_engine", engine)
    console.print(f"[green]Active engine set to:[/green] [cyan]{engine}[/cyan]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
