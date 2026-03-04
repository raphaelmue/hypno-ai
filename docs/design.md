# HypnoAI — Design Document

**AI-Powered Local Text-to-Speech Engine for Hypnosis & Meditation Scripts**

Version 4.0 · March 2026

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Script Markup Language — HypnoScript](#2-script-markup-language--hypnoscript)
3. [Architecture](#3-architecture)
4. [Model-Agnostic Design](#4-model-agnostic-design)
5. [TTS Backends](#5-tts-backends)
6. [Paragraph-Level Generation & Prosody Continuity](#6-paragraph-level-generation--prosody-continuity)
7. [AI Script Generation](#7-ai-script-generation)
8. [Music, Ambient & Binaural Layering](#8-music-ambient--binaural-layering)
9. [Language Support](#9-language-support)
10. [Audio Post-Processing](#10-audio-post-processing)
11. [Resource Orchestrator](#11-resource-orchestrator)
12. [CLI Interface](#12-cli-interface)
13. [Desktop GUI](#13-desktop-gui)
14. [Packaging & Distribution](#14-packaging--distribution)
15. [Project Structure](#15-project-structure)
16. [Technology Stack](#16-technology-stack)
17. [Configuration](#17-configuration)
18. [Electron ↔ Python Bridge — JSON-RPC Schema](#18-electron--python-bridge--json-rpc-schema)
19. [Implementation Roadmap](#19-implementation-roadmap)
20. [Risk Assessment](#20-risk-assessment)

---

## 1. Vision & Goals

HypnoAI is a local, privacy-first desktop application that transforms written hypnosis and meditation scripts into high-quality audio sessions. Write a script — or let an AI draft one for you — pick a voice, and render a production-ready audio file. All TTS runs locally; AI script generation can optionally use a local LLM or a remote API.

**Goals:**
- Convert scripts into natural-sounding audio using **local TTS models**.
- Support a **script markup language** (HypnoScript) with directives for pauses, music, voice changes, binaural tones, and volume control.
- Generate audio **paragraph-by-paragraph** with **prosody continuity**.
- Allow **voice selection and customization** (pitch, speed, emotion).
- Provide **AI-assisted script generation** with curated prompt templates.
- Offer a polished **desktop GUI** alongside the CLI.
- Be **model-agnostic** — TTS engines, LLMs, and audio backends are all swappable.
- Run entirely offline by default; cloud features are opt-in.
- **Manage system resources** intelligently — GPU VRAM, model lifecycle, concurrent workloads.

**Stretch Goals:** Live Mode for real-time practitioner-guided sessions; batch rendering; session analytics; community template library.

---

## 2. Script Markup Language — HypnoScript

Scripts are plain-text files (`.hypno` or `.md`) mixing spoken content with inline directives in `@{...}`.

### 2.1 Example

```text
@{voice: calm_female}
@{speed: 0.85}

Close your eyes and take a deep breath, {{name}}.

@{pause: 4s}

Now slowly release the air from your lungs.

@{pause: 6s}
@{music: start, file="ocean_waves.mp3", volume=0.15, fade_in=3s}
@{binaural: frequency=4Hz, carrier=100Hz, volume=0.08}

With every breath, you feel yourself sinking deeper into relaxation.

@{pause: 8s}
@{voice: pitch=-2st, emotion=soothing}

You are safe. You are calm. Nothing can disturb you here, {{name}}.

@{binaural: stop, fade_out=3s}
@{music: stop, fade_out=5s}
```

### 2.2 Directive Reference

| Directive | Parameters | Description |
|-----------|-----------|-------------|
| `@{pause: <duration>}` | `Ns` or `Nms` | Insert silence. |
| `@{voice: <n>}` | Voice identifier | Switch TTS voice for subsequent text. |
| `@{voice: pitch=<N>st}` | Semitones (+/-) | Shift pitch relative to voice default. |
| `@{voice: emotion=<tag>}` | `soothing`, `warm`, `whisper`, `confident`, ... | Emotional delivery hint (engine-dependent). |
| `@{speed: <factor>}` | Float (1.0 = normal) | Set speech rate. 0.8–0.9 ideal for hypnosis. |
| `@{volume: <factor>}` | Float 0.0–1.0 | Set speech volume for subsequent paragraphs. |
| `@{music: start}` | `file`, `volume`, `fade_in` | Begin looping a background audio track. |
| `@{music: stop}` | `fade_out` | Stop the current background track. |
| `@{music: volume=<N>}` | `fade` | Adjust music volume mid-session. |
| `@{binaural: frequency=<N>Hz}` | `carrier`, `volume`, `fade_in` | Start a programmatically generated binaural beat. |
| `@{binaural: stop}` | `fade_out` | Stop binaural tones. |
| `@{breath: <pattern>}` | e.g. `4-7-8` (inhale-hold-exhale) | Insert a guided breathing cycle with timed silence. |
| `@{section: <n>}` | Label string | Named marker for navigation, chapter metadata, and GUI heatmaps. |
| `@{comment: <text>}` | Any text | Author note; ignored during rendering. |

### 2.3 Variable Injection

Scripts support **Mustache-style variables** (`{{name}}`) resolved before parsing from a dictionary supplied at render time. The GUI provides a "Session Variables" panel. Undefined variables produce a **warning** — the raw `{{name}}` text remains in output.

### 2.4 Parsing Rules

1. Blank lines separate **paragraphs** — each becomes one TTS generation unit.
2. Directives on their own line apply *before* the next paragraph.
3. Directives are cumulative until overridden.
4. Variable injection runs **before** directive parsing.
5. Unknown directives produce a **warning**, not an error.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   HypnoAI Desktop / CLI                          │
└──────────┬──────────────────────────────────┬───────────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────┐           ┌─────────────────────────┐
│   AI Script Studio   │           │     Script Parser        │
│  LLM Provider ◄─────┤──────────►│  .hypno → AST of Blocks │
│  + Prompt Templates  │           │  (TextBlock, Pause,      │
└─────────────────────┘           │   MusicCue, Binaural...) │
                                  └──────────┬───────────────┘
                                             │  List[Block]
                                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Render Pipeline                             │
│  Paragraph workers → WAV chunks (prosody-chained for XTTS/F5)  │
│  Silence / Binaural / Music generators run in parallel          │
└──────────────────────────────┬──────────────────────────────────┘
                               │  paths to WAV chunk files
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Audio Assembler                             │
│  Concatenate + crossfade + normalize + limit → final file        │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
                         session.wav / .mp3 / .flac
```

### 3.1 Core Components

| Component | Responsibility |
|-----------|---------------|
| **Script Parser** | Tokenize `.hypno` files into an ordered AST. Variable injection, syntax validation, warnings. |
| **Voice Registry** | Discovers available TTS models/voices, exposes metadata, handles parameter overrides. |
| **TTS Engine Adapter** | Abstraction over TTS backends. Returns audio from text + voice config + optional prosody context. |
| **AI Script Studio** | Manages LLM providers and prompt templates for script generation. |
| **Resource Orchestrator** | GPU/CPU model lifecycle — loads, unloads, sequences heavy models to prevent VRAM contention. |
| **Render Pipeline** | Iterates over AST blocks, dispatches TTS jobs with prosody context, collects ordered WAV chunk paths. |
| **Binaural Generator** | Programmatic tone synthesis for brainwave entrainment. |
| **Music Mixer** | Loads background tracks, loops, applies fades and auto-ducking. |
| **Audio Assembler** | Concatenates chunks, crossfades, normalizes loudness, applies limiter, encodes output, embeds chapter markers. |
| **Engine Manager** | Single source of truth for all engine metadata, install/uninstall via pip subprocess. |
| **Sidecar** | JSON-RPC 2.0 server over stdin/stdout; bridges Electron frontend to Python backend. |

---

## 4. Model-Agnostic Design

No concrete model or provider is hardwired into any layer.

```
┌────────────────────────────────────────────────────────────┐
│                  HypnoAI Application                        │
├──────────────────┬──────────────────┬──────────────────────┤
│   TTSEngine      │   LLMProvider    │   AudioBackend        │
│   (Protocol)     │   (Protocol)     │   (Protocol)          │
├──────────────────┼──────────────────┼──────────────────────┤
│ ● PiperEngine    │ ● OllamaProvider │ ● soundfile + numpy   │
│ ● CoquiEngine    │ ● OpenAIProvider │ ● pydub               │
│ ● StyleTTSEngine │ ● AnthropicProv. │                       │
│ ● KokoroEngine   │ ● (any OpenAI-   │                       │
│ ● BarkEngine     │   compatible)    │                       │
│ ● F5TTSEngine    │                  │                       │
└──────────────────┴──────────────────┴──────────────────────┘
```

### 4.1 TTS Engine Protocol

```python
class TTSEngine(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def requires_gpu(self) -> bool: ...
    @property
    def vram_estimate_mb(self) -> int: ...
    def load(self) -> None: ...
    def unload(self) -> None: ...
    def is_loaded(self) -> bool: ...
    def list_voices(self) -> list[VoiceInfo]: ...
    def generate(
        self,
        text: str,
        voice: str,
        speed: float = 1.0,
        pitch_shift_st: float = 0.0,
        emotion: str | None = None,
        prosody_reference: Path | None = None,
    ) -> AudioSegment: ...
    def supports_cloning(self) -> bool: ...
    def supports_prosody_reference(self) -> bool: ...
    def supports_emotions(self) -> list[str]: ...
    def clone_voice(self, name: str, reference_audio: Path) -> VoiceInfo: ...
```

### 4.2 LLM Provider Protocol

```python
class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def requires_gpu(self) -> bool: ...
    def is_available(self) -> bool: ...
    def generate(self, system_prompt: str, user_prompt: str, ...) -> str: ...
    def stream(self, system_prompt: str, user_prompt: str, ...) -> Iterator[str]: ...
```

Adding a new TTS model or LLM is a matter of writing one adapter class.

---

## 5. TTS Backends

All TTS runs locally. Engines are **optional extras** (`pip install hypnoai[kokoro]`).

| Engine | Quality | Speed | VRAM | Prosody Ref | Emotions | Notes |
|--------|---------|-------|------|-------------|----------|-------|
| **Piper** | Good | Very fast (RT ×20+) | CPU only | No | No | ONNX-based, many voices. Bundled in sidecar. |
| **Coqui XTTS v2** | Excellent | Moderate (RT ×1–3) | ~4 GB | **Yes** | No | Voice cloning; prosody reference chaining. |
| **Kokoro** | Excellent | Fast | ~2 GB | No | No | Apache 2.0 licensed. Preset voices (af_*/am_*=en-us, bf_*/bm_*=en-gb). |
| **StyleTTS 2** | Excellent | Fast | ~3 GB | No | **Yes** | Style vectors for emotional control. |
| **F5-TTS** | Excellent | Moderate | ~4 GB | **Yes** | No | Strong zero-shot voice cloning. |
| **Bark** | Very good | Slow | ~6 GB | No | Partial | Supports non-speech sounds (sighs, breathing). |

**Emotion tags** (`@{voice: emotion=...}`) are best-effort. Engines without native support degrade gracefully (logged info, not error). For engines without support, heuristic post-processing applies (e.g. `whisper` → reduce volume + subtle reverb).

---

## 6. Paragraph-Level Generation & Prosody Continuity

Generating the entire script in one TTS call is fragile. HypnoAI generates **one paragraph at a time** while maintaining **tonal continuity** across paragraph boundaries.

### 6.1 Prosody Reference Chain

For engines that support it (XTTS v2, F5-TTS), HypnoAI passes the **tail end of the previous paragraph's audio** as a prosody reference. This prevents jarring tone "restarts" between paragraphs — critical for hypnotherapy where a slow, descending, calming tone is essential.

```
Paragraph 1 ──generate──► [audio₁] ──tail 3s──┐
                                                │ prosody_reference
Paragraph 2 ──generate──► [audio₂] ──tail 3s──┤
                                                │ prosody_reference
Paragraph 3 ──generate──► [audio₃]             ...
```

### 6.2 Concurrency Strategy

```
Phase 1 (sequential):  TTS with prosody chain (for XTTS/F5-TTS)
Phase 2 (parallel):    Post-process chunks concurrently
Phase 3 (sequential):  Assemble in order
```

For engines **without** prosody support (Piper, Kokoro), paragraphs are generated fully in parallel.

### 6.3 Caching

Paragraphs are cached by content hash. Editing one paragraph only regenerates changed and downstream chunks (downstream because their prosody reference changes).

```python
cache_key = sha256(f"{text}|{voice}|{speed}|{pitch}|{prosody_ref_hash}")
```

---

## 7. AI Script Generation

HypnoAI can use an LLM to draft scripts from a user description. This is a **guided, template-driven** workflow — the LLM never runs unsupervised, and users always review before rendering.

### 7.1 Prompt Templates

Pre-built templates encode both HypnoScript syntax and therapeutic semantics:

| Template | Category |
|----------|----------|
| `progressive_relaxation` | Relaxation |
| `sleep_induction` | Sleep |
| `focus_enhancement` | Focus |
| `habit_change` | Habit |
| `anxiety_relief` | Anxiety |
| `confidence_boost` | Self-esteem |
| `pain_management` | Pain |
| `custom` | General |

Each template has language-specific variants (`en.toml`, `de.toml`). Native templates are preferred; English template with a language instruction serves as fallback.

### 7.2 LLM Providers

| Provider | Type | Privacy |
|----------|------|---------|
| **Ollama** | Local | Full privacy |
| **OpenAI API** | Remote | Data sent to OpenAI |
| **Anthropic API** | Remote | Data sent to Anthropic |
| **Any OpenAI-compatible** | Either | Varies (covers LM Studio, vLLM, etc.) |

### 7.3 Post-Processing

1. **Syntax check** — Auto-fix common LLM mistakes (e.g. `@{pause 5s}` → `@{pause: 5s}`).
2. **Safety scan** — Flag authoritarian language, distressing imagery.
3. **Structure check** — Verify induction, body, and emergence sections exist.
4. **Duration estimate** — Word count + pauses; warn if far from target.
5. **Pacing analysis** — Flag paragraphs exceeding language-appropriate WPM threshold.

---

## 8. Music, Ambient & Binaural Layering

### 8.1 Music Timeline

```
Speech:    [████ Text₁ ████]---silence---[████ Text₂ ████]
Music:     [▓▓▓▓▓▓▓▓▓▓▓▓▓▓ ocean_waves.mp3 (looped) ▓▓▓▓▓]
Binaural:  [░░░░░░░░░░░░░░░░░░░░░░ 4Hz theta ░░░░░░░ fade]
```

- Background tracks are looped to session length and volume-automated.
- **Auto-ducking**: reduce music volume during speech, restore during pauses.

### 8.2 Binaural Tone Generator

Generated programmatically (no pre-recorded files needed):

```python
# Left ear: carrier; Right ear: carrier + beat frequency
# Brain perceives the difference as the target frequency
left  = np.sin(2 * np.pi * carrier * t) * volume
right = np.sin(2 * np.pi * (carrier + frequency) * t) * volume
```

| Brainwave | Frequency | Use Case |
|-----------|-----------|----------|
| Delta | 0.5–4 Hz | Deep sleep |
| Theta | 4–8 Hz | Hypnosis, deep relaxation |
| Alpha | 8–13 Hz | Calm focus, light meditation |
| Beta | 13–30 Hz | Alert, focused (awakening) |

> Binaural beats require **stereo output** and **headphones**. The app warns when `@{binaural}` is present.

### 8.3 Audio Formats & Chapter Markers

- Input: `.mp3`, `.wav`, `.ogg`, `.flac` — Output: `.wav`, `.mp3`, `.flac`, `.ogg`
- `@{section: ...}` embeds chapter markers: ID3 CHAP frames (MP3), iTunes chapters (M4A), cue points (WAV).

---

## 9. Language Support

English and German are first-class languages. Adding a new language requires a voice pack, a pacing profile (TOML), and optionally localized prompt templates — no code changes needed.

### 9.1 Language-Specific Pacing

| Language | Ideal WPM | "Too Fast" |
|----------|-----------|------------|
| **English** | 60–80 | > 90 |
| **German** | 50–70 | > 80 |

The linter also warns on **voice–language mismatches** (e.g. German script + English voice).

---

## 10. Audio Post-Processing

| Stage | Purpose | Library |
|-------|---------|---------|
| **Crossfade** | Smooth transitions between chunks (20–50ms). | numpy / pydub |
| **De-essing** | Optional sibilance reduction. | scipy |
| **EQ / Warmth** | Gentle low-mid boost for soothing tone. | scipy.signal |
| **Loudness normalization** | Target -16 LUFS (ITU-R BS.1770). | pyloudnorm |
| **Compression** | Light dynamic range compression. | numpy |
| **Limiter** | Brick-wall at -1 dBFS. Prevents clipping when mixing speech + music + binaural. | numpy |
| **Encoding** | Export to target format + chapter markers. | soundfile / pydub / mutagen |

---

## 11. Resource Orchestrator

Consumer hardware cannot run a large LLM and a large TTS model simultaneously. The orchestrator prevents contention by managing model lifecycle with LRU eviction.

| Scenario | VRAM Needed | 8 GB GPU |
|----------|-------------|----------|
| Ollama (Llama 3.1 8B Q4) | ~5 GB | ✅ |
| Coqui XTTS v2 | ~4 GB | ✅ |
| Both simultaneously | ~9 GB | ❌ OOM |

The orchestrator auto-evicts least-recently-used models when a new one needs to load. The GUI shows a **VRAM indicator** (e.g. "3.8 / 8.0 GB"). In CPU-only mode, Piper is selected as default TTS; LLM routes to a CPU-optimized local model or remote API.

---

## 12. CLI Interface

```bash
# Voices
hypnoai voices --list
hypnoai voices --clone my_therapist --reference sample.wav --engine coqui

# Engine management
hypnoai engines list                    # show installed + available engines
hypnoai engines install kokoro          # install engine via pip
hypnoai engines uninstall bark          # remove engine

# Voice packs (Piper)
hypnoai models list                     # installed Piper voice packs
hypnoai models download en_US-amy-medium
hypnoai models remove de_DE-thorsten-medium

# Rendering
hypnoai render session.hypno -o session.wav
hypnoai render session.hypno -o session.mp3 --format mp3 --bitrate 192k
hypnoai render session.hypno -o out.wav --voice calm_female --speed 0.85
hypnoai render session.hypno -o out.wav --var name=Sarah --var safe_place=meadow

# Preview & validation
hypnoai preview session.hypno --paragraph 5 --play
hypnoai lint session.hypno

# AI script generation
hypnoai generate --template progressive_relaxation \
                 --duration 15 --theme "ocean beach" \
                 --language en --var name=Sarah \
                 --provider ollama -o session.hypno

# System info
hypnoai system --info
```

---

## 13. Desktop GUI

### 13.1 Technology: Electron + React

| Consideration | Decision | Rationale |
|---------------|----------|-----------|
| **Framework** | **Electron v31** | Cross-platform, mature ecosystem, easy sidecar process management. |
| **Frontend** | **React + TypeScript** | Rich editor components. |
| **Styling** | **Tailwind CSS** | Custom `surface`/`accent`/`warm` dark palette. |
| **Backend bridge** | **Electron IPC → Python sidecar** | JSON-RPC over stdin/stdout. Audio passed as **file paths**, never raw bytes. |

### 13.2 Screen Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  HypnoAI                              [Engine: Piper]  ─  □  ✕  │
├───────────────┬──────────────────────────────────────────────────┤
│               │                                                  │
│  📁 Sessions  │  ┌─── Script Editor ──────────────────────────┐  │
│               │  │                                             │  │
│  ▸ My Scripts │  │  @{voice: calm_female}                     │  │
│    Deep Relax │  │  @{speed: 0.85}         ┌─ Pacing Heatmap─┐│  │
│    Sleep      │  │                          │ ▓▓▓░░▓▓░░░▓▓▓░ ││  │
│    Morning    │  │  Close your eyes...      │ ok fast ok  ok  ││  │
│               │  │                          └─────────────────┘│  │
│  ▸ AI Drafts  │  │  @{pause: 4s}                               │  │
│               │  └─────────────────────────────────────────────┘  │
│  ─────────    │                                                  │
│  📋 Variables │  ┌─── Voice & Render Settings ─────────────────┐  │
│  name: Sarah  │  │  Engine: [Piper ▾]   Voice: [amy-medium ▾]  │  │
│               │  │  Speed:  [===●===]   Pitch: [===●===]       │  │
│  ─────────    │  │  ████████████░░░░  45% — Paragraph 5/11     │  │
│  📦 Engines   │  │  [▶ Preview]  [⏺ Render]                    │  │
│  Piper ✅     │  └─────────────────────────────────────────────┘  │
│  XTTS  ✅     │                                                  │
│  [Manage...]  │                                                  │
└───────────────┴──────────────────────────────────────────────────┘
```

### 13.3 Key GUI Panels

**Sidebar** — Session tree, Variables panel (auto-populated from `{{variable}}` references in script), Engine/Model Manager.

**Script Editor** — HypnoScript syntax highlighting; directive inline blocks; **pacing heatmap** gutter (green=60–80 WPM, yellow=borderline, red=too fast); inline linter warnings; paragraph-click-to-preview; autocomplete for directives/voices; "Verify Paragraph" (re-renders single chunk for QA).

**AI Script Assistant** — Session type selector, duration slider, theme input, LLM provider selector, streaming generation into editor.

**Voice & Render Settings** — Engine/voice dropdowns, speed/pitch/emotion controls, progress bar with paragraph granularity.

**Model Manager** — Browse, install, uninstall TTS engines and Piper voice packs. Accessible at any time (not just first launch). First-launch wizard wraps this with guided recommendations.

### 13.4 Electron ↔ Python Bridge

The Python engine runs as a **managed sidecar process** via Electron's `child_process`, communicating JSON-RPC 2.0 over stdin/stdout.

- **`electron/main.ts`** — spawns sidecar, handles `rpc-call` / `rpc-stream` IPC from renderer
- **`electron/preload.ts`** — exposes `window.electronAPI` (`rpcCall`, `rpcStream`) via contextBridge
- **`src/hooks/useRpc.ts`** — checks `isElectron()` guard before calling `window.electronAPI`

Audio data is exchanged as **file paths only**, never raw bytes or base64. The sidecar writes WAV chunks to a shared temp directory; Electron reads them directly for playback and waveform rendering.

---

## 14. Packaging & Distribution

### 14.1 Strategy: Bootstrap + Runtime Engine Install

The initial installer is small (~15 MB). ML engines are too large to bundle and are installed at runtime via `engine_manager.install()`.

```
Phase 1: Tiny Installer
  • Electron shell + React frontend
  • Python sidecar binary (PyInstaller, bundles core + Piper only)
  • No ML models yet

Phase 2: First-Launch Wizard (wraps ModelManager)
  • Recommends Piper (CPU, ~80 MB) as starting point
  • Optional: Coqui/Kokoro/etc. installed via pip at runtime
  • User downloads preferred Piper voice packs
```

- **PyInstaller spec**: `build/sidecar.spec` — bundles core + piper, excludes torch/TTS/bark
- **Build script**: `build/build.sh [sidecar|electron|all]`
- **Output**: `engine/dist/hypnoai-sidecar` (extraResource in `electron-builder.yml`)
- ML engines cannot be bundled (too large). In frozen context, `engine_manager.install()` raises `EnvironmentError`.
- **App updates**: via Electron's auto-updater.
- **Engine updates**: downloaded on demand; version-pinned in config.

---

## 15. Project Structure

```
hypnoai/
├── pyproject.toml              # hatchling build, pytest testpaths=engine/tests
├── README.md
│
├── engine/                     # Python backend (CLI + sidecar)
│   ├── hypnoai/
│   │   ├── cli.py              # Typer CLI (lazy engine imports in _build_engine())
│   │   ├── config.py
│   │   ├── parser/
│   │   │   ├── lexer.py
│   │   │   ├── ast_nodes.py
│   │   │   ├── parser.py
│   │   │   └── variables.py   # {{variable}} injection
│   │   ├── tts/
│   │   │   ├── base.py         # TTSEngine protocol
│   │   │   ├── piper_engine.py
│   │   │   ├── coqui_engine.py
│   │   │   ├── kokoro_engine.py
│   │   │   ├── bark_engine.py
│   │   │   ├── f5tts_engine.py
│   │   │   ├── styletts_engine.py
│   │   │   └── voice_registry.py  # exports only base + registry (no heavy imports)
│   │   ├── ai/
│   │   │   ├── base.py         # LLMProvider protocol
│   │   │   ├── ollama_provider.py
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── templates/
│   │   │   │   ├── progressive_relaxation/{en,de}.toml
│   │   │   │   ├── sleep_induction/{en,de}.toml
│   │   │   │   └── ...
│   │   │   └── post_processor.py
│   │   ├── render/
│   │   │   ├── pipeline.py     # prosody-aware rendering + worker pool
│   │   │   ├── cache.py        # SHA-256 content-addressed cache
│   │   │   ├── music_mixer.py
│   │   │   └── binaural.py     # programmatic tone generator
│   │   ├── audio/
│   │   │   ├── assembler.py
│   │   │   ├── effects.py
│   │   │   ├── normalize.py
│   │   │   ├── limiter.py      # brick-wall limiter
│   │   │   ├── chapters.py     # chapter marker embedding
│   │   │   └── encoder.py
│   │   ├── resources/
│   │   │   ├── engine_manager.py   # EngineSpec + ENGINES dict; install/uninstall via pip
│   │   │   ├── model_manager.py    # PiperModelManager (ONNX voice download/list/remove)
│   │   │   └── voice_manager.py
│   │   └── sidecar/
│   │       ├── server.py       # JSON-RPC 2.0 dispatcher
│   │       ├── session.py      # temp dir + job registry
│   │       └── handlers/
│   │           ├── script.py   # script.lint
│   │           ├── render.py   # render.start/progress/cancel/preview
│   │           ├── voices.py   # voices.list/clone
│   │           ├── ai.py       # ai.generate (streaming)
│   │           ├── models.py   # models.list/download/remove (Piper voices)
│   │           ├── engines.py  # engines.list/install/uninstall
│   │           └── sessions.py
│   └── tests/
│
├── desktop/                    # Electron v31 + React frontend
│   ├── electron/
│   │   ├── main.ts             # main process; spawns sidecar, handles IPC
│   │   └── preload.ts          # contextBridge: window.electronAPI
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ScriptEditor.tsx    # editor + pacing heatmap
│   │   │   ├── PacingHeatmap.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── VariablesPanel.tsx
│   │   │   ├── VoiceRenderSettings.tsx
│   │   │   ├── AIAssistant.tsx
│   │   │   ├── ModelManager.tsx    # engines + voice packs (always accessible)
│   │   │   └── VoiceManager.tsx
│   │   └── hooks/
│   │       └── useRpc.ts
│   ├── tsconfig.electron.json  # compiles electron/ → dist-electron/ (NodeNext ESM)
│   ├── electron-builder.yml    # extraResources: hypnoai-sidecar
│   ├── vite.config.ts          # base: './' in production (file:// asset loading)
│   └── package.json            # main: dist-electron/main.js
│
├── build/
│   ├── sidecar.spec            # PyInstaller spec
│   └── build.sh                # build: sidecar | electron | all
│
└── examples/
    ├── en/
    └── de/
```

---

## 16. Technology Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| **Python engine** | Python 3.12 | Best TTS/ML ecosystem. |
| **CLI** | Typer | Modern, type-hinted CLI. |
| **Desktop shell** | Electron v31 | Cross-platform; Node.js main process. |
| **Frontend** | React + TypeScript + Tailwind | Custom dark theme palette. |
| **TTS (fast/CPU)** | Piper | Bundled in sidecar binary. |
| **TTS (quality/clone)** | Coqui XTTS v2 | Prosody reference chaining. |
| **TTS (balanced)** | Kokoro | Apache 2.0, preset voices. |
| **TTS (emotion)** | StyleTTS 2 | Style vectors. |
| **LLM (local)** | Ollama | Easy model management. |
| **LLM (remote)** | OpenAI / Anthropic API | Optional. |
| **Audio I/O** | soundfile + numpy | Low-level, reliable. |
| **Mixing** | pydub | Overlay, fade, conversion. |
| **Pitch shift** | librosa / pyrubberband | High quality. |
| **Binaural** | numpy (signal gen) | Zero external deps. |
| **Normalization** | pyloudnorm | ITU-R BS.1770. |
| **Chapter markers** | mutagen | ID3/M4A metadata. |
| **Packaging** | PyInstaller + electron-builder | Sidecar binary + Electron app. |
| **Testing** | pytest + Vitest | 56+ tests passing. |

---

## 17. Configuration

```toml
# hypnoai.toml

[general]
default_tts_engine = "piper"
default_voice = "en_US-amy-medium"
output_format = "wav"
cache_enabled = true
cache_dir = "./cache"

[render]
max_workers_cpu = 3
max_workers_gpu = 1
crossfade_ms = 30
paragraph_gap_ms = 200
prosody_tail_seconds = 3.0

[audio]
sample_rate = 22050
loudness_target_lufs = -16.0
apply_warmth_eq = true
limiter_ceiling_dbfs = -1.0

[music]
auto_duck = true
duck_amount_db = -6
duck_attack_ms = 300
duck_release_ms = 500

[binaural]
default_carrier_hz = 100.0
stereo_warning = true

[ai]
provider = "ollama"
ollama_model = "llama3.1"
ollama_url = "http://localhost:11434"
# openai_api_key = "sk-..."
# anthropic_api_key = "sk-ant-..."
default_template = "progressive_relaxation"
default_language = "en"

[resources]
vram_budget_mb = 0   # 0 = auto-detect
gpu_enabled = true
model_dir = "./models"

[gui]
theme = "dark"
show_pacing_heatmap = true
```

---

## 18. Electron ↔ Python Bridge — JSON-RPC Schema

All communication uses JSON-RPC 2.0 over stdin/stdout. Audio data is **never** sent over the bridge — only file paths.

### 18.1 Shared Temp Directory

```
/tmp/hypnoai-{session_id}/
├── chunks/          # paragraph WAV files: 000.wav, 001.wav, ...
├── preview.wav      # single paragraph preview
└── output/          # final rendered file
    └── session.wav
```

### 18.2 RPC Methods

**Script & Rendering:**

```jsonc
{ "method": "script.lint", "params": { "path": "/path/to/session.hypno" } }
→ { "result": { "valid": true, "warnings": [...], "paragraph_count": 11,
                "estimated_duration_s": 780, "variables": ["name"],
                "pacing": [{ "paragraph": 0, "wpm": 72 }, ...] } }

{ "method": "render.start", "params": {
    "script_path": "...", "output_path": "...",
    "variables": { "name": "Sarah" }, "voice": "en_US-amy-medium",
    "engine": "piper", "format": "wav"
}}
→ { "result": { "job_id": "abc123" } }

{ "method": "render.progress", "params": { "job_id": "abc123" } }
→ { "result": { "state": "rendering", "current_paragraph": 5, "total": 11,
                "chunk_paths": [...], "elapsed_s": 12.3 } }

{ "method": "render.cancel", "params": { "job_id": "abc123" } }

{ "method": "render.preview", "params": {
    "text": "Close your eyes.", "voice": "en_US-amy-medium", "engine": "piper", "speed": 0.85
}}
→ { "result": { "audio_path": "/tmp/.../preview.wav", "duration_s": 4.2 } }
```

**Voices & AI:**

```jsonc
{ "method": "voices.list", "params": { "engine": "piper" } }
→ { "result": { "voices": [{ "id": "en_US-amy-medium", "language": "en_US", ... }] } }

{ "method": "voices.clone", "params": {
    "name": "my_therapist", "reference_path": "/path/to/sample.wav", "engine": "coqui"
}}
→ { "result": { "voice_id": "cloned-my_therapist" } }

{ "method": "ai.generate", "params": {
    "template": "progressive_relaxation", "language": "en",
    "variables": { "duration": 15, "theme": "ocean", "name": "Sarah" },
    "provider": "ollama"
}}
→ (streamed chunks) → (final) { "result": { "done": true, "validation": { "warnings": [] } } }
```

**Engine Management:**

```jsonc
{ "method": "engines.list" }
→ { "result": { "installed": [...], "available": [...] } }

{ "method": "engines.install", "params": { "name": "kokoro" } }
→ (streaming log lines) → { "result": { "done": true } }

{ "method": "engines.uninstall", "params": { "name": "bark" } }
→ { "result": { "done": true } }
```

### 18.3 Error Codes

| Code | Meaning |
|------|---------|
| -32600 | Invalid request |
| -32601 | Method not found |
| **-1001** | Engine not installed |
| **-1002** | Download/install failed |
| **-1003** | Render failed (includes paragraph index) |
| **-1004** | LLM provider unavailable |
| **-1005** | Script validation error (includes line number) |
| **-1006** | GPU out of memory — suggest CPU engine |

---

## 19. Implementation Roadmap

### ✅ Phase 1 — Engine MVP
- HypnoScript parser (text + pause/voice/speed/language/variables directives).
- Language profiles for English and German (pacing thresholds, voice validation).
- Piper TTS integration with voice selection.
- Sequential paragraph rendering, silence insertion.
- CLI: `render`, `voices --list`, `lint`.

### ✅ Phase 2 — Quality & Concurrency
- Concurrent paragraph generation with worker pool.
- Paragraph-level content-hash caching.
- Audio post-processing chain (crossfade, normalization, warmth EQ, limiter).
- Coqui XTTS v2, Kokoro, Bark, F5-TTS, StyleTTS 2 integration.
- Pitch shifting support.

### ✅ Phase 3 — AI Integration & Engine Management
- LLM provider abstraction + Ollama, OpenAI, Anthropic providers.
- Prompt template system with English and German variants.
- Post-processor (syntax fix, safety scan, pacing analysis).
- CLI: `generate` command with `--language` flag.
- **Engine Manager** (`hypnoai engines install/uninstall/list`) — single source of truth via `EngineSpec`/`ENGINES` dict; pip subprocess install with streaming output.
- Piper Model Manager (`hypnoai models download/list/remove`).

### ✅ Phase 4 — Desktop GUI
- Electron v31 + React scaffold with Python sidecar bridge.
- JSON-RPC communication layer (file-path-based audio).
- Script editor with syntax highlighting + pacing heatmap.
- Variables panel, Voice/render settings, progress bar.
- AI assistant panel with template wizard.
- Model Manager panel (engines + Piper voice packs, always accessible).
- First-launch setup wizard.
- Dark theme with custom Tailwind `surface`/`accent`/`warm` palette.

### 🔲 Phase 5 — Music & Advanced Audio
- Background music layering (`@{music}` directives).
- Auto-ducking during speech.
- Binaural/isochronic tone generator (`@{binaural}` directive).
- `@{breath}` pattern generator.
- Audio timeline with waveform visualization.
- Chapter marker embedding (ID3, M4A).

### 🔲 Phase 6 — Pro Features (Backlog)
- **Prosody Continuity**: sequential rendering with tail-audio reference chaining (XTTS, F5-TTS); prosody-aware cache invalidation; "fast mode" (no chain) for editing vs. "quality mode" for final render.
- **Resource Orchestrator**: VRAM-aware model lifecycle with LRU eviction; GUI VRAM indicator.
- **Emotion tagging** (`@{voice: emotion=whisper}`) with StyleTTS 2 style vectors.
- **Live Mode**: real-time practitioner-guided sessions.
- Batch rendering for A/B script variants.
- Session analytics, community template sharing.

---

## 20. Risk Assessment

| Risk | Mitigation |
|------|------------|
| **Prosody discontinuity** ("Frankenstein audio") | Prosody reference chaining for XTTS/F5-TTS (§6.1); crossfades + normalization for others. |
| **Sidecar data bottleneck** | Exchange file paths only, never raw bytes. Shared temp directory (§18.1). |
| **VRAM contention** (LLM + TTS simultaneously) | Resource Orchestrator with LRU eviction (§11). GUI VRAM meter. |
| **Multi-GB install size** | Bootstrap installer: tiny initial download, progressive engine fetching (§14). |
| **TTS hallucination on long paragraphs** | Paragraph-level generation limits input length. "Verify Paragraph" button for spot-checking. |
| **Audio clipping from mixed layers** | Brick-wall limiter at -1 dBFS as final chain stage (§10). |
| **Model licensing violations** | Engine Manager shows license info; restricted models require explicit acknowledgment. |
| **LLM generates unsafe content** | Post-processor safety scan; user always reviews before render (§7.3). |
| **LLM generates invalid HypnoScript** | Auto-fix common mistakes; lint before render. |
| **Sidecar communication failure** | Heartbeat + timeout; auto-restart sidecar; error UI with recovery actions. |
| **Prosody cache invalidation cascade** | Warn user in GUI; offer fast mode for editing. |
| **Voice–language mismatch** | Linter warns; GUI highlights mismatch before render (§9.1). |
| **Poor non-English AI scripts** | Native prompt templates per language; English template + language instruction as fallback. |
