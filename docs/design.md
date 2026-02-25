# HypnoAI — Design Document

**AI-Powered Local Text-to-Speech Engine for Hypnosis & Meditation Scripts**

Version 3.0 · February 2026

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Script Markup Language — HypnoScript](#2-script-markup-language--hypnoscript)
3. [Architecture](#3-architecture)
4. [Model-Agnostic Design](#4-model-agnostic-design)
5. [TTS Backend — Local Model Selection](#5-tts-backend--local-model-selection)
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
18. [Tauri ↔ Python Bridge — JSON-RPC Schema](#18-tauri--python-bridge--json-rpc-schema)
19. [Example Session Scripts](#19-example-session-scripts)
20. [Implementation Roadmap](#20-implementation-roadmap)
21. [Risk Assessment](#21-risk-assessment)

---

## 1. Vision & Goals

HypnoAI is a local, privacy-first desktop application that transforms written hypnosis and meditation scripts into high-quality audio sessions. Write a script — or let an AI draft one for you — pick a voice, and render a production-ready audio file. All TTS runs locally; AI script generation can optionally use a local LLM or a remote API, at the user's choice.

### Primary Goals

- Convert authored scripts into natural-sounding spoken audio using a **local TTS model**.
- Support a **script markup language** with directives for pauses, music layers, voice changes, binaural tones, and volume control.
- Generate audio **paragraph-by-paragraph** with **prosody continuity** for stable, natural-sounding output.
- Allow **voice selection and customization** (pitch, speed, warmth, emotion).
- Provide **AI-assisted script generation** with curated prompt templates for different session types.
- Offer a polished **desktop GUI** alongside the CLI.
- Be **model-agnostic** at every layer — TTS engines, LLMs, and audio backends are all swappable.
- Run entirely offline by default — cloud features are opt-in.
- **Manage system resources** intelligently — GPU VRAM, model lifecycle, and concurrent workloads.

### Stretch Goals

- **Live Mode** for real-time practitioner-guided sessions.
- Batch rendering of script variants (e.g. different durations).
- Session analytics (listening history, favorites).
- Community template library.

---

## 2. Script Markup Language — HypnoScript

Scripts are plain-text files (`.hypno` or `.md`) that mix spoken content with inline directives wrapped in `@{...}`. Directives are case-insensitive.

### 2.1 Syntax Overview

```text
@{language: en}
@{voice: calm_female}
@{speed: 0.85}

Close your eyes and take a deep breath, {{name}}.

@{pause: 4s}

Now slowly release the air from your lungs.

@{pause: 6s}
@{music: start, file="ocean_waves.mp3", volume=0.15, fade_in=3s}
@{binaural: frequency=4Hz, carrier=100Hz, volume=0.08}

With every breath, you feel yourself sinking deeper
into a state of complete relaxation.

@{pause: 8s}
@{voice: pitch=-2st, emotion=soothing}

You are safe. You are calm. Nothing can disturb you here, {{name}}.

@{music: volume=0.05, fade=2s}
@{pause: 30s}

When you are ready, begin to notice the sounds around you.

@{binaural: stop, fade_out=3s}
@{music: stop, fade_out=5s}
@{pause: 3s}

Open your eyes. Welcome back.
```

### 2.2 Directive Reference

| Directive | Parameters | Description |
|-----------|-----------|-------------|
| `@{language: <code>}` | ISO 639-1 code (`en`, `de`, ...) | Set the script language. Affects voice validation, pacing targets, and AI prompt selection. Defaults to `en` if omitted. See §9. |
| `@{pause: <duration>}` | `Ns` or `Nms` | Insert silence of the given duration. |
| `@{voice: <n>}` | Voice identifier string | Switch the TTS voice/model for subsequent text. |
| `@{voice: pitch=<N>st}` | Semitones (+/-) | Shift pitch relative to the voice default. |
| `@{voice: emotion=<tag>}` | `soothing`, `warm`, `whisper`, `confident`, ... | Emotional delivery hint (engine-dependent, see §5.2). |
| `@{speed: <factor>}` | Float (1.0 = normal) | Set speech rate. 0.8–0.9 is ideal for hypnosis. |
| `@{volume: <factor>}` | Float 0.0–1.0 | Set speech volume for subsequent paragraphs. |
| `@{music: start}` | `file`, `volume`, `fade_in` | Begin looping a background audio track. |
| `@{music: stop}` | `fade_out` | Stop the current background track. |
| `@{music: volume=<N>}` | `fade` (transition time) | Adjust music volume mid-session. |
| `@{binaural: frequency=<N>Hz}` | `carrier`, `volume`, `fade_in` | Start a programmatically generated binaural beat (see §8.3). |
| `@{binaural: stop}` | `fade_out` | Stop binaural tones. |
| `@{breath: <pattern>}` | e.g. `4-7-8` (inhale-hold-exhale) | Insert a guided breathing cycle with timed silence. |
| `@{section: <n>}` | Label string | Named marker — used for navigation, chapter metadata (§8.5), and GUI heatmaps. |
| `@{comment: <text>}` | Any text | Author note; ignored during rendering. |

### 2.3 Variable Injection

Scripts support **Mustache-style variables** for personalization:

```text
You are doing so well, {{name}}. Every breath takes you deeper.
```

Variables are resolved before parsing, from a dictionary supplied at render time:

```python
variables = {"name": "Sarah", "safe_place": "a sunlit meadow"}
rendered_text = inject_variables(raw_script, variables)
```

The GUI provides a "Session Variables" panel where the user fills in values before rendering. Undefined variables produce a **warning**, not an error — the raw `{{name}}` text remains so it's obvious in the output.

### 2.4 Parsing Rules

1. Blank lines separate **paragraphs** — each paragraph becomes one TTS generation unit.
2. Directives on their own line apply *before* the next paragraph.
3. Directives are cumulative; `@{voice: calm_female}` stays active until overridden.
4. Variable injection runs **before** directive parsing.
5. Unknown directives produce a **warning** (not an error) so scripts stay forward-compatible.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        HypnoAI Desktop / CLI                         │
└──────────┬──────────────────────────────────────────┬────────────────┘
           │                                          │
           ▼                                          ▼
┌─────────────────────┐                   ┌─────────────────────────┐
│   AI Script Studio   │                   │     Script Parser        │
│                       │                   │  .hypno → AST of Blocks │
│  LLM Provider ◄──────┤ generated script  │  (TextBlock, Pause,     │
│  (local or remote)   ├──────────────────►│   MusicCue, Binaural,   │
│  + Prompt Templates  │                   │   VoiceChange, ...)     │
└─────────────────────┘                   └──────────┬──────────────┘
                                                     │  List[Block]
                                                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                     Resource Orchestrator                           │
│  Manages model lifecycle: load/unload LLM & TTS to fit VRAM.      │
│  Ensures no two heavy models compete for GPU memory.               │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Render Pipeline                              │
│                                                                    │
│  ┌────────────────────┐   ┌────────────────────┐                  │
│  │  Paragraph Workers  │   │  Prosody Context    │                  │
│  │  TTS.generate()     │◄──│  (tail audio ref)   │                  │
│  │  → WAV chunk file   │   └────────────────────┘                  │
│  └────────────────────┘                                            │
│           ...                                                      │
│  (worker pool, writes chunks to temp dir)                          │
│                                                                    │
│  ┌────────────────────┐   ┌────────────────────┐                  │
│  │  Silence Generator  │   │  Binaural Generator │                  │
│  └────────────────────┘   └────────────────────┘                  │
│                                                                    │
│  ┌────────────────────┐                                            │
│  │  Music Mixer        │                                            │
│  │  Overlay + duck     │                                            │
│  └────────────────────┘                                            │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  paths to WAV chunk files
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Audio Assembler                              │
│  Concatenate + crossfade + normalize + limit → final file         │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
                           ▼
                     session.wav / .mp3 / .flac
                     (with chapter markers from @{section})
```

### 3.1 Core Components

| Component | Responsibility |
|-----------|---------------|
| **Script Parser** | Tokenize `.hypno` files into an ordered AST. Handles variable injection, validates syntax, emits warnings for unknown directives. |
| **Voice Registry** | Discovers available TTS models/voices, exposes metadata, handles parameter overrides. |
| **TTS Engine Adapter** | Abstraction over TTS backends. Accepts text + voice config + optional prosody context, returns audio. |
| **AI Script Studio** | Manages LLM providers and prompt templates for script generation (§7). |
| **Resource Orchestrator** | Manages GPU/CPU model lifecycle — loads, unloads, and sequences heavy models to prevent VRAM contention (§11). |
| **Render Pipeline** | Iterates over AST blocks, dispatches TTS jobs with prosody context, collects ordered WAV chunk file paths. |
| **Worker Pool** | Concurrent TTS generation with bounded parallelism (§6). |
| **Binaural Generator** | Programmatic tone synthesis for brainwave entrainment (§8.3). |
| **Music Mixer** | Loads background tracks, loops, applies fades and auto-ducking. |
| **Audio Assembler** | Concatenates chunks, crossfades, normalizes loudness, applies a final limiter, encodes output, embeds chapter markers. |

---

## 4. Model-Agnostic Design

HypnoAI is built on the principle that **no concrete model or provider should be hardwired** into any layer.

### 4.1 Abstraction Layers

```
┌─────────────────────────────────────────────────────────┐
│                  HypnoAI Application                     │
├──────────────────┬──────────────────┬───────────────────┤
│   TTSEngine      │   LLMProvider    │   AudioBackend    │
│   (Protocol)     │   (Protocol)     │   (Protocol)      │
├──────────────────┼──────────────────┼───────────────────┤
│ ● PiperEngine    │ ● OllamaProvider │ ● SoundfileIO     │
│ ● CoquiEngine    │ ● LlamaCppProv.  │ ● PydubIO         │
│ ● StyleTTSEngine │ ● OpenAIProvider │ ● FFmpegIO        │
│ ● KokoroEngine   │ ● AnthropicProv. │                   │
│ ● BarkEngine     │ ● MistralProv.   │                   │
│ ● (future...)    │ ● (future...)    │                   │
└──────────────────┴──────────────────┴───────────────────┘
```

### 4.2 TTS Engine Protocol

```python
from typing import Protocol
from pathlib import Path

class TTSEngine(Protocol):
    """Any local TTS model plugs in here."""

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
        prosody_reference: Path | None = None,  # for continuity
    ) -> AudioSegment: ...

    def supports_cloning(self) -> bool: ...

    def supports_prosody_reference(self) -> bool: ...

    def supports_emotions(self) -> list[str]: ...

    def clone_voice(self, name: str, reference_audio: Path) -> VoiceInfo: ...
```

Adding a new TTS model is a matter of writing one adapter class. The engine is selected at runtime via configuration or the GUI dropdown.

### 4.3 LLM Provider Protocol

```python
class LLMProvider(Protocol):
    """Any LLM — local or remote — plugs in here."""

    @property
    def name(self) -> str: ...

    @property
    def requires_gpu(self) -> bool: ...

    @property
    def vram_estimate_mb(self) -> int: ...

    def is_available(self) -> bool: ...

    def load(self) -> None: ...

    def unload(self) -> None: ...

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str: ...

    def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Iterator[str]: ...
```

### 4.4 Provider Registry

```python
engine_registry.register("piper", PiperEngine)
engine_registry.register("coqui", CoquiEngine)
llm_registry.register("ollama", OllamaProvider)
llm_registry.register("openai", OpenAIProvider)

# Runtime
tts = engine_registry.get(config.default_engine)
llm = llm_registry.get(config.ai.provider)
```

### 4.5 Why This Matters

| Benefit | Detail |
|---------|--------|
| **Future-proof** | New TTS models can be added without refactoring. |
| **User choice** | Users pick the quality/speed/privacy tradeoff that suits them. |
| **Testability** | Mock engines for unit tests — no GPU required. |
| **Graceful degradation** | Unavailable models are disabled in the GUI, not crash-inducing. |
| **Mixed workflows** | Piper for drafts (fast), XTTS for final render (quality). |
| **Resource awareness** | Each engine reports its VRAM needs, enabling the Resource Orchestrator (§11). |

---

## 5. TTS Backend — Local Model Selection

All TTS runs locally.

### 5.1 Recommended Models

| Model | Quality | Speed | VRAM | Prosody Ref | Emotions | Notes |
|-------|---------|-------|------|-------------|----------|-------|
| **Piper** | Good | Very fast (RT ×20+) | CPU only | No | No | ONNX-based, many voices. Ideal starting point. |
| **Coqui XTTS v2** | Excellent | Moderate (RT ×1–3) | ~4 GB | **Yes** | No | Voice cloning, supports prosody reference audio. |
| **Kokoro** | Excellent | Fast | ~2 GB | No | No | Lightweight, Apache 2.0 licensed. |
| **StyleTTS 2** | Excellent | Fast | ~3 GB | No | **Yes** | Style vectors for emotional control. |
| **F5-TTS** | Excellent | Moderate | ~4 GB | **Yes** | No | Strong zero-shot voice cloning. |
| **Bark** | Very good | Slow | ~6 GB | No | Partial | Supports non-speech sounds (sighs, breathing). |

### 5.2 Voice Customization & Emotion Tagging

| Parameter | Implementation |
|-----------|---------------|
| **Voice selection** | Choose from installed voices or provide a reference `.wav` for cloning. |
| **Speed** | Native TTS length regulator. |
| **Pitch shift** | Post-process with `librosa` or `rubberband`. |
| **Warmth / tone** | EQ post-processing (low-mid boost). |
| **Emotion tags** | For **StyleTTS 2**: map emotion names to style vectors. For **Bark**: select appropriate speaker presets. For engines without emotion support: apply heuristic post-processing (e.g. `whisper` → reduce volume + add subtle reverb, `confident` → slight speed increase + presence boost). |

Emotion support is **best-effort** — the `@{voice: emotion=...}` directive is a hint. Engines that don't support it degrade gracefully by ignoring the tag (with a logged info message).

---

## 6. Paragraph-Level Generation & Prosody Continuity

Generating the entire script in one TTS call is fragile. HypnoAI generates **one paragraph at a time** — but maintains **emotional and tonal continuity** across paragraph boundaries.

### 6.1 The Problem: "Frankenstein Audio"

TTS models reset their internal state between calls. In normal speech this is barely noticeable, but in hypnosis — where a slow, descending, calming tone is essential — a sudden prosody reset between paragraphs creates a jarring "restart" effect.

### 6.2 Solution: Prosody Reference Chain

For TTS engines that support it (XTTS v2, F5-TTS), HypnoAI passes the **tail end of the previous paragraph's audio** as a prosody reference for the next paragraph. This gives the model context to match the tone, pacing, and energy.

```
Paragraph 1 ──generate──► [audio₁] ──tail 3s──┐
                                                │ prosody_reference
Paragraph 2 ──generate──► [audio₂] ──tail 3s──┤
                                                │ prosody_reference
Paragraph 3 ──generate──► [audio₃]             │
                                                ...
```

```python
PROSODY_TAIL_SECONDS = 3.0

def render_with_prosody(blocks: list[TextBlock], engine: TTSEngine) -> list[Path]:
    """Sequential rendering with prosody chaining."""
    chunks = []
    previous_tail: Path | None = None

    for block in blocks:
        audio = engine.generate(
            text=block.text,
            voice=block.voice,
            speed=block.speed,
            prosody_reference=previous_tail,
        )
        chunk_path = save_to_temp(audio, block.index)
        chunks.append(chunk_path)

        # Extract the tail for the next paragraph's context
        if engine.supports_prosody_reference():
            previous_tail = extract_tail(chunk_path, PROSODY_TAIL_SECONDS)

    return chunks
```

### 6.3 Concurrency with Prosody

Prosody chaining is inherently **sequential** — paragraph N needs the tail of paragraph N-1. However, we can still exploit concurrency:

```
Strategy: Sequential prosody chain + parallel post-processing

Phase 1 (sequential):  Generate raw audio with prosody chain
  TTS(P1) → TTS(P2, ref=tail₁) → TTS(P3, ref=tail₂) → ...

Phase 2 (parallel):    Post-process chunks concurrently
  [pitch_shift(P1)] [eq(P2)] [pitch_shift(P3)] [eq(P4)]
       ↓                ↓           ↓               ↓

Phase 3 (sequential):  Assemble in order
```

For engines **without** prosody support (Piper, Kokoro), paragraphs can be generated fully in parallel since there's no state to chain:

```python
def render_pipeline(blocks: list[TextBlock], engine: TTSEngine) -> list[Path]:
    if engine.supports_prosody_reference():
        return render_with_prosody(blocks, engine)       # sequential TTS
    else:
        return render_parallel(blocks, engine)            # concurrent TTS
```

### 6.4 Concurrency Constraints

| Concern | Solution |
|---------|----------|
| **GPU contention** | `max_workers=1` for GPU models. CPU models like Piper allow `2–4`. |
| **Memory limits** | Each worker writes to a temp file (~10 MB for 30s). Bounded pool prevents OOM. |
| **Ordering** | Each job carries its `index`. Assembly sorts by index regardless of completion order. |
| **Failure isolation** | A failed paragraph inserts silence + logged warning rather than aborting the session. Retry once before falling back. |
| **Thread safety** | If the model isn't thread-safe, use `ProcessPoolExecutor` or serialize behind a lock. |

### 6.5 Caching

Already-generated paragraphs are cached by content hash. Re-rendering after a single edit only regenerates the changed chunk (and subsequent chunks if prosody chaining is active, since the reference changes).

```python
cache_key = hashlib.sha256(
    f"{text}|{voice}|{speed}|{pitch}|{prosody_ref_hash}".encode()
).hexdigest()
cache_path = CACHE_DIR / f"{cache_key}.wav"
```

> **Note:** With prosody chaining, editing paragraph 3 invalidates the cache for paragraphs 4, 5, 6, ... since their prosody reference changes. The GUI should warn the user: *"Editing this paragraph will re-render all following paragraphs."*

---

## 7. AI Script Generation

HypnoAI can optionally use an LLM to draft scripts from a brief user description. This is a **guided, template-driven workflow** — the LLM never runs unsupervised.

### 7.1 Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  AI Script Studio                          │
│                                                            │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────────┐ │
│  │   Prompt    │   │   LLM        │   │  Post-Processor   │ │
│  │   Builder   │──►│   Provider   │──►│  Syntax fix       │ │
│  │             │   │  (Protocol)  │   │  Safety scan      │ │
│  └──────┬─────┘   └──────────────┘   │  Structure check  │ │
│         │                             │  Duration estimate│ │
│   User intent                        └──────┬───────────┘ │
│   + template                                │              │
│   + variables                        Valid .hypno script   │
└──────────────────────────────────────────────────────────┘
```

### 7.2 Prompt Templates

Pre-built templates encode both **HypnoScript syntax** and **therapeutic semantics**:

```python
@dataclass
class PromptTemplate:
    id: str                         # e.g. "progressive_relaxation"
    name: str                       # "Progressive Muscle Relaxation"
    category: SessionCategory       # RELAXATION, SLEEP, FOCUS, HABIT, ...
    system_prompt: str              # detailed instructions for the LLM
    user_prompt_template: str       # template with {placeholders}
    default_variables: dict         # defaults for script {{variables}}
    validation_rules: list[str]     # post-generation checks
```

**Example system prompt (abbreviated):**

```text
You are a certified hypnotherapist writing scripts for HypnoAI.

OUTPUT FORMAT:
- Write in HypnoScript format. Use @{pause: Ns} for silence,
  @{voice: ...} for voice, @{speed: N} for pacing.
- Use {{name}} for the client's name (it will be injected at render time).
- Begin with an induction (3–5 min), main therapeutic content, and
  end with an emergence/awakening.

CLINICAL GUIDELINES:
- Use permissive language ("you may notice...", "allow yourself to...")
- Never use authoritarian commands
- Include deepening techniques (countdowns, staircase metaphors)
- Pace pauses generously — silence is therapeutic
- Use present tense and second person
- Target 60–80 words per minute for spoken sections

SAFETY:
- Never include content that could cause distress
- Always include a full awakening/emergence sequence
- Include grounding cues (awareness of body, surroundings)

TARGET: {session_type}, {duration} minutes, theme: {theme}
```

### 7.3 Available Templates

| Template | Category | Description |
|----------|----------|-------------|
| `progressive_relaxation` | Relaxation | Systematic body scan with tension release. |
| `sleep_induction` | Sleep | Guided countdown into deep sleep. |
| `focus_enhancement` | Focus | Visualization for concentration and clarity. |
| `habit_change` | Habit | Suggestion-based script for behavior change. |
| `anxiety_relief` | Anxiety | Breathing-focused calming session. |
| `confidence_boost` | Self-esteem | Positive suggestion and visualization. |
| `pain_management` | Pain | Glove anesthesia and dissociation techniques. |
| `custom` | General | Open-ended with user-provided description. |

### 7.4 LLM Provider Implementations

| Provider | Type | Privacy | Setup |
|----------|------|---------|-------|
| **Ollama** | Local | Full privacy | `ollama pull llama3.1`. Auto-detected. |
| **llama.cpp** | Local | Full privacy | Point to a GGUF file. |
| **OpenAI API** | Remote | Data sent to OpenAI | API key in config. |
| **Anthropic API** | Remote | Data sent to Anthropic | API key in config. |
| **Any OpenAI-compatible** | Either | Varies | Base URL + optional key. Covers LM Studio, vLLM, etc. |

### 7.5 Post-Processing & Validation

1. **Syntax check** — Parse the output; auto-fix common LLM mistakes (e.g. `@{pause 5s}` → `@{pause: 5s}`).
2. **Safety scan** — Flag authoritarian language, distressing imagery.
3. **Structure check** — Verify induction, body, and emergence sections exist.
4. **Duration estimate** — Word count + pauses; warn if far from target.
5. **Pacing analysis** — Flag paragraphs that exceed 80 WPM (hypnosis standard).

The user **always reviews and edits** before rendering. AI output is a draft, never a final product.

### 7.6 Generation Workflow (GUI)

```
 ┌─ Step 1 ──────────────────────┐
 │  Select session type & template│
 │  Set duration, theme           │
 │  Fill in variables (name, ...) │
 └──────────┬─────────────────────┘
            ▼
 ┌─ Step 2 ──────────────────────┐
 │  Review system prompt          │
 │  (advanced users can edit)     │
 │  Choose LLM provider           │
 │  Click "Generate"              │
 └──────────┬─────────────────────┘
            ▼
 ┌─ Step 3 ──────────────────────┐
 │  LLM streams into editor       │
 │  Post-processor validates       │
 │  Warnings shown inline         │
 └──────────┬─────────────────────┘
            ▼
 ┌─ Step 4 ──────────────────────┐
 │  User reviews & edits          │
 │  Adjusts pauses, wording       │
 │  Proceeds to render            │
 └────────────────────────────────┘
```

---

## 8. Music, Ambient & Binaural Layering

### 8.1 Music Timeline

Music cues create a **parallel timeline** mixed with the speech during assembly.

```
Speech:    [████ Text₁ ████]---silence---[████ Text₂ ████]---silence---[███ Text₃ ███]
Music:     ................[▓▓▓▓▓▓▓▓▓▓▓▓▓ ocean_waves.mp3 (looped) ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓]
Binaural:  ...[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 4Hz theta ░░░░░░░░░░░░░░░░░░░░░░░]
                                                                       ↑ fade out
```

### 8.2 Music Implementation

- **pydub** or **soundfile + numpy** for mixing.
- Background tracks are loaded, looped to fit session length, and volume-automated.
- **Auto-ducking**: reduce music volume during speech, restore during pauses.

### 8.3 Binaural & Isochronic Tone Generator

Instead of requiring pre-recorded brainwave files, HypnoAI **generates tones programmatically**:

```python
def generate_binaural(
    frequency: float,       # beat frequency (e.g. 4Hz for theta)
    carrier: float = 100.0, # carrier frequency in Hz
    duration_s: float = 60.0,
    sample_rate: int = 44100,
    volume: float = 0.1,
) -> np.ndarray:
    """Generate a stereo binaural beat.
    Left ear: carrier frequency
    Right ear: carrier + beat frequency
    The brain perceives the difference as the target frequency.
    """
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    left = np.sin(2 * np.pi * carrier * t) * volume
    right = np.sin(2 * np.pi * (carrier + frequency) * t) * volume
    return np.column_stack([left, right])
```

| Brainwave | Frequency | Use Case |
|-----------|-----------|----------|
| **Delta** | 0.5–4 Hz | Deep sleep, unconscious |
| **Theta** | 4–8 Hz | Hypnosis, meditation, deep relaxation |
| **Alpha** | 8–13 Hz | Calm focus, light meditation |
| **Beta** | 13–30 Hz | Alert, focused (awakening phase) |

> **Important:** Binaural beats require **stereo output** and **headphones**. The CLI/GUI should warn the user when binaural directives are present.

### 8.4 Supported Audio Formats

Input: `.mp3`, `.wav`, `.ogg`, `.flac` — Output: `.wav` (default), `.mp3`, `.flac`, `.ogg`

### 8.5 Automated Chapter Markers

The `@{section: ...}` directive is used to embed **chapter markers** into the final audio file:

- **MP3**: ID3 CHAP frames.
- **M4A/AAC**: iTunes-compatible chapter metadata.
- **WAV**: Cue points.

This allows users to skip to "Induction", "Deepening", or "Awakening" in their audio player or phone.

---

## 9. Language Support

HypnoAI supports **German and English** as first-class script languages from day one. The architecture is designed so that additional languages can be added with minimal effort — a new language requires a voice pack, a pacing profile, and optionally localized prompt templates, but no code changes. The GUI remains English-only.

### 9.1 Language Directive

Scripts declare their language explicitly. This enables voice validation, correct pacing thresholds, and language-appropriate AI generation.

```text
@{language: de}
@{voice: de_DE-thorsten-medium}
@{speed: 0.85}

Schließe deine Augen und nimm einen tiefen Atemzug.

@{pause: 5s}

Lass die Luft langsam durch den Mund ausströmen.
```

If `@{language}` is omitted, the parser defaults to `en`. The language directive is **session-wide** in v1. A future extension could allow per-paragraph language switching for multilingual sessions.

### 9.2 Voice–Language Validation

The linter cross-checks the declared language against the selected voice:

| Scenario | Behavior |
|----------|----------|
| `@{language: de}` + `@{voice: de_DE-thorsten-medium}` | ✅ Valid |
| `@{language: de}` + `@{voice: en_US-amy-medium}` | ⚠️ Warning: *"Voice 'en_US-amy-medium' is English but script language is German. This will produce poor pronunciation."* |
| `@{language: en}` + `@{voice: de_DE-thorsten-medium}` | ⚠️ Warning (same logic, reversed) |
| No `@{language}` directive | ℹ️ Info: *"No language set, defaulting to English. Add @{language: de} for German scripts."* |

The voice registry tags every voice with its language code. Validation is a simple prefix match (`de_DE-*` → `de`).

### 9.3 Language-Specific Pacing

Hypnotherapeutic pacing differs by language. German has longer compound words, so fewer words-per-minute produce the same speaking rate. The pacing heatmap (§13.3) and the linter adapt their thresholds based on the script language.

| Language | Ideal WPM | "Too Fast" Threshold | Rationale |
|----------|-----------|---------------------|-----------|
| **English** | 60–80 | > 90 | Standard for English-language hypnotherapy. |
| **German** | 50–70 | > 80 | Longer average word length (compound nouns, inflections). |

These thresholds are stored in a **language profile** config, making it trivial to add new languages:

```toml
# languages/de.toml
[pacing]
ideal_wpm_min = 50
ideal_wpm_max = 70
too_fast_wpm = 80

[meta]
name = "German"
code = "de"
voice_prefix = "de_DE"
```

```toml
# languages/en.toml
[pacing]
ideal_wpm_min = 60
ideal_wpm_max = 80
too_fast_wpm = 90

[meta]
name = "English"
code = "en"
voice_prefix = "en_US"
```

### 9.4 AI Prompt Templates per Language

Each prompt template (§7.2) can have **language-specific variants**. This is essential because good hypnotherapy scripts are not translations — they require culturally and linguistically native phrasing.

```
engine/hypnoai/ai/templates/
├── progressive_relaxation/
│   ├── en.toml          # English system prompt + user prompt
│   └── de.toml          # German system prompt + user prompt
├── sleep_induction/
│   ├── en.toml
│   └── de.toml
└── ...
```

**German-specific prompt adjustments:**
- Use "Du" (informal) rather than "Sie" (formal) — standard in therapeutic context.
- Use permissive phrasing native to German: *"Du darfst jetzt loslassen..."*, *"Erlaube dir..."*, *"Vielleicht bemerkst du..."* — not literal translations of English patterns.
- Adapt metaphors to German-speaking cultural context where appropriate.
- Instruct the LLM to target 50–70 WPM for pacing.

If a template has no variant for the requested language, HypnoAI falls back to the English template with an added instruction: *"Write the script in {language}."* This produces acceptable results but the native templates are preferred.

### 9.5 Voice Availability per Language

The Model Manager (§14) filters available voice packs by language. On first launch, it recommends voices matching the system locale:

| System Locale | Recommended Voice | Engine |
|---------------|------------------|--------|
| `en_*` | en_US-amy-medium | Piper |
| `de_*` | de_DE-thorsten-medium | Piper |

For Coqui XTTS v2 (voice cloning), the cloned voice inherits the language of the reference audio. The user must tag the language when cloning:

```bash
hypnoai voices --clone mein_therapeut --reference sample.wav --engine coqui --language de
```

### 9.6 Adding a New Language (Future)

Adding a third language (e.g. French, Spanish) requires:

1. **Voice pack** — download or clone a voice for that language (via Model Manager).
2. **Language profile** — create `languages/fr.toml` with pacing thresholds.
3. **Prompt templates** (optional) — add `fr.toml` variants to template directories for native-quality AI generation. Without these, the English template with a language instruction serves as fallback.
4. **No code changes** — the parser, renderer, and GUI read language profiles dynamically.

This makes language expansion a content task, not an engineering task.

---

## 10. Audio Post-Processing

| Stage | Purpose | Library |
|-------|---------|---------|
| **Crossfade** | Smooth transitions between chunks (20–50ms). | numpy / pydub |
| **De-essing** | Optional sibilance reduction. | scipy |
| **EQ / Warmth** | Gentle low-mid boost for soothing tone. | scipy.signal |
| **Loudness normalization** | Target -16 LUFS. | pyloudnorm |
| **Compression** | Light dynamic range compression. | numpy / custom |
| **Limiter** | **Brick-wall limiter at -1 dBFS.** Prevents digital clipping when music, binaural tones, and speech are mixed. This is the last stage before encoding. | numpy / custom |
| **Final encoding** | Export to target format + chapter markers. | soundfile / pydub / mutagen |

> **Why a limiter?** Simply adding waveforms (speech + music + binaural) can exceed 0 dBFS and produce digital clipping artifacts. A brick-wall limiter at -1 dBFS catches any peaks the normalizer and compressor missed. This is non-negotiable in the audio chain.

---

## 11. Resource Orchestrator

Consumer hardware (8 GB VRAM GPU, 16 GB RAM) cannot run a large LLM and a large TTS model simultaneously. The Resource Orchestrator prevents contention.

### 11.1 Problem

| Scenario | VRAM Needed | 8 GB GPU Result |
|----------|-------------|-----------------|
| Ollama (Llama 3.1 8B Q4) | ~5 GB | ✅ fits |
| Coqui XTTS v2 | ~4 GB | ✅ fits |
| Both simultaneously | ~9 GB | ❌ OOM / disk swap |

### 11.2 Solution: Model Lifecycle Manager

```python
class ResourceOrchestrator:
    """Ensures only one GPU-heavy model is loaded at a time."""

    def __init__(self, vram_budget_mb: int = 0):
        self.vram_budget = vram_budget_mb or detect_available_vram()
        self.loaded_models: dict[str, ModelHandle] = {}

    def request_model(self, model: TTSEngine | LLMProvider) -> None:
        """Load a model, unloading others if needed to fit VRAM budget."""
        needed = model.vram_estimate_mb
        available = self.vram_budget - self._currently_used()

        if needed > available:
            self._evict_until_free(needed)

        model.load()
        self.loaded_models[model.name] = ModelHandle(model)

    def release_model(self, name: str) -> None:
        if name in self.loaded_models:
            self.loaded_models[name].model.unload()
            del self.loaded_models[name]

    def _evict_until_free(self, needed_mb: int) -> None:
        """Unload models LRU-first until enough VRAM is free."""
        by_lru = sorted(self.loaded_models.values(), key=lambda h: h.last_used)
        for handle in by_lru:
            if self._currently_used() + needed_mb <= self.vram_budget:
                break
            handle.model.unload()
            del self.loaded_models[handle.model.name]
```

### 11.3 Workflow Integration

```
User clicks "Generate Script" (AI)
  → Orchestrator loads Ollama LLM
  → LLM generates script
  → Orchestrator unloads LLM

User clicks "Render" (TTS)
  → Orchestrator loads XTTS
  → TTS renders all paragraphs
  → Model stays loaded for previews

User clicks "Generate Script" again
  → Orchestrator unloads XTTS, loads LLM
```

The GUI shows a **resource indicator** (e.g. "VRAM: 3.8 / 8.0 GB") so the user understands why model switches take a moment.

### 11.4 CPU-Only Mode

If no GPU is detected (or the user opts out), the orchestrator selects Piper (CPU-only) as the default TTS engine, routes LLM to a CPU-optimized Ollama model or a remote API, and manages RAM instead of VRAM.

---

## 12. CLI Interface

```bash
# Voices
hypnoai voices --list
hypnoai voices --clone my_therapist --reference sample.wav --engine coqui

# Model management (always available, not just during setup)
hypnoai models list                          # show installed engines + voices
hypnoai models list --available              # show downloadable models
hypnoai models download piper               # download a TTS engine
hypnoai models download en_US-amy-medium    # download a specific voice pack
hypnoai models remove coqui-xtts-v2         # remove an engine to free disk space
hypnoai models info piper                   # show size, license, capabilities

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
                 --language en \
                 --var name=Sarah \
                 --provider ollama \
                 -o session.hypno

# Generate a German script
hypnoai generate --template sleep_induction \
                 --duration 20 --theme "Waldspaziergang" \
                 --language de \
                 --var name=Anna \
                 --provider ollama \
                 -o schlaf_session.hypno

# System info
hypnoai system --info          # show GPU, VRAM, installed models, disk usage
```

---

## 13. Desktop GUI

### 14.1 Technology Choice: Tauri + React

| Consideration | Decision | Rationale |
|---------------|----------|-----------|
| **Framework** | **Tauri v2** | Rust-based, ~5 MB shell. Native webview. |
| **Frontend** | **React + TypeScript** | Rich editor components. |
| **Styling** | **Tailwind CSS** | Rapid, consistent design. |
| **Backend bridge** | **Tauri IPC → Python sidecar** | JSON-RPC over stdin/stdout. Audio data passed as **file paths**, never raw bytes (see §13.4). |

### 14.2 Screen Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  HypnoAI                                    [Engine: Piper]  ─  □  ✕   │
├───────────────┬──────────────────────────────────────────────────────────┤
│               │                                                          │
│  📁 Sessions  │   ┌─── Script Editor ────────────────────────────────┐   │
│               │   │                                                   │   │
│  ▸ My Scripts │   │  @{voice: calm_female}                           │   │
│    Deep Relax │   │  @{speed: 0.85}            ┌─ Pacing Heatmap ─┐ │   │
│    Sleep      │   │                             │ ▓▓▓░░▓▓░░░▓▓▓▓░ │ │   │
│    Morning    │   │  Close your eyes and take   │ ok  fast ok  ok  │ │   │
│               │   │  a deep breath, {{name}}.   └──────────────────┘ │   │
│  ▸ AI Drafts  │   │                                                   │   │
│    Draft 1    │   │  @{pause: 4s}          ← syntax highlighted       │   │
│               │   │                                                   │   │
│  ▸ Templates  │   │  Now slowly release...                            │   │
│               │   │                                                   │   │
│  ─────────    │   └───────────────────────────────────────────────────┘   │
│  📋 Variables │                                                          │
│  name: Sarah  │   ┌─── Voice & Render Settings ──────────────────────┐   │
│  safe_place:  │   │                                                   │   │
│   meadow      │   │  Engine: [Piper ▾]    Voice: [amy-medium ▾]      │   │
│               │   │  Speed:  [===●===]    Pitch: [===●===]           │   │
│  ─────────    │   │  Emotion: [soothing ▾]                            │   │
│  📦 Models    │   │                                                   │   │
│  Piper ✅     │   │  Output: session.wav   [▶ Preview]  [⏺ Render]   │   │
│  XTTS  ✅     │   │                                                   │   │
│  [Manage...]  │   │  ████████████░░░░░░░░  45% — Paragraph 5/11      │   │
│               │   └───────────────────────────────────────────────────┘   │
│               │                                                          │
│               │   ┌─── Audio Timeline ───────────────────────────────┐   │
│               │   │  ▶ ■  00:00 ━━━━━━●━━━━━━━━━━━━━━━━━━━ 12:30    │   │
│               │   │  ┊▁▂▃▅▇▅▃▂▁┊___┊▁▃▅▇▅▃▁┊_________┊▁▂▅▇▃▁┊     │   │
│               │   │  Speech ▓▓▓  Silence ___  Music ░░░  🎧 Binaural │   │
│               │   │  [Intro]     [Body Scan]   [Deepening] [Awaken]  │   │
│               │   └───────────────────────────────────────────────────┘   │
└───────────────┴──────────────────────────────────────────────────────────┘
```

### 14.3 Key GUI Panels

**① Sidebar — Session Manager, Variables & Models**
- Tree view of saved scripts, AI drafts, and templates.
- **Variables panel**: key-value fields for `{{name}}`, `{{safe_place}}`, etc. Automatically populated from the script's variable references.
- **Models panel**: quick overview of installed engines and their status. "Manage..." opens the full Model Manager (§14.6) for downloading, removing, and updating engines and voice packs.
- Create, duplicate, import/export `.hypno` files.

**② Script Editor with Pacing Heatmap**
- Full-featured editor with HypnoScript syntax highlighting.
- Directives rendered as colored inline blocks.
- **Pacing heatmap** (toggle-able): a gutter overlay that color-codes each paragraph by words-per-minute. Green = 60–80 WPM (ideal for hypnosis), yellow = borderline, red = too fast. Calculated from estimated speech duration at the current speed setting.
- Inline linter warnings (red underline).
- Click paragraph number to preview that paragraph's audio.
- Autocomplete for directives and voice identifiers.
- "Re-generate this section" context menu (sends section to AI).
- **"Verify Paragraph"** button: re-renders a single paragraph to check for TTS hallucinations (repeated words, gibberish). Quick QA without re-rendering the entire session.

**③ AI Script Assistant (slide-out panel)**
- Session type selector, duration slider, theme input.
- LLM provider selector (only shows available/configured providers).
- "Generate" streams output into editor.
- "Regenerate section" for partial rewrites.

**④ Voice & Render Settings**
- Engine/voice dropdowns populated from Voice Registry.
- Speed, pitch, emotion controls.
- "Preview" (current paragraph) and "Render" (full session).
- Progress bar with paragraph granularity + prosody chain indicator.

**⑤ Audio Timeline**
- Waveform visualization of rendered session.
- Color-coded: speech (solid), silence (flat), music (shaded), binaural (dotted).
- **Chapter markers** from `@{section}` shown as labeled dividers.
- Click-to-jump: waveform position highlights corresponding paragraph in editor.
- Playback controls.

**⑥ System Status (title bar)**
- Shows currently loaded TTS engine and disk usage for models.
- Clicking opens the Model Manager panel.

### 14.4 Tauri ↔ Python Bridge

The Python engine runs as a **managed sidecar process** communicating via JSON-RPC over stdin/stdout.

**Critical design decision: audio data is exchanged as file paths, never as raw bytes or base64.** The Python sidecar writes WAV chunks to a shared temp directory; Tauri reads them directly. This avoids the base64 encoding bottleneck and UI lag.

```
┌──────────────┐  JSON-RPC (stdin/stdout)  ┌─────────────────────┐
│   Tauri       │ ◄──────────────────────► │  Python sidecar      │
│   (Rust +     │   commands → responses    │                      │
│    React)     │                           │  TTS, Parser, AI,    │
│               │   audio via shared        │  Assembler, Resource │
│   reads WAV ◄─┤── temp directory ────────┤── writes WAV chunks  │
│   files       │   /tmp/hypnoai/chunks/    │                      │
└──────────────┘                           └─────────────────────┘
```

See §18 for the full JSON-RPC schema.

### 14.5 Theming

Dark theme by default (deep blues, soft grays — appropriate for the subject). Light theme available. Muted, warm colors throughout. No harsh whites or saturated accents.

---

## 14. Packaging & Distribution

### 14.1 The Size Problem

Tauri is ~5 MB, but a functional HypnoAI installation includes Python, ML runtimes, and model weights — easily multi-gigabyte. Bundling everything into one installer is impractical and intimidating.

### 14.2 Solution: Bootstrap Installer + Permanent Model Manager

The key insight is that model management isn't a one-time setup task — it's an ongoing workflow. Users add new voices, try different engines, remove models to free disk space. So the Model Manager is a **first-class, always-accessible feature** in both the CLI and the GUI.

**First launch** uses the same Model Manager, just wrapped in a guided wizard that recommends a starting configuration.

```
┌─ Phase 1: Tiny Installer (~15 MB) ─────────────────────────────────┐
│  • Tauri shell + React frontend                                     │
│  • Bundled Python runtime (embedded, e.g. python-build-standalone)  │
│  • Core Python packages (parser, CLI, config)                       │
│  • No TTS models yet — just the app shell                          │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ First Launch
                                   ▼
┌─ Phase 2: First-Launch Wizard (uses Model Manager internally) ──────┐
│                                                                      │
│  "Welcome to HypnoAI! Let's set up your first audio engine."       │
│                                                                      │
│  ┌──────────────────────────────────────────────┐                   │
│  │  ☑ Piper (CPU, ~80 MB)         Recommended   │                   │
│  │  ☐ Coqui XTTS v2 (GPU, ~1.8 GB)             │                   │
│  │  ☐ Kokoro (GPU, ~500 MB)                     │                   │
│  └──────────────────────────────────────────────┘                   │
│                                                                      │
│  Voice Packs:                                                        │
│  ☑ English - Amy (medium quality, 25 MB)                            │
│  ☐ English - Lessac (high quality, 75 MB)                           │
│                                                                      │
│  [Download & Install]    Estimated: 105 MB                          │
│  ████████████████░░░░░░  67% — Downloading Piper...                 │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 14.3 Model Manager — CLI

The CLI provides full model management as a permanent subcommand:

```bash
hypnoai models list                          # installed engines + voice packs
hypnoai models list --available              # browsable catalog of downloadable models
hypnoai models download piper               # download engine + default voice
hypnoai models download en_US-amy-medium    # download a specific voice pack
hypnoai models remove coqui-xtts-v2         # remove engine to free disk space
hypnoai models info piper                   # size, license, capabilities, voices
hypnoai models update                       # check for updates to installed models
```

### 14.4 Model Manager — GUI

In the desktop app, the Model Manager is accessible at any time via the sidebar or settings:

```
┌─── Model Manager ────────────────────────────────────────────────┐
│                                                                    │
│  Installed                                          Disk: 2.1 GB  │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ ✅ Piper          CPU    80 MB   3 voices    [Manage] [🗑️]  │ │
│  │ ✅ Coqui XTTS v2  GPU   1.8 GB  1 cloned    [Manage] [🗑️]  │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Available                                                         │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ ⬇️ Kokoro         GPU   500 MB  Apache 2.0   [Download]     │ │
│  │ ⬇️ StyleTTS 2     GPU   1.2 GB  MIT          [Download]     │ │
│  │ ⬇️ Bark           GPU   6.0 GB  MIT          [Download]     │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Voice Packs for Piper:                                            │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ ✅ en_US - Amy (medium)     25 MB                            │ │
│  │ ⬇️ en_US - Lessac (high)   75 MB       [Download]           │ │
│  │ ⬇️ de_DE - Thorsten (med)  30 MB       [Download]           │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ████████████████░░░░░░  67% — Downloading Lessac voice...        │
└──────────────────────────────────────────────────────────────────┘
```

The Model Manager panel also shows license info, disk usage per model, and warns before deleting a model that's referenced in saved scripts.

### 14.5 Update Strategy

- **App shell**: Auto-update via Tauri's built-in updater.
- **Python engine**: Versioned separately; updated via the sidecar package manager.
- **Models**: Downloaded on demand; version-pinned in config. `hypnoai models update` checks for newer versions.

### 14.6 Licensing Awareness

The Model Manager displays license information for each model. Only models with permissive licenses (Apache 2.0, MIT) are shown by default. Research-only or restricted models require the user to acknowledge the license before downloading.

---

## 15. Project Structure

```
hypnoai/
├── pyproject.toml
├── README.md
│
├── engine/                         # Python backend (CLI + sidecar)
│   ├── hypnoai/
│   │   ├── __init__.py
│   │   ├── cli.py                  # Typer CLI
│   │   ├── sidecar.py              # JSON-RPC server for Tauri bridge
│   │   ├── parser/
│   │   │   ├── lexer.py
│   │   │   ├── ast_nodes.py
│   │   │   ├── parser.py
│   │   │   └── variables.py        # {{variable}} injection
│   │   ├── tts/
│   │   │   ├── base.py             # TTSEngine protocol
│   │   │   ├── piper_engine.py
│   │   │   ├── coqui_engine.py
│   │   │   ├── styletts_engine.py
│   │   │   └── voice_registry.py
│   │   ├── ai/
│   │   │   ├── base.py             # LLMProvider protocol
│   │   │   ├── ollama_provider.py
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   ├── templates/
│   │   │   │   ├── progressive_relaxation/
│   │   │   │   │   ├── en.toml     # English prompt variant
│   │   │   │   │   └── de.toml     # German prompt variant
│   │   │   │   ├── sleep_induction/
│   │   │   │   │   ├── en.toml
│   │   │   │   │   └── de.toml
│   │   │   │   └── ...
│   │   │   └── post_processor.py
│   │   ├── render/
│   │   │   ├── pipeline.py         # Prosody-aware rendering
│   │   │   ├── cache.py
│   │   │   ├── music_mixer.py
│   │   │   └── binaural.py         # Tone generator
│   │   ├── audio/
│   │   │   ├── assembler.py
│   │   │   ├── effects.py
│   │   │   ├── normalize.py
│   │   │   ├── limiter.py          # Brick-wall limiter
│   │   │   ├── chapters.py         # Chapter marker embedding
│   │   │   └── encoder.py
│   │   ├── resources/
│   │   │   ├── orchestrator.py     # VRAM/RAM model manager
│   │   │   └── model_downloader.py
│   │   └── config.py
│   ├── languages/                  # Language profiles (pacing, metadata)
│   │   ├── en.toml
│   │   └── de.toml
│   ├── voices/
│   ├── cache/
│   └── tests/
│
├── desktop/                        # Tauri + React frontend
│   ├── src-tauri/
│   │   ├── Cargo.toml
│   │   ├── src/
│   │   │   ├── main.rs
│   │   │   ├── bridge.rs           # Sidecar management + JSON-RPC
│   │   │   └── commands.rs
│   │   └── tauri.conf.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Editor.tsx          # HypnoScript editor + heatmap
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Variables.tsx       # Session variable inputs
│   │   │   ├── VoiceSettings.tsx
│   │   │   ├── Timeline.tsx        # Waveform + chapters
│   │   │   ├── AIAssistant.tsx
│   │   │   ├── ModelManager.tsx    # Browse, download, remove models (always accessible)
│   │   │   ├── StatusBar.tsx       # Engine + system status indicator
│   │   │   └── SetupWizard.tsx     # First-launch guide (wraps ModelManager)
│   │   ├── hooks/
│   │   │   ├── useBridge.ts
│   │   │   ├── useAudioPlayer.ts
│   │   │   └── useModels.ts
│   │   └── styles/
│   ├── package.json
│   └── tailwind.config.ts
│
└── examples/
    ├── en/
    │   ├── deep_relaxation.hypno
    │   ├── sleep_induction.hypno
    │   └── morning_meditation.hypno
    └── de/
        ├── tiefenentspannung.hypno
        ├── schlaf_induktion.hypno
        └── morgen_meditation.hypno
```

---

## 16. Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Python engine** | Python 3.11+ | Best TTS/ML ecosystem. |
| **CLI** | Typer | Modern, type-hinted CLI. |
| **Desktop shell** | Tauri v2 (Rust) | Small binary, native feel. |
| **Frontend** | React + TypeScript + Tailwind | Rich editor, rapid development. |
| **TTS (fast)** | Piper | CPU-only, extremely fast. |
| **TTS (quality)** | Coqui XTTS v2 | Best local voice cloning + prosody reference. |
| **TTS (emotion)** | StyleTTS 2 | Style vectors for emotional control. |
| **LLM (local)** | Ollama | Easy model management. |
| **LLM (remote)** | OpenAI / Anthropic API | Optional, best script quality. |
| **Audio I/O** | soundfile + numpy | Reliable, low-level. |
| **Mixing** | pydub | Overlay, fade, conversion. |
| **Pitch shift** | librosa / pyrubberband | High quality. |
| **Binaural** | numpy (signal gen) | Zero dependencies. |
| **Normalization** | pyloudnorm | ITU-R BS.1770. |
| **Chapter markers** | mutagen | ID3/M4A metadata. |
| **Caching** | File-based (SHA-256) | Simple, no DB. |
| **Config** | TOML | Human-readable. |
| **Testing** | pytest + Vitest | Backend + frontend. |

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
max_workers_cpu = 3             # for CPU-only engines (Piper)
max_workers_gpu = 1             # for GPU engines (serialized)
retry_on_failure = true
crossfade_ms = 30
paragraph_gap_ms = 200
prosody_tail_seconds = 3.0      # audio context for prosody chaining

[audio]
sample_rate = 22050
loudness_target_lufs = -16.0
apply_warmth_eq = true
apply_compression = false
limiter_ceiling_dbfs = -1.0     # brick-wall limiter threshold

[music]
auto_duck = true
duck_amount_db = -6
duck_attack_ms = 300
duck_release_ms = 500

[binaural]
default_carrier_hz = 100.0
stereo_warning = true           # warn user to use headphones

[ai]
provider = "ollama"
ollama_model = "llama3.1"
ollama_url = "http://localhost:11434"
# openai_api_key = "sk-..."
# anthropic_api_key = "sk-ant-..."
default_template = "progressive_relaxation"
default_duration_minutes = 15
default_language = "en"         # language for AI-generated scripts

[languages]
# Language profiles are loaded from languages/*.toml
# Built-in: en, de. Add more by creating new profile files.
profiles_dir = "./languages"

[resources]
vram_budget_mb = 0              # 0 = auto-detect
gpu_enabled = true
model_dir = "./models"

[gui]
theme = "dark"                  # dark | light
show_pacing_heatmap = true
pacing_target_wpm = 70          # ideal words-per-minute for hypnosis
```

---

## 18. Tauri ↔ Python Bridge — JSON-RPC Schema

All communication between Tauri and the Python sidecar uses JSON-RPC 2.0 over stdin/stdout. Audio data is **never** sent over the bridge — only file paths.

### 18.1 Shared Temp Directory

On startup, the sidecar creates a session-specific temp directory:

```
/tmp/hypnoai-{session_id}/
├── chunks/          # paragraph WAV files
│   ├── 000.wav
│   ├── 001.wav
│   └── ...
├── preview.wav      # single paragraph preview
└── output/          # final rendered file
    └── session.wav
```

Tauri has read access to this directory. The sidecar returns paths; Tauri reads the files directly for playback and waveform rendering.

### 18.2 RPC Methods

**Script & Rendering:**

```jsonc
// Parse and validate a script
{ "method": "script.lint", "params": { "path": "/path/to/session.hypno" } }
→ { "result": { "valid": true, "warnings": [...], "paragraph_count": 11,
                 "estimated_duration_s": 780, "variables": ["name", "safe_place"],
                 "pacing": [{ "paragraph": 0, "wpm": 72 }, ...] } }

// Render full session
{ "method": "render.start", "params": {
    "script_path": "/path/to/session.hypno",
    "output_path": "/tmp/hypnoai-xxx/output/session.wav",
    "variables": { "name": "Sarah" },
    "voice": "en_US-amy-medium",
    "engine": "piper",
    "format": "wav"
}}
→ { "result": { "job_id": "abc123" } }

// Poll render progress
{ "method": "render.progress", "params": { "job_id": "abc123" } }
→ { "result": { "state": "rendering", "current_paragraph": 5, "total": 11,
                 "chunk_paths": ["/tmp/.../000.wav", ...],
                 "elapsed_s": 12.3 } }

// Cancel render
{ "method": "render.cancel", "params": { "job_id": "abc123" } }

// Preview single paragraph
{ "method": "render.preview", "params": {
    "text": "Close your eyes and take a deep breath, Sarah.",
    "voice": "en_US-amy-medium", "engine": "piper", "speed": 0.85
}}
→ { "result": { "audio_path": "/tmp/hypnoai-xxx/preview.wav", "duration_s": 4.2 } }
```

**Voice Management:**

```jsonc
{ "method": "voices.list", "params": { "engine": "piper" } }
→ { "result": { "voices": [
    { "id": "en_US-amy-medium", "name": "Amy", "language": "en_US",
      "quality": "medium", "sample_rate": 22050 }, ...
] } }

{ "method": "voices.clone", "params": {
    "name": "my_therapist", "reference_path": "/path/to/sample.wav", "engine": "coqui"
}}
→ { "result": { "voice_id": "cloned-my_therapist", "status": "ready" } }
```

**AI Script Generation:**

```jsonc
{ "method": "ai.generate", "params": {
    "template": "progressive_relaxation",
    "language": "de",
    "variables": { "duration": 15, "theme": "Waldspaziergang", "name": "Anna" },
    "provider": "ollama"
}}
→ (streamed) { "result": { "chunk": "@{voice: calm_female}\n@{speed: 0.85}\n\n" } }
→ (streamed) { "result": { "chunk": "Close your eyes..." } }
→ (final)    { "result": { "done": true, "validation": { "warnings": [...] } } }
```

**Model Management:**

```jsonc
{ "method": "models.status" }
→ { "result": { "gpu_available": true, "vram_total_mb": 8192,
                 "loaded_engine": "piper",
                 "disk_used_mb": 2100 } }

{ "method": "models.list" }
→ { "result": { "installed": [
    { "name": "piper", "type": "tts", "size_mb": 80, "loaded": true,
      "voices": ["en_US-amy-medium"], "license": "MIT" },
    { "name": "coqui-xtts-v2", "type": "tts", "size_mb": 1800, "loaded": false,
      "voices": ["cloned-my_therapist"], "license": "CPML" }
], "available_for_download": [
    { "name": "kokoro", "type": "tts", "size_mb": 500, "license": "Apache-2.0",
      "requires_gpu": true }
] } }

{ "method": "models.download", "params": { "model": "kokoro" } }
→ { "result": { "job_id": "dl-456", "size_mb": 500 } }

{ "method": "models.download.progress", "params": { "job_id": "dl-456" } }
→ { "result": { "state": "downloading", "progress_pct": 67, "speed_mbps": 12.3 } }

{ "method": "models.remove", "params": { "model": "coqui-xtts-v2" } }
→ { "result": { "freed_mb": 1800 } }
```

### 18.3 Error Handling

All errors use standard JSON-RPC error codes plus custom codes:

| Code | Meaning |
|------|---------|
| -32600 | Invalid request |
| -32601 | Method not found |
| -32602 | Invalid params |
| **-1001** | Model not installed — suggest `hypnoai models download <name>` |
| **-1002** | Model download failed — network error or disk space |
| **-1003** | Render failed — includes paragraph index and retry suggestion |
| **-1004** | LLM provider unavailable |
| **-1005** | Script validation error — includes line number and message |
| **-1006** | GPU out of memory — suggest switching to a CPU-based engine |

The Tauri frontend maps these to user-friendly error messages and suggested actions (e.g. "Piper is not installed yet. Download now?" → one-click download).

---

## 19. Example Session Scripts

### 19.1 English Example — Progressive Relaxation

```text
@{comment: Progressive Muscle Relaxation — 15 min session}
@{language: en}
@{voice: en_US-amy-medium}
@{speed: 0.85}
@{section: Introduction}

Welcome to this guided relaxation session, {{name}}.
Find a comfortable position, and when you are ready, gently close your eyes.

@{pause: 5s}

Take a deep breath in through your nose.

@{breath: 4-4-6}

@{music: start, file="ambient_pad.wav", volume=0.12, fade_in=4s}
@{binaural: frequency=6Hz, carrier=100Hz, volume=0.06, fade_in=5s}
@{section: Body Scan}

Now bring your attention to your feet, {{name}}.
Notice any tension you might be holding there.

@{pause: 4s}

As you breathe out, let that tension dissolve.
Feel your feet becoming heavy and warm.

@{pause: 6s}
@{voice: pitch=-1st, emotion=soothing}

Moving upward now, to your calves and your shins.
Allow these muscles to soften and release.

@{pause: 8s}

@{section: Deepening}
@{music: volume=0.06, fade=3s}
@{binaural: frequency=4Hz, fade=5s}

With each breath, you drift deeper.
Every sound you hear only takes you further into relaxation.

@{pause: 15s}

@{section: Awakening}
@{music: volume=0.15, fade=2s}
@{binaural: frequency=10Hz, fade=8s}
@{speed: 0.95}

In a moment, I will count from one to five.
With each number, you will feel more alert and refreshed.

@{pause: 3s}

One. Becoming aware of your surroundings.
@{pause: 3s}
Two. Feeling energy returning to your body.
@{pause: 3s}
Three. Taking a deep, refreshing breath.
@{pause: 3s}
Four. Almost fully awake now.
@{pause: 3s}
Five. Eyes open. Fully alert. Feeling wonderful.

@{binaural: stop, fade_out=3s}
@{music: stop, fade_out=4s}
@{pause: 2s}

Welcome back, {{name}}. Take a moment before you continue with your day.
```

### 19.2 German Example — Sleep Induction

```text
@{comment: Schlaf-Induktion — 10 Minuten}
@{language: de}
@{voice: de_DE-thorsten-medium}
@{speed: 0.80}
@{section: Einleitung}

Willkommen zu deiner Schlaf-Session, {{name}}.
Mach es dir bequem und schließe sanft deine Augen.

@{pause: 5s}

Nimm einen tiefen Atemzug durch die Nase ein.

@{breath: 4-4-6}

@{music: start, file="nacht_ambient.wav", volume=0.10, fade_in=5s}
@{binaural: frequency=3Hz, carrier=80Hz, volume=0.05, fade_in=6s}
@{section: Vertiefung}

Mit jedem Atemzug sinkst du ein kleines Stück tiefer.
Du darfst jetzt loslassen, {{name}}. Alles ist gut.

@{pause: 6s}
@{voice: pitch=-1st, emotion=soothing}

Stell dir vor, du liegst auf einer weichen Wiese.
Über dir ein klarer Nachthimmel, voller Sterne.

@{pause: 8s}

Die Luft ist angenehm kühl und du spürst,
wie dein Körper schwerer und schwerer wird.

@{pause: 10s}

@{section: Einschlafen}
@{music: volume=0.04, fade=4s}
@{binaural: frequency=1.5Hz, fade=8s}
@{speed: 0.75}

Zehn... tiefer und tiefer.
@{pause: 4s}
Neun... alles loslassen.
@{pause: 4s}
Acht... schwerer und ruhiger.
@{pause: 5s}
Sieben... nichts ist wichtig.
@{pause: 5s}
Sechs... nur noch Stille.
@{pause: 6s}
Fünf...
@{pause: 6s}
Vier...
@{pause: 7s}
Drei...
@{pause: 8s}
Zwei...
@{pause: 10s}
Eins...

@{pause: 30s}

@{binaural: stop, fade_out=10s}
@{music: stop, fade_out=15s}
```

---

## 20. Implementation Roadmap

### Phase 1 — Engine MVP (Weeks 1–3)
- HypnoScript parser (text + `@{pause}` + `@{voice}` + `@{speed}` + `@{language}` + `{{variables}}`).
- **Language profiles** for English and German (pacing thresholds, voice validation).
- Piper TTS integration with voice selection (English + German voice packs).
- Sequential paragraph rendering.
- Simple concatenation with silence insertion.
- CLI: `render`, `voices --list`, `lint` (with language–voice mismatch warnings).

### Phase 2 — Quality & Concurrency (Weeks 4–6)
- Concurrent paragraph generation with worker pool.
- Paragraph-level caching.
- Audio post-processing chain (crossfade, normalization, warmth EQ, **limiter**).
- Coqui XTTS v2 integration + voice cloning.
- Pitch shifting support.

### Phase 3 — AI Integration & Model Management (Weeks 7–9)
- LLM provider abstraction + Ollama integration.
- Prompt template system with validation — **English and German** template variants.
- Post-processor (syntax fix, safety scan, pacing analysis — language-aware).
- CLI: `generate` command (with `--language` flag).
- OpenAI / Anthropic remote providers.
- **Model Downloader** as a permanent CLI feature: `hypnoai models download`, `hypnoai models list`, `hypnoai models remove` (see §14).

### Phase 4 — Desktop GUI (Weeks 10–14)
- Tauri + React scaffold with Python sidecar bridge.
- JSON-RPC communication layer (file-path-based audio exchange).
- Script editor with syntax highlighting + **pacing heatmap**.
- Variables panel.
- Voice/render settings + progress bar.
- AI assistant panel with template wizard.
- **Model Manager panel** (browse, download, remove TTS engines and voice packs — always accessible, not just at first launch).
- **First-launch setup wizard** (guides new users to download their first engine + voice, then becomes the regular Model Manager).

### Phase 5 — Music & Audio (Weeks 15–17)
- Background music layering (`@{music}` directives).
- Auto-ducking.
- **Binaural/isochronic tone generator** (`@{binaural}` directive).
- `@{breath}` pattern generator.
- Audio timeline with waveform visualization.
- **Chapter marker embedding** (ID3, M4A).
- Dark/light theming.

### Phase 6 — Pro Features (Backlog)
- **Prosody Continuity**: sequential rendering with tail-audio reference chaining for supported engines (XTTS, F5-TTS). Prosody-aware cache invalidation. See §6.2.
- **Resource Orchestrator**: VRAM-aware model lifecycle manager with LRU eviction. GUI VRAM indicator. See §11.
- **Emotion tagging** (`@{voice: emotion=whisper}`) with StyleTTS 2 integration.
- **Live Mode**: real-time practitioner-guided sessions ("Next paragraph" / "Extend pause" buttons while AI speaks to client).
- SSML passthrough for prosody control.
- Binaural beat presets (theta program, delta program).
- Batch rendering for A/B variants.
- Community template sharing with license checks.
- Session analytics.

---

## 21. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Prosody discontinuity** ("Frankenstein audio") | Jarring tone shifts between paragraphs | Prosody reference chaining for supported engines (§6.2); crossfades + normalization for others. |
| **Sidecar data bottleneck** | UI lag when transferring audio | Exchange file paths only, never raw bytes. Shared temp directory (§18.1). |
| **VRAM contention** (LLM + TTS simultaneously) | OOM / crash on consumer GPUs | Resource Orchestrator with LRU eviction (§11). GUI shows VRAM meter. |
| **Multi-GB install size** | User drop-off during onboarding | Bootstrap installer: tiny initial download, progressive model fetching with clear UI (§14). |
| **TTS hallucination on long paragraphs** | Repeated words, gibberish | Paragraph-level generation. "Verify Paragraph" button to re-render single chunks. Max paragraph length limit. |
| **Audio clipping from mixed layers** | Distortion in final output | Brick-wall limiter at -1 dBFS as final chain stage (§10). |
| **Model licensing violations** | Legal risk | Model downloader shows license info. Only permissive licenses by default. Restricted models require explicit acknowledgment (§14.6). |
| **LLM generates unsafe content** | Therapeutic harm | Post-processor safety scan; user always reviews before render (§7.5). |
| **LLM generates invalid HypnoScript** | Broken scripts | Auto-fix common mistakes; lint before render. |
| **Tauri ↔ sidecar communication failure** | App hang | Heartbeat + timeout. Auto-restart sidecar. Error UI with recovery actions. |
| **Thread-safety issues** | Corrupted audio | Serialize GPU access behind lock; process isolation fallback. |
| **Long pauses feel dead** | Poor UX | Quiet pink noise during pauses; encourage `@{music}` and `@{binaural}` usage. |
| **Prosody cache invalidation cascade** | Slow re-render after small edits | Warn user in GUI; offer "fast mode" (no prosody chain) for editing, "quality mode" for final render. |
| **Inference drift on long scripts** | Quality degrades towards end | Per-paragraph generation inherently prevents this. "Verify Paragraph" for spot-checking. |
| **Voice–language mismatch** | Garbled pronunciation, broken immersion | Linter warns when `@{language}` doesn't match voice language prefix. GUI highlights mismatch before render (§9.2). |
| **AI generates poor non-English scripts** | Unnatural phrasing, literal translations | Native prompt templates per language (§9.4). Fallback to English template + language instruction when no native template exists. |

---

*This is a living document. Update it as implementation reveals new constraints and opportunities.*