/**
 * Engine Manager panel — install/uninstall TTS engines and manage Piper voice packs.
 * Accessible at any time via the sidebar or settings (§14.4).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { CatalogVoice, DownloadProgress, EngineSpec, ModelStatus } from "../types";
import { useRpc } from "../hooks/useRpc";

interface Props {
  onClose?: () => void;
  isFirstLaunch?: boolean;
}

interface ActiveDownload {
  jobId: string;
  voiceName: string;
  progress: DownloadProgress | null;
}

interface ActiveInstall {
  engine: string;
  lines: string[];
  error: string | null;
}

export function EngineManager({ onClose, isFirstLaunch = false }: Props) {
  const rpc = useRpc();
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [engines, setEngines] = useState<EngineSpec[]>([]);
  const [catalogVoices, setCatalogVoices] = useState<CatalogVoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [activeInstall, setActiveInstall] = useState<ActiveInstall | null>(null);
  const [uninstallingEngine, setUninstallingEngine] = useState<string | null>(null);
  const [activeDownloads, setActiveDownloads] = useState<ActiveDownload[]>([]);
  const [removingVoice, setRemovingVoice] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch voice catalog separately — it requires a HuggingFace network call
  // which can block the sidecar for several seconds. We don't want that to
  // delay the engine list or prevent the Install button from working.
  const fetchCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const result = await rpc.voicesCatalog();
      setCatalogVoices(result.voices);
    } catch (e) {
      setCatalogError(`Failed to load voice catalog: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setCatalogLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Load engine list first — it's fast and controls the loading spinner.
      const enginesResult = await rpc.enginesList();
      setEngines(enginesResult.engines);
    } catch (e) {
      setError(`Failed to load: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
    // Load GPU/disk status independently — may be slow if torch is installed.
    try {
      const statusResult = await rpc.modelsStatus();
      setStatus(statusResult);
    } catch {
      // Status is informational; swallow errors silently.
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchData().then(() => fetchCatalog());
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll download progress for active voice-pack downloads
  useEffect(() => {
    if (activeDownloads.length === 0) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(async () => {
      const updated = await Promise.all(
        activeDownloads.map(async (dl) => {
          try {
            const progress = await rpc.modelsDownloadProgress(dl.jobId);
            return { ...dl, progress };
          } catch {
            return dl;
          }
        })
      );
      const stillActive = updated.filter(
        (dl) => dl.progress?.state !== "done" && dl.progress?.state !== "failed"
      );
      if (stillActive.length < updated.length) fetchData();
      setActiveDownloads(stillActive);
    }, 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeDownloads]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleInstall = async (engineName: string) => {
    setActiveInstall({ engine: engineName, lines: [], error: null });
    try {
      await rpc.enginesInstall(engineName, (line) => {
        setActiveInstall((prev) =>
          prev ? { ...prev, lines: [...prev.lines, line] } : null
        );
      });
      setActiveInstall(null);
      fetchData().then(() => fetchCatalog());
    } catch (e) {
      setActiveInstall((prev) =>
        prev ? { ...prev, error: String(e) } : null
      );
    }
  };

  const handleUninstall = async (engineName: string) => {
    if (!confirm(`Uninstall "${engineName}"?`)) return;
    setUninstallingEngine(engineName);
    try {
      await rpc.enginesUninstall(engineName);
    } catch (e) {
      console.error("Uninstall failed:", e);
    } finally {
      setUninstallingEngine(null);
      fetchData().then(() => fetchCatalog());
    }
  };

  const handleDownloadVoice = async (voiceId: string) => {
    try {
      const result = await rpc.modelsDownload(voiceId);
      setActiveDownloads((prev) => [
        ...prev,
        {
          jobId: result.job_id,
          voiceName: voiceId,
          progress: { state: "pending", progress_pct: 0, speed_mbps: 0, error: null },
        },
      ]);
    } catch (e) {
      console.error("Download failed:", e);
    }
  };

  const handleRemoveVoice = async (voiceId: string, sizeMb: number) => {
    if (!confirm(`Remove voice "${voiceId}"? This will free ${sizeMb.toFixed(1)} MB.`)) return;
    setRemovingVoice(voiceId);
    try {
      await rpc.modelsRemove(voiceId);
      fetchData().then(() => fetchCatalog());
    } catch (e) {
      console.error("Remove failed:", e);
    } finally {
      setRemovingVoice(null);
    }
  };

  const installedVoices = catalogVoices.filter((v) => v.installed);
  const availableVoices = catalogVoices.filter((v) => !v.installed);
  const piperInstalled = engines.find((e) => e.name === "piper")?.installed ?? false;
  const anyEngineReady =
    installedVoices.length > 0 ||
    engines.some((e) => e.name !== "piper" && e.installed);

  return (
    <div className="flex flex-col h-full bg-surface-950">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700 bg-surface-900">
        <div>
          <h2 className="text-sm font-medium text-surface-200">
            {isFirstLaunch ? "Welcome to HypnoAI — Setup" : "Engine Manager"}
          </h2>
          {isFirstLaunch && (
            <p className="text-xs text-surface-400 mt-0.5">
              Install a TTS engine or download a Piper voice to get started.
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
            Loading…
          </div>
        )}

        {error && (
          <div className="bg-danger/10 border border-danger/30 rounded p-3 text-sm text-danger">
            {error}
          </div>
        )}

        {/* Active engine install log */}
        {activeInstall && (
          <section>
            <h3 className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
              Installing {activeInstall.engine}…
            </h3>
            <div className="bg-surface-900 rounded p-3 border border-surface-700 font-mono text-xs text-surface-300 max-h-40 overflow-y-auto">
              {activeInstall.lines.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
              {activeInstall.error && (
                <div className="text-danger mt-1">{activeInstall.error}</div>
              )}
              {!activeInstall.error && activeInstall.lines.length === 0 && (
                <div className="text-surface-500 animate-pulse">Starting…</div>
              )}
            </div>
          </section>
        )}

        {/* Active voice-pack downloads */}
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
                    <span className="text-sm text-surface-200">{dl.voiceName}</span>
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

        {/* TTS Engines */}
        {engines.length > 0 && (
          <section>
            <h3 className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
              TTS Engines
            </h3>
            <div className="flex flex-col gap-2">
              {engines.map((engine) => (
                <div
                  key={engine.name}
                  className="bg-surface-800 rounded p-3 border border-surface-700 flex items-start gap-3"
                >
                  <span
                    className={`text-base mt-0.5 ${engine.installed ? "text-success" : "text-surface-500"}`}
                  >
                    {engine.installed ? "✓" : "○"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm text-surface-200 font-medium capitalize">
                        {engine.name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-surface-400">
                        {engine.voice_type}
                      </span>
                      {engine.vram_mb > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-surface-400">
                          GPU
                        </span>
                      )}
                      {engine.supports_cloning && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-surface-400">
                          cloning
                        </span>
                      )}
                      {engine.supports_emotions && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-700 text-surface-400">
                          emotions
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-surface-400 mt-0.5">
                      {engine.description}
                    </div>
                    <div className="text-xs text-surface-500 mt-0.5">
                      {engine.languages.join(", ")}
                    </div>
                    <div className="text-xs text-surface-500">
                      {engine.model_size_gb > 0 ? `${engine.model_size_gb} GB · ` : ""}
                      {engine.license}
                    </div>
                  </div>
                  {engine.name !== "piper" && (engine.installed ? (
                    <button
                      onClick={() => handleUninstall(engine.name)}
                      disabled={uninstallingEngine === engine.name || !!activeInstall}
                      className="text-xs px-2 py-1 rounded bg-danger/10 text-danger hover:bg-danger/20 disabled:opacity-50 shrink-0"
                    >
                      {uninstallingEngine === engine.name ? "…" : "Uninstall"}
                    </button>
                  ) : (
                    <button
                      onClick={() => handleInstall(engine.name)}
                      disabled={!!activeInstall}
                      className="text-xs px-2 py-1 rounded bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-50 shrink-0"
                    >
                      Install
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Piper Voice Packs */}
        {piperInstalled && (
          <section>
            <h3 className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
              Piper Voice Packs
            </h3>

            {installedVoices.length > 0 && (
              <div className="flex flex-col gap-2 mb-2">
                {installedVoices.map((voice) => (
                  <div
                    key={voice.id}
                    className="bg-surface-800 rounded p-3 border border-surface-700 flex items-center gap-3"
                  >
                    <span className="text-success text-base">✓</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-surface-200 font-medium truncate">
                        {voice.id}
                      </div>
                      <div className="text-xs text-surface-400">
                        {voice.language} · {voice.quality} · {voice.size_mb.toFixed(0)} MB
                      </div>
                    </div>
                    <button
                      onClick={() => handleRemoveVoice(voice.id, voice.size_mb)}
                      disabled={removingVoice === voice.id}
                      className="text-xs px-2 py-1 rounded bg-danger/10 text-danger hover:bg-danger/20 disabled:opacity-50 shrink-0"
                    >
                      {removingVoice === voice.id ? "…" : "Remove"}
                    </button>
                  </div>
                ))}
              </div>
            )}

            {availableVoices.length > 0 && (
              <div className="flex flex-col gap-2">
                {availableVoices.map((voice) => (
                  <div
                    key={voice.id}
                    className="bg-surface-800 rounded p-3 border border-surface-700 flex items-start gap-3"
                  >
                    <span className="text-surface-500 text-base mt-0.5">⬇</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-surface-200 font-medium truncate">
                        {voice.id}
                      </div>
                      <div className="text-xs text-surface-400">
                        {voice.language} · {voice.quality} · {voice.size_mb.toFixed(0)} MB
                      </div>
                    </div>
                    <button
                      onClick={() => handleDownloadVoice(voice.id)}
                      disabled={activeDownloads.some((d) => d.voiceName === voice.id)}
                      className="text-xs px-2 py-1 rounded bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-50 shrink-0"
                    >
                      Download
                    </button>
                  </div>
                ))}
              </div>
            )}

            {catalogLoading && (
              <p className="text-xs text-surface-400 py-2 animate-pulse">Loading catalog…</p>
            )}
            {catalogError && (
              <p className="text-xs text-danger py-2">{catalogError}</p>
            )}
            {installedVoices.length === 0 && availableVoices.length === 0 && !catalogLoading && !catalogError && (
              <p className="text-xs text-surface-500 py-2">
                No voice packs found. Check your connection and try refreshing.
              </p>
            )}
          </section>
        )}
      </div>

      {/* First-launch footer */}
      {isFirstLaunch && onClose && (
        <div className="p-4 border-t border-surface-700 bg-surface-900">
          <button
            onClick={onClose}
            disabled={!anyEngineReady}
            className="w-full py-2 rounded bg-accent text-surface-950 text-sm font-medium hover:bg-accent-hover disabled:opacity-50"
          >
            Get Started →
          </button>
          {!anyEngineReady && (
            <p className="text-xs text-surface-500 text-center mt-1">
              Install an engine or download a Piper voice to continue.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
