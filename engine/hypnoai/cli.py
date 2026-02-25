"""HypnoAI command-line interface."""
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .audio.assembler import assemble
from .config import Config
from .parser import find_variables, inject_variables, parse
from .parser.ast_nodes import (
    PauseBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
    VoiceChangeBlock,
)
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


def _load_config(config_path: Optional[Path]) -> Config:
    return Config.load(config_path)


@app.command()
def render(
    script: Path = typer.Argument(..., help="Path to a .hypno script file."),
    output: Path = typer.Option(Path("output.wav"), "--output", "-o", help="Output WAV file."),
    voice: Optional[str] = typer.Option(None, "--voice", "-v", help="Voice ID to use."),
    engine: str = typer.Option("piper", "--engine", "-e", help="TTS engine."),
    speed: Optional[float] = typer.Option(None, "--speed", "-s", help="Speech speed (1.0 = normal)."),
    var: list[str] = typer.Option([], "--var", help="Variable: NAME=VALUE (repeatable)."),
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

    if engine != "piper":
        err_console.print(f"[red]Error:[/red] Engine '{engine}' is not yet supported. Use 'piper'.")
        raise typer.Exit(1)

    tts_engine = PiperEngine(cfg.voices_dir, piper_bin=cfg.piper_bin)
    pipeline = RenderPipeline(tts_engine, sample_rate=cfg.sample_rate)

    with tempfile.TemporaryDirectory(prefix="hypnoai-") as tmp:
        chunks_dir = Path(tmp) / "chunks"
        console.print(
            f"Rendering [bold]{script.name}[/bold] · "
            f"voice=[cyan]{active_voice}[/cyan] · "
            f"speed=[cyan]{active_speed}[/cyan]"
        )
        try:
            job = pipeline.render(
                blocks=blocks,
                output_dir=chunks_dir,
                initial_voice=active_voice,
                initial_speed=active_speed,
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

        assemble(job.chunk_paths, output)

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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
