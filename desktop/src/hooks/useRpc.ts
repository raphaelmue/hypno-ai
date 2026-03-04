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
      showSaveDialog: (options: {
        title?: string;
        defaultPath?: string;
        filters?: { name: string; extensions: string[] }[];
      }) => Promise<{ canceled: boolean; filePath?: string }>;
      showInFolder: (filePath: string) => Promise<void>;
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
  EngineSpec,
  EngineStatus,
  LintResult,
  ModelList,
  ModelStatus,
  RenderProgress,
  RenderSettings,
  SessionInfo,
  VoiceInfo,
} from "../types";

export function useRpc() {
  // --- Script ---

  const lintScript = useCallback(
    (scriptContent: string, variables?: Record<string, string>): Promise<LintResult> => {
      return rpcCall<LintResult>("script.lint", {
        script_content: scriptContent,
        ...(variables ? { variables } : {}),
      });
    },
    []
  );

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
        use_gpu?: boolean;
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

  const cacheClear = useCallback(
    (): Promise<{ cleared_files: number; freed_mb: number }> => {
      return rpcCall("cache.clear", {});
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

  const enginesList = useCallback(
    (): Promise<{ engines: EngineSpec[] }> => rpcCall("engines.list", {}),
    []
  );

  const enginesInstall = useCallback(
    (engine: string, onLine: (line: string) => void): Promise<void> =>
      rpcStream("engines.install", { engine }, (chunk) => {
        if (chunk.line) onLine(chunk.line as string);
      }),
    []
  );

  const enginesUninstall = useCallback(
    (engine: string): Promise<{ uninstalled: boolean }> =>
      rpcCall("engines.uninstall", { engine }),
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

  // --- Sessions ---

  const sessionsList = useCallback(
    (): Promise<{ sessions: SessionInfo[]; sessions_dir: string }> =>
      rpcCall("sessions.list", {}),
    []
  );

  const sessionsCreate = useCallback(
    (opts: {
      name?: string;
      script_content?: string;
      render_settings?: Partial<RenderSettings>;
      is_draft?: boolean;
    }): Promise<{ id: string; name: string; path: string; script_path: string; output_path: string }> =>
      rpcCall("sessions.create", opts as Record<string, unknown>),
    []
  );

  const sessionsLoad = useCallback(
    (id: string): Promise<{
      id: string;
      name: string;
      path: string;
      script_content: string;
      script_path: string;
      output_path: string;
      render_settings: Partial<RenderSettings>;
      variables: Record<string, string>;
      is_draft: boolean;
      modified_at: string;
    }> => rpcCall("sessions.load", { id }),
    []
  );

  const sessionsSave = useCallback(
    (opts: {
      id: string;
      script_content?: string;
      render_settings?: Partial<RenderSettings>;
      variables?: Record<string, string>;
      name?: string;
      is_draft?: boolean;
    }): Promise<{ id: string; modified_at: string }> =>
      rpcCall("sessions.save", opts as Record<string, unknown>),
    []
  );

  const sessionsDelete = useCallback(
    (id: string): Promise<{ deleted: boolean; id: string }> =>
      rpcCall("sessions.delete", { id }),
    []
  );

  const sessionsRename = useCallback(
    (id: string, name: string): Promise<{ id: string; name: string }> =>
      rpcCall("sessions.rename", { id, name }),
    []
  );

  const sessionsDirGet = useCallback(
    (): Promise<{ sessions_dir: string }> => rpcCall("sessions.dir.get", {}),
    []
  );

  const sessionsDirSet = useCallback(
    (sessions_dir: string): Promise<{ sessions_dir: string }> =>
      rpcCall("sessions.dir.set", { sessions_dir }),
    []
  );

  return {
    lintScript,
    renderStart,
    renderProgress,
    renderCancel,
    cacheClear,
    listVoices,
    cloneVoice,
    voicesEngines,
    voicesCatalog,
    voicesRemove,
    voicesAdd,
    enginesActive,
    enginesUse,
    enginesList,
    enginesInstall,
    enginesUninstall,
    generateScript,
    modelsStatus,
    modelsList,
    modelsDownload,
    modelsDownloadProgress,
    modelsRemove,
    sessionsList,
    sessionsCreate,
    sessionsLoad,
    sessionsSave,
    sessionsDelete,
    sessionsRename,
    sessionsDirGet,
    sessionsDirSet,
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

export function showSaveDialog(options: {
  title?: string;
  defaultPath?: string;
  filters?: { name: string; extensions: string[] }[];
}): Promise<{ canceled: boolean; filePath?: string }> {
  if (!window.electronAPI?.showSaveDialog) {
    return Promise.resolve({ canceled: true });
  }
  return window.electronAPI.showSaveDialog(options);
}

export function showInFolder(filePath: string): Promise<void> {
  if (!window.electronAPI?.showInFolder) return Promise.resolve();
  return window.electronAPI.showInFolder(filePath);
}

/** Convert an absolute local file path to a hypnoai-local:// URL the renderer can load. */
export function localFileUrl(filePath: string): string {
  const normalized = filePath.replace(/\\/g, '/');
  return `hypnoai-local://localhost/${encodeURIComponent(normalized)}`;
}
