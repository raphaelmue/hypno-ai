/**
 * JSON-RPC bridge between the React frontend and the Python sidecar.
 *
 * In the Electron app, the Node.js main process manages the sidecar and
 * exposes two IPC handlers via the preload script's `window.electronAPI`:
 *   - `rpcCall(method, params)` → Promise<result>
 *   - `rpcStream(method, params, onChunk)` → Promise<void> (streaming)
 */

import { useCallback } from "react";

// ---------------------------------------------------------------------------
// Electron interop
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    electronAPI?: {
      rpcCall: (method: string, params: Record<string, unknown>) => Promise<unknown>;
      rpcStream: (
        method: string,
        params: Record<string, unknown>,
        onChunk: (chunk: Record<string, unknown>) => void
      ) => Promise<void>;
    };
  }
}

const isElectron = () => typeof window !== "undefined" && !!window.electronAPI;

export async function rpcCall<T = unknown>(
  method: string,
  params: Record<string, unknown> = {}
): Promise<T> {
  if (!isElectron()) throw new Error(`Electron API not available (running in browser). Method: ${method}`);
  return window.electronAPI!.rpcCall(method, params) as Promise<T>;
}

export async function rpcStream(
  method: string,
  params: Record<string, unknown>,
  onChunk: (chunk: Record<string, unknown>) => void
): Promise<void> {
  if (!isElectron()) throw new Error(`Electron API not available (running in browser). Method: ${method}`);
  return window.electronAPI!.rpcStream(method, params, onChunk);
}

// ---------------------------------------------------------------------------
// Typed RPC helpers
// ---------------------------------------------------------------------------

import type {
  AIChunk,
  AIGenerateParams,
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
      params: AIGenerateParams,
      onChunk: (chunk: AIChunk) => void
    ): Promise<void> => {
      return rpcStream("ai.generate", params as unknown as Record<string, unknown>, onChunk as (chunk: Record<string, unknown>) => void);
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
