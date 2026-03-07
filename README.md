# HypnoAI

> AI-powered local text-to-speech engine for hypnosis & meditation scripts.

Write a script, pick a voice, and render a professional-quality audio session — entirely on your own machine. Optionally let an AI draft the script for you.

---

## Features

- **HypnoScript markup** — a lightweight script language with directives for pauses, voice changes, speed control, and section labelling
- **Six TTS engines** — Piper (CPU, fast), Coqui XTTS v2, Kokoro, StyleTTS2, F5-TTS, Bark
- **Voice cloning** — supply a reference WAV and clone any voice with Coqui, F5-TTS, or StyleTTS2
- **AI script generation** — prompt templates for relaxation, sleep, focus, habit change, and anxiety; works with Ollama (local), OpenAI, or Anthropic
- **Audio post-processing** — loudness normalisation, per-section speed/pitch control, true-peak limiting
- **Desktop GUI** — Tauri v2 + React; script editor with pacing heatmap, AI assistant, model manager, variables panel
- **CLI** — full feature access without the GUI
- **Privacy-first** — all TTS runs locally; cloud LLM is opt-in

---

## HypnoScript Quick Reference

```
@{section: Induction}

Allow yourself to relax. Breathe slowly and deeply.

@{pause: 3s}

@{voice: narrator}
@{speed: 0.85}

Every breath takes you deeper into calm.

@{section: Emergence}

Slowly returning now. Wide awake.
```

Variables are injected at render time:

```
Welcome, {{name}}. Today we focus on {{goal}}.
```

---

## Installation

Requires Python 3.11+ and (optionally) Node.js 20+ / yarn 4 for the desktop app.

```bash
git clone https://github.com/your-org/hypno-ai
cd hypno-ai
python -m venv .venv && source .venv/bin/activate

# Core CLI
pip install -e .

# Add the TTS engine(s) you want
pip install -e ".[piper]"        # CPU-only, fast, recommended for first run
pip install -e ".[kokoro]"       # High-quality, GPU optional
pip install -e ".[coqui]"        # Voice cloning, needs CUDA
pip install -e ".[f5tts]"        # Voice cloning
pip install -e ".[styletts]"     # Voice cloning
pip install -e ".[bark]"         # Expressive/multilingual
```

---

## CLI Usage

### Render a script

```bash
hypnoai render script.hypno --engine piper --voice en_US-amy-medium --output session.wav
```

### Lint a script

```bash
hypnoai lint script.hypno
```

### Generate a script with AI

```bash
# requires a running Ollama instance, or set openai_api_key / anthropic_api_key in hypnoai.toml
hypnoai generate --template relaxation --theme "deep sleep" --duration 20 --output sleep.hypno
```

### Manage voices (Piper)

```bash
hypnoai voices list --available          # browse downloadable voices
hypnoai voices add en_US-ryan-medium     # download a voice
hypnoai voices list                      # show installed voices
```

### Manage models (GPU engines)

```bash
hypnoai models list --available          # list supported GPU engines
hypnoai models download kokoro           # install via pip (shows command)
```

---

## Desktop App

The desktop app is an Electron-based GUI with a Python sidecar process.

### Quick Start (Development)

```bash
# Install Python dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev,piper,pitch]"

# Install desktop dependencies
cd desktop
corepack enable
yarn install

# Run in development mode
yarn dev
```

### Building for Distribution

See [docs/PACKAGING.md](docs/PACKAGING.md) for detailed packaging instructions.

**Quick build (all platforms):**

```bash
# Unix (macOS/Linux)
./scripts/build.sh

# Windows
scripts\build.bat
```

The packaged application will be in `desktop/release/`.

**Platform-specific builds:**

```bash
cd desktop
yarn build:dist:win      # Windows
yarn build:dist:mac      # macOS
yarn build:dist:linux    # Linux
```

### Pre-built Binaries

Download pre-built packages from the [Releases](https://github.com/your-org/hypno-ai/releases) page:

- **Windows**: `.exe` installer or portable
- **macOS**: `.dmg` disk image
- **Linux**: `.AppImage`, `.deb`, or `.rpm`

---

## Configuration

On first run HypnoAI looks for `~/.config/hypnoai/hypnoai.toml`. Override with `--config`:

```toml
voices_dir       = "/home/user/.local/share/hypnoai/voices"
default_engine   = "piper"
default_voice    = "en_US-amy-medium"
llm_provider     = "ollama"         # ollama | openai | anthropic
# openai_api_key   = "sk-..."
# anthropic_api_key = "sk-ant-..."
```

---

## Running the Tests

```bash
source .venv/bin/activate
python -m pytest
```

---

## Project Structure

```
hypno-ai/
├── engine/
│   ├── hypnoai/          # Python package
│   │   ├── parser/       # HypnoScript lexer + AST
│   │   ├── tts/          # TTS engine adapters
│   │   ├── render/       # Parallel render pipeline
│   │   ├── audio/        # Post-processing (normalise, limit)
│   │   ├── ai/           # LLM providers + script templates
│   │   ├── resources/    # Model & voice managers
│   │   ├── sidecar/      # JSON-RPC bridge for the desktop app
│   │   └── cli.py        # Typer CLI entrypoint
│   └── tests/
├── desktop/              # Electron + React frontend
│   ├── src/              # React components & hooks
│   ├── electron/         # Electron main & preload
│   └── build/            # Build resources (icons, etc.)
├── scripts/              # Build scripts
│   ├── build.sh          # Unix build script
│   └── build.bat         # Windows build script
├── docs/
│   └── PACKAGING.md      # Detailed packaging guide
└── hypnoai-sidecar.spec  # PyInstaller spec for sidecar
```

---

## License

MIT
