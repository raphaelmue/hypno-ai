/**
 * Shared TypeScript types for the HypnoAI GUI.
 * Mirrors the JSON-RPC schema defined in §18 of the design document.
 */

// ---------------------------------------------------------------------------
// Voice & engine types
// ---------------------------------------------------------------------------

export interface VoiceInfo {
  id: string;
  name: string;
  language: string;
  quality: string;
  sample_rate: number;
  size_mb: number;
  is_custom: boolean;
  engine: string;
}

export interface EngineInfo {
  name: string;
  type: "tts" | "llm";
  requires_gpu: boolean;
  vram_mb: number;
  size_mb: number;
  license: string;
  install_hint?: string;
}

// ---------------------------------------------------------------------------
// Script / lint types
// ---------------------------------------------------------------------------

export interface PacingEntry {
  paragraph: number;
  wpm: number;
}

export interface LintResult {
  valid: boolean;
  warnings: string[];
  paragraph_count: number;
  pause_count: number;
  section_count: number;
  estimated_duration_s: number;
  variables: string[];
  pacing: PacingEntry[];
}

// ---------------------------------------------------------------------------
// Render job types
// ---------------------------------------------------------------------------

export type JobState = "pending" | "rendering" | "done" | "failed" | "cancelled";

export interface RenderProgress {
  state: JobState;
  current_paragraph: number;
  total: number;
  chunk_paths: string[];
  elapsed_s: number;
  error: string | null;
}

export interface PreviewResult {
  audio_path: string;
  duration_s: number;
}

// ---------------------------------------------------------------------------
// Model manager types
// ---------------------------------------------------------------------------

export interface InstalledModel {
  name: string;
  type: string;
  engine: string;
  size_mb: number;
  loaded: boolean;
  voices: string[];
  license: string;
}

export interface AvailableModel {
  name: string;
  type: string;
  size_mb: number;
  license: string;
  requires_gpu: boolean;
  install_hint?: string;
}

export interface ModelList {
  installed: InstalledModel[];
  available_for_download: AvailableModel[];
}

export interface ModelStatus {
  gpu_available: boolean;
  vram_total_mb: number;
  disk_used_mb: number;
}

export type DownloadState = "pending" | "downloading" | "done" | "failed";

export interface DownloadProgress {
  state: DownloadState;
  progress_pct: number;
  speed_mbps: number;
  error: string | null;
}

// ---------------------------------------------------------------------------
// AI generation types
// ---------------------------------------------------------------------------

export interface AIGenerateParams {
  template: string;
  language: string;
  variables: Record<string, string>;
  provider: string;
  duration: number;
  theme: string;
}

export interface AIChunk {
  chunk?: string;
  done?: boolean;
  script?: string;
  validation?: { warnings: string[] };
}

// ---------------------------------------------------------------------------
// Session / app state
// ---------------------------------------------------------------------------

export interface RenderSettings {
  engine: string;
  voice: string;
  speed: number;
  pitch: number;
  emotion: string;
}

export interface SessionVariables {
  [key: string]: string;
}

export type AppView = "editor" | "model-manager" | "first-launch";
