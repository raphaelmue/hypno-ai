/**
 * JSON-RPC bridge between the React frontend and the Python sidecar.
 *
 * In the Tauri app, the Rust backend manages the sidecar process and exposes
 * two Tauri commands:
 *   - `rpc_call(method, params)` → Promise<result>
 *   - `rpc_stream(method, params, onChunk)` → async streaming via Tauri channels
 *
 * In non-Tauri (browser dev) mode, calls are stubbed so the UI still renders.
 */

import { useCallback } from "react";

// ---------------------------------------------------------------------------
// Tauri interop
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    __TAURI__?: {
      core: {
        invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>;
      };
    };
  }
}

const isTauri = () => typeof window !== "undefined" && !!window.__TAURI__;

async function tauriInvoke<T>(
  command: string,
  args: Record<string, unknown>
): Promise<T> {
  if (!isTauri()) {
    throw new Error(`Tauri not available (running in browser). Command: ${command}`);
  }
  return window.__TAURI__!.core.invoke<T>(command, args);
}

// ---------------------------------------------------------------------------
// RPC call (request → single response)
// ---------------------------------------------------------------------------

export async function rpcCall<T = unknown>(
  method: string,
  params: Record<string, unknown> = {}
): Promise<T> {
  return tauriInvoke<T>("rpc_call", { method, params });
}

// ---------------------------------------------------------------------------
// RPC stream (request → multiple chunks until done=true)
// ---------------------------------------------------------------------------

export async function rpcStream(
  method: string,
  params: Record<string, unknown>,
  onChunk: (chunk: Record<string, unknown>) => void
): Promise<void> {
  // Tauri channels are used for streaming; the Rust command sends events on a
  // channel and resolves when done=true is received.
  await tauriInvoke<void>("rpc_stream", { method, params, onChunk });
}

// ---------------------------------------------------------------------------
// Typed RPC helpers
// ---------------------------------------------------------------------------

import type {
  AIChunk,
  DownloadProgress,
  LintResult,
  ModelList,
  ModelStatus,
  PreviewResult,
  RenderProgress,
  VoiceInfo,
} from "../types";

export function useRpc() {
  // --- Script ---

  const lintScript = useCallback((path: string): Promise<LintResult> => {
    return rpcCall<LintResult>("script.lint", { path });
  }, []);

  // --- Render ---

  const renderStart = useCallback(
    (
      scriptPath: string,
      outputPath: string,
      options: {
        variables?: Record<string, string>;
        voice?: string;
        engine?: string;
        speed?: number;
      }
    ): Promise<{ job_id: string }> => {
      return rpcCall("render.start", {
        script_path: scriptPath,
        output_path: outputPath,
        ...options,
      });
    },
    []
  );

  const renderProgress = useCallback(
    (jobId: string): Promise<RenderProgress> => {
      return rpcCall<RenderProgress>("render.progress", { job_id: jobId });
    },
    []
  );

  const renderCancel = useCallback(
    (jobId: string): Promise<{ cancelled: boolean }> => {
      return rpcCall("render.cancel", { job_id: jobId });
    },
    []
  );

  const renderPreview = useCallback(
    (
      text: string,
      voice: string,
      engine: string,
      speed: number
    ): Promise<PreviewResult> => {
      return rpcCall<PreviewResult>("render.preview", {
        text,
        voice,
        engine,
        speed,
      });
    },
    []
  );

  // --- Voices ---

  const listVoices = useCallback(
    (engine: string, language?: string): Promise<{ voices: VoiceInfo[] }> => {
      return rpcCall("voices.list", { engine, language });
    },
    []
  );

  const cloneVoice = useCallback(
    (
      name: string,
      referencePath: string,
      engine: string
    ): Promise<{ voice_id: string; status: string }> => {
      return rpcCall("voices.clone", { name, reference_path: referencePath, engine });
    },
    []
  );

  // --- AI ---

  const generateScript = useCallback(
    (
      params: Record<string, unknown>,
      onChunk: (chunk: AIChunk) => void
    ): Promise<void> => {
      return rpcStream("ai.generate", params, onChunk as (chunk: Record<string, unknown>) => void);
    },
    []
  );

  // --- Models ---

  const modelsStatus = useCallback((): Promise<ModelStatus> => {
    return rpcCall<ModelStatus>("models.status", {});
  }, []);

  const modelsList = useCallback((): Promise<ModelList> => {
    return rpcCall<ModelList>("models.list", {});
  }, []);

  const modelsDownload = useCallback(
    (model: string): Promise<{ job_id: string; size_mb: number }> => {
      return rpcCall("models.download", { model });
    },
    []
  );

  const modelsDownloadProgress = useCallback(
    (jobId: string): Promise<DownloadProgress> => {
      return rpcCall<DownloadProgress>("models.download.progress", {
        job_id: jobId,
      });
    },
    []
  );

  const modelsRemove = useCallback(
    (model: string): Promise<{ freed_mb: number }> => {
      return rpcCall("models.remove", { model });
    },
    []
  );

  return {
    lintScript,
    renderStart,
    renderProgress,
    renderCancel,
    renderPreview,
    listVoices,
    cloneVoice,
    generateScript,
    modelsStatus,
    modelsList,
    modelsDownload,
    modelsDownloadProgress,
    modelsRemove,
  };
}
