/**
 * Model Manager panel — browse, download, and remove TTS engines and voice packs.
 * Accessible at any time via the sidebar or settings (§14.4).
 */
import React, { useCallback, useEffect, useState } from "react";
import type { AvailableModel, DownloadProgress, InstalledModel, ModelList, ModelStatus } from "../types";

interface Props {
  onClose?: () => void;
  isFirstLaunch?: boolean;
}

interface ActiveDownload {
  jobId: string;
  modelName: string;
  progress: DownloadProgress | null;
}

// Stub for Tauri invoke — replaced by real hook in full app
async function stubInvoke<T>(_cmd: string, _args?: unknown): Promise<T> {
  throw new Error("Tauri not available in browser mode");
}

export function ModelManager({ onClose, isFirstLaunch = false }: Props) {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [modelList, setModelList] = useState<ModelList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeDownloads, setActiveDownloads] = useState<ActiveDownload[]>([]);
  const [removingModel, setRemovingModel] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // In production these calls go through the Tauri RPC bridge.
      // Gracefully show an offline state in browser dev mode.
      const [statusResult, listResult] = await Promise.all([
        stubInvoke<ModelStatus>("rpc_call", { method: "models.status", params: {} }),
        stubInvoke<ModelList>("rpc_call", { method: "models.list", params: {} }),
      ]);
      setStatus(statusResult);
      setModelList(listResult);
    } catch {
      setError("Model information unavailable (sidecar not running).");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleDownload = async (model: AvailableModel) => {
    try {
      const result = await stubInvoke<{ job_id: string; size_mb: number }>("rpc_call", {
        method: "models.download",
        params: { model: model.name },
      });
      const download: ActiveDownload = {
        jobId: result.job_id,
        modelName: model.name,
        progress: { state: "pending", progress_pct: 0, speed_mbps: 0, error: null },
      };
      setActiveDownloads((prev) => [...prev, download]);
    } catch (e) {
      console.error("Download failed:", e);
    }
  };

  const handleRemove = async (model: InstalledModel) => {
    if (!confirm(`Remove "${model.name}"? This will free ${model.size_mb.toFixed(1)} MB.`)) return;
    setRemovingModel(model.name);
    try {
      await stubInvoke("rpc_call", {
        method: "models.remove",
        params: { model: model.name },
      });
      await fetchModels();
    } catch (e) {
      console.error("Remove failed:", e);
    } finally {
      setRemovingModel(null);
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface-950">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700 bg-surface-900">
        <div>
          <h2 className="text-sm font-medium text-surface-200">
            {isFirstLaunch ? "Welcome to HypnoAI — Setup" : "Model Manager"}
          </h2>
          {isFirstLaunch && (
            <p className="text-xs text-surface-400 mt-0.5">
              Download your first TTS engine to get started.
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {status && (
            <div className="text-xs text-surface-400">
              {status.gpu_available ? (
                <span className="text-success">GPU available · {status.vram_total_mb} MB VRAM</span>
              ) : (
                <span>CPU only</span>
              )}
              {" · "}
              {status.disk_used_mb.toFixed(0)} MB used
            </div>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="text-surface-400 hover:text-surface-200"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
        {loading && (
          <div className="text-sm text-surface-400 text-center py-8 animate-pulse">
            Loading model information…
          </div>
        )}

        {error && (
          <div className="bg-danger/10 border border-danger/30 rounded p-3 text-sm text-danger">
            {error}
          </div>
        )}

        {/* Active downloads */}
        {activeDownloads.length > 0 && (
          <section>
            <h3 className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
              Downloading
            </h3>
            <div className="flex flex-col gap-2">
              {activeDownloads.map((dl) => (
                <div
                  key={dl.jobId}
                  className="bg-surface-800 rounded p-3 border border-surface-700"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-surface-200">{dl.modelName}</span>
                    <span className="text-xs text-surface-400">
                      {dl.progress?.progress_pct ?? 0}%
                    </span>
                  </div>
                  <div className="w-full bg-surface-700 rounded-full h-1.5">
                    <div
                      className="bg-accent h-full rounded-full transition-all"
                      style={{ width: `${dl.progress?.progress_pct ?? 0}%` }}
                    />
                  </div>
                  {dl.progress?.speed_mbps ? (
                    <div className="text-xs text-surface-500 mt-1">
                      {dl.progress.speed_mbps.toFixed(1)} MB/s
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Installed models */}
        {modelList && modelList.installed.length > 0 && (
          <section>
            <h3 className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
              Installed · {modelList.installed.length} model{modelList.installed.length !== 1 ? "s" : ""}
            </h3>
            <div className="flex flex-col gap-2">
              {modelList.installed.map((model) => (
                <div
                  key={model.name}
                  className="bg-surface-800 rounded p-3 border border-surface-700 flex items-center gap-3"
                >
                  <span className="text-success text-base">✓</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-surface-200 font-medium truncate">
                      {model.name}
                    </div>
                    <div className="text-xs text-surface-400">
                      {model.engine} · {model.size_mb.toFixed(0)} MB · {model.license}
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemove(model)}
                    disabled={removingModel === model.name}
                    className="text-xs px-2 py-1 rounded bg-danger/10 text-danger hover:bg-danger/20 disabled:opacity-50"
                    title="Remove"
                  >
                    {removingModel === model.name ? "…" : "Remove"}
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Available for download */}
        {modelList && modelList.available_for_download.length > 0 && (
          <section>
            <h3 className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
              Available
            </h3>
            <div className="flex flex-col gap-2">
              {modelList.available_for_download.map((model) => (
                <div
                  key={model.name}
                  className="bg-surface-800 rounded p-3 border border-surface-700 flex items-start gap-3"
                >
                  <span className="text-surface-500 text-base mt-0.5">⬇</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-surface-200 font-medium">
                        {model.name}
                      </span>
                      {model.requires_gpu && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-surface-400">
                          GPU
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-surface-400">
                      {model.size_mb >= 1000
                        ? `${(model.size_mb / 1024).toFixed(1)} GB`
                        : `${model.size_mb.toFixed(0)} MB`}{" "}
                      · {model.license}
                    </div>
                    {model.install_hint && (
                      <div className="text-xs text-surface-500 font-mono mt-1">
                        {model.install_hint}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => handleDownload(model)}
                    className="text-xs px-2 py-1 rounded bg-accent/20 text-accent hover:bg-accent/30"
                  >
                    Download
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {modelList && modelList.installed.length === 0 && (
          <div className="text-center py-4">
            <p className="text-sm text-surface-400">No models installed yet.</p>
            <p className="text-xs text-surface-500 mt-1">
              Download Piper to get started — it runs on CPU with no GPU required.
            </p>
          </div>
        )}
      </div>

      {/* First-launch footer */}
      {isFirstLaunch && onClose && (
        <div className="p-4 border-t border-surface-700 bg-surface-900">
          <button
            onClick={onClose}
            disabled={!modelList || modelList.installed.length === 0}
            className="w-full py-2 rounded bg-accent text-surface-950 text-sm font-medium hover:bg-accent-hover disabled:opacity-50"
          >
            Get Started →
          </button>
          {(!modelList || modelList.installed.length === 0) && (
            <p className="text-xs text-surface-500 text-center mt-1">
              Download at least one model to continue.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
