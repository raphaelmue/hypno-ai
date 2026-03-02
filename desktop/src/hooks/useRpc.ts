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
      showOpenDialog: (options: {
        title?: string;
        filters?: { name: string; extensions: string[] }[];
        properties?: string[];
      }) => Promise<{ canceled: boolean; filePaths: string[] }>;
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
  CatalogVoice,
  DownloadProgress,
  EngineStatus,
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
      outputPath: string,
      options: {
        scriptContent?: string;
        scriptPath?: string;
        variables?: Record<string, string>;
        voice?: string;
        engine?: string;
        speed?: number;
      }
    ): Promise<{ job_id: string }> => {
      const { scriptContent, scriptPath, ...rest } = options;
      return rpcCall("render.start", {
        output_path: outputPath,
        ...(scriptContent !== undefined ? { script_content: scriptContent } : {}),
        ...(scriptPath !== undefined ? { script_path: scriptPath } : {}),
        ...rest,
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

  const voicesEngines = useCallback(
    (): Promise<{ engines: EngineStatus[] }> =>
      rpcCall("voices.engines", {}),
    []
  );

  const voicesCatalog = useCallback(
    (): Promise<{ voices: CatalogVoice[] }> =>
      rpcCall("voices.catalog", {}),
    []
  );

  const voicesRemove = useCallback(
    (voiceId: string, engine: string): Promise<{ removed: boolean }> =>
      rpcCall("voices.remove", { voice_id: voiceId, engine }),
    []
  );

  const voicesAdd = useCallback(
    (name: string, sourcePath: string, engine: string): Promise<{ voice_id: string }> =>
      rpcCall("voices.add", { name, source_path: sourcePath, engine }),
    []
  );

  // --- Engines ---

  const enginesActive = useCallback(
    (): Promise<{ engine: string }> => rpcCall("engines.active", {}),
    []
  );

  const enginesUse = useCallback(
    (engine: string): Promise<{ engine: string }> => rpcCall("engines.use", { engine }),
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
    voicesEngines,
    voicesCatalog,
    voicesRemove,
    voicesAdd,
    enginesActive,
    enginesUse,
    generateScript,
    modelsStatus,
    modelsList,
    modelsDownload,
    modelsDownloadProgress,
    modelsRemove,
  };
}

export function showOpenDialog(options: {
  title?: string;
  filters?: { name: string; extensions: string[] }[];
  properties?: string[];
}): Promise<{ canceled: boolean; filePaths: string[] }> {
  if (!window.electronAPI?.showOpenDialog) {
    return Promise.resolve({ canceled: true, filePaths: [] });
  }
  return window.electronAPI.showOpenDialog(options);
}
