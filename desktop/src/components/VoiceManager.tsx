/**
 * Voice Manager — per-engine voice management.
 *
 * Three engine archetypes are handled differently:
 *   catalog (Piper)           — downloadable ONNX model per voice; full CRUD
 *   preset  (Kokoro, Bark)    — voices baked into one checkpoint; read-only list
 *   clone   (Coqui/F5/STTS2) — user .wav reference clips; removable
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { CatalogVoice, DownloadProgress, EngineStatus, VoiceInfo } from "../types";
import { useRpc, showOpenDialog } from "../hooks/useRpc";

interface Props {
  activeEngine?: string;
  onClose?: () => void;
  onVoicesChanged?: () => void;
}

interface ActiveDownload {
  jobId: string;
  voiceName: string;
  progress: DownloadProgress | null;
}

// Install instructions shown when an engine package is missing
const INSTALL_HINTS: Record<string, string> = {
  coqui: "pip install TTS",
  kokoro: "pip install kokoro",
  styletts2: "pip install styletts2",
  f5tts: "pip install f5-tts",
  bark: "pip install suno-bark",
};

const ENGINE_LABELS: Record<string, string> = {
  piper: "Piper",
  coqui: "Coqui XTTS v2",
  kokoro: "Kokoro",
  styletts2: "StyleTTS2",
  f5tts: "F5-TTS",
  bark: "Bark",
};

export function VoiceManager({ activeEngine, onClose, onVoicesChanged }: Props) {
  const {
    voicesEngines,
    voicesCatalog,
    modelsDownload,
    modelsDownloadProgress,
    voicesRemove,
    voicesAdd,
  } = useRpc();

  const [engines, setEngines] = useState<EngineStatus[]>([]);
  const [catalog, setCatalog] = useState<CatalogVoice[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [languageFilter, setLanguageFilter] = useState("");
  const [activeDownloads, setActiveDownloads] = useState<ActiveDownload[]>([]);
  const [removingVoice, setRemovingVoice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addVoiceName, setAddVoiceName] = useState("");
  const [addVoicePath, setAddVoicePath] = useState("");
  const [addingVoice, setAddingVoice] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // -------------------------------------------------------------------------
  // Data loading — engine statuses are fast (local disk), catalog is network
  // -------------------------------------------------------------------------

  const fetchEngines = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const result = await voicesEngines();
      setEngines(result.engines);
    } catch (e) {
      setError(`Could not load voice data: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }, [voicesEngines]);

  const fetchCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const result = await voicesCatalog();
      setCatalog(result.voices);
    } catch (e) {
      setCatalogError(`Catalog unavailable: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setCatalogLoading(false);
    }
  }, [voicesCatalog]);

  useEffect(() => {
    fetchEngines();
    fetchCatalog();
  }, [fetchEngines, fetchCatalog]);

  // -------------------------------------------------------------------------
  // Download polling
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (activeDownloads.length === 0) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(async () => {
      const updated = await Promise.all(
        activeDownloads.map(async (dl) => {
          try {
            const progress = await modelsDownloadProgress(dl.jobId);
            return { ...dl, progress };
          } catch {
            return dl;
          }
        })
      );
      const stillActive = updated.filter(
        (dl) => dl.progress?.state !== "done" && dl.progress?.state !== "failed"
      );
      if (stillActive.length < updated.length) {
        await fetchEngines(true);
        onVoicesChanged?.();
      }
      setActiveDownloads(stillActive);
    }, 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeDownloads, modelsDownloadProgress, fetchEngines, onVoicesChanged]);

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  const handleDownload = async (voice: CatalogVoice) => {
    try {
      const result = await modelsDownload(voice.id);
      setActiveDownloads((prev) => [
        ...prev,
        {
          jobId: result.job_id,
          voiceName: voice.id,
          progress: { state: "pending", progress_pct: 0, speed_mbps: 0, error: null },
        },
      ]);
    } catch (e) {
      console.error("Download failed:", e);
    }
  };

  const handleRemove = async (voice: VoiceInfo) => {
    if (!confirm(`Remove "${voice.name}"? This will free ${voice.size_mb.toFixed(1)} MB.`)) return;
    setRemovingVoice(voice.id);
    try {
      await voicesRemove(voice.id, voice.engine);
      await fetchEngines(true);
      onVoicesChanged?.();
    } catch (e) {
      console.error("Remove failed:", e);
    } finally {
      setRemovingVoice(null);
    }
  };

  const handlePickFile = async () => {
    const result = await showOpenDialog({
      title: "Select reference .wav clip",
      filters: [{ name: "WAV Audio", extensions: ["wav"] }],
      properties: ["openFile"],
    });
    if (!result.canceled && result.filePaths.length > 0) {
      setAddVoicePath(result.filePaths[0]);
      if (!addVoiceName) {
        // Pre-fill name from filename (without extension)
        const filename = result.filePaths[0].replace(/\\/g, "/").split("/").pop() ?? "";
        setAddVoiceName(filename.replace(/\.wav$/i, ""));
      }
    }
  };

  const handleAddVoice = async (engineName: string) => {
    if (!addVoiceName.trim() || !addVoicePath) return;
    setAddingVoice(true);
    try {
      await voicesAdd(addVoiceName.trim(), addVoicePath, engineName);
      setAddVoiceName("");
      setAddVoicePath("");
      await fetchEngines(true);
      onVoicesChanged?.();
    } catch (e) {
      console.error("Add voice failed:", e);
    } finally {
      setAddingVoice(false);
    }
  };

  // -------------------------------------------------------------------------
  // Derived data
  // -------------------------------------------------------------------------

  // Show only the active engine (if specified), otherwise show all
  const visibleEngines = activeEngine
    ? engines.filter((e) => e.name === activeEngine)
    : engines;

  const downloadingIds = new Set(activeDownloads.map((dl) => dl.voiceName));

  const catalogLanguages = Array.from(
    new Set(catalog.map((v) => v.language.slice(0, 2)))
  ).sort();

  const filteredCatalog = catalog.filter((v) => {
    if (v.installed || downloadingIds.has(v.id)) return false;
    if (languageFilter && !v.language.startsWith(languageFilter)) return false;
    return true;
  });

  // -------------------------------------------------------------------------
  // Render helpers
  // -------------------------------------------------------------------------

  const renderDownloads = () => {
    if (activeDownloads.length === 0) return null;
    return (
      <section>
        <SectionHeader label="Downloading" />
        <div className="flex flex-col gap-2">
          {activeDownloads.map((dl) => (
            <div key={dl.jobId} className="bg-surface-800 rounded p-3 border border-surface-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-surface-200">{dl.voiceName}</span>
                <span className="text-xs text-surface-400">{dl.progress?.progress_pct ?? 0}%</span>
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
    );
  };

  const renderCatalogEngine = (eng: EngineStatus) => {
    const installedVoices = eng.voices;
    return (
      <section key={eng.name}>
        <EngineHeader name={ENGINE_LABELS[eng.name] ?? eng.name} installed={eng.installed} />

        {/* Installed Piper voices */}
        {installedVoices.length > 0 && (
          <div className="flex flex-col gap-2 mb-4">
            {installedVoices.map((voice) => (
              <VoiceRow
                key={voice.id}
                voice={voice}
                onRemove={handleRemove}
                removing={removingVoice === voice.id}
              />
            ))}
          </div>
        )}
        {installedVoices.length === 0 && (
          <p className="text-xs text-surface-500 mb-4">No voices installed yet.</p>
        )}

        {/* Catalog download section */}
        <div className="border-t border-surface-800 pt-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-surface-400">Available for download</span>
            {catalogLanguages.length > 0 && (
              <select
                value={languageFilter}
                onChange={(e) => setLanguageFilter(e.target.value)}
                className="text-xs px-2 py-0.5 bg-surface-800 border border-surface-700 rounded text-surface-300 focus:outline-none focus:border-accent"
              >
                <option value="">All languages</option>
                {catalogLanguages.map((lang) => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            )}
          </div>

          {catalogLoading && (
            <p className="text-xs text-surface-500 animate-pulse">Fetching catalog…</p>
          )}
          {catalogError && (
            <p className="text-xs text-danger">{catalogError}</p>
          )}
          {!catalogLoading && !catalogError && filteredCatalog.length === 0 && catalog.length > 0 && (
            <p className="text-xs text-surface-500">
              All voices for this language are already installed.
            </p>
          )}

          <div className="flex flex-col gap-2">
            {filteredCatalog.map((voice) => (
              <div
                key={voice.id}
                className="bg-surface-800 rounded p-3 border border-surface-700 flex items-start gap-3"
              >
                <span className="text-surface-500 mt-0.5">⬇</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-surface-200 font-medium truncate">{voice.id}</div>
                  <div className="text-xs text-surface-400">
                    {voice.language} · {voice.quality} ·{" "}
                    {voice.size_mb >= 1000
                      ? `${(voice.size_mb / 1024).toFixed(1)} GB`
                      : `${voice.size_mb.toFixed(0)} MB`}
                  </div>
                </div>
                <button
                  onClick={() => handleDownload(voice)}
                  className="text-xs px-2 py-1 rounded bg-accent/20 text-accent hover:bg-accent/30"
                >
                  Download
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  };

  const renderPresetEngine = (eng: EngineStatus) => (
    <section key={eng.name}>
      <EngineHeader name={ENGINE_LABELS[eng.name] ?? eng.name} installed={eng.installed} />
      {!eng.installed ? (
        <NotInstalledHint engine={eng.name} />
      ) : (
        <>
          <p className="text-xs text-surface-500 mb-2">
            {eng.voices.length} preset voice{eng.voices.length !== 1 ? "s" : ""} — built into the
            model checkpoint, no download needed.
          </p>
          <div className="flex flex-wrap gap-1">
            {eng.voices.map((v) => (
              <span
                key={v.id}
                title={`${v.language} · ${v.quality}`}
                className="text-xs px-2 py-0.5 rounded bg-surface-800 border border-surface-700 text-surface-300"
              >
                {v.id}
              </span>
            ))}
          </div>
        </>
      )}
    </section>
  );

  const renderCloneEngine = (eng: EngineStatus) => (
    <section key={eng.name}>
      <EngineHeader name={ENGINE_LABELS[eng.name] ?? eng.name} installed={eng.installed} />
      {!eng.installed ? (
        <NotInstalledHint engine={eng.name} />
      ) : (
        <>
          {eng.voices.length === 0 ? (
            <p className="text-xs text-surface-500 mb-3">No custom voices yet.</p>
          ) : (
            <div className="flex flex-col gap-2 mb-4">
              {eng.voices.map((voice) => (
                <VoiceRow
                  key={voice.id}
                  voice={voice}
                  onRemove={handleRemove}
                  removing={removingVoice === voice.id}
                />
              ))}
            </div>
          )}

          {/* Add Voice form */}
          <div className="border-t border-surface-800 pt-3">
            <p className="text-xs text-surface-400 mb-2 font-medium">Add custom voice</p>
            <div className="flex flex-col gap-2">
              <input
                type="text"
                value={addVoiceName}
                onChange={(e) => setAddVoiceName(e.target.value)}
                placeholder="Voice name"
                className="px-2 py-1 text-xs bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={addVoicePath}
                  placeholder="No file selected"
                  className="flex-1 min-w-0 px-2 py-1 text-xs bg-surface-800 border border-surface-700 rounded text-surface-400 font-mono cursor-pointer"
                  onClick={handlePickFile}
                />
                <button
                  onClick={handlePickFile}
                  className="text-xs px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 text-surface-200 whitespace-nowrap"
                >
                  Browse…
                </button>
              </div>
              <button
                onClick={() => handleAddVoice(eng.name)}
                disabled={addingVoice || !addVoiceName.trim() || !addVoicePath}
                className="py-1.5 text-xs rounded bg-accent text-surface-950 hover:bg-accent-hover font-medium disabled:opacity-50"
              >
                {addingVoice ? "Adding…" : "Add Voice"}
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );

  // -------------------------------------------------------------------------
  // Main render
  // -------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full bg-surface-950">
      <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700 bg-surface-900">
        <h2 className="text-sm font-medium text-surface-200">Voice Manager</h2>
        {onClose && (
          <button onClick={onClose} className="text-surface-400 hover:text-surface-200">×</button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
        {loading && (
          <div className="text-sm text-surface-400 text-center py-8 animate-pulse">
            Loading voices…
          </div>
        )}

        {error && (
          <div className="bg-danger/10 border border-danger/30 rounded p-3 text-sm text-danger">
            {error}
          </div>
        )}

        {!loading && (
          <>
            {renderDownloads()}

            {visibleEngines.map((eng) => {
              if (eng.voice_type === "catalog") return renderCatalogEngine(eng);
              if (eng.voice_type === "preset") return renderPresetEngine(eng);
              return renderCloneEngine(eng);
            })}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionHeader({ label }: { label: string }) {
  return (
    <h3 className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
      {label}
    </h3>
  );
}

function EngineHeader({ name, installed }: { name: string; installed: boolean }) {
  return (
    <div className="flex items-center gap-2 mb-2">
      <h3 className="text-xs font-medium text-surface-300 uppercase tracking-wide">{name}</h3>
      <span
        className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
          installed
            ? "bg-success/15 text-success"
            : "bg-surface-700 text-surface-400"
        }`}
      >
        {installed ? "installed" : "not installed"}
      </span>
    </div>
  );
}

function NotInstalledHint({ engine }: { engine: string }) {
  const hint = INSTALL_HINTS[engine];
  return (
    <p className="text-xs text-surface-500">
      Engine not installed.
      {hint && (
        <>
          {" "}Run:{" "}
          <code className="font-mono bg-surface-800 px-1 rounded">{hint}</code>
        </>
      )}
    </p>
  );
}

function VoiceRow({
  voice,
  onRemove,
  removing,
}: {
  voice: VoiceInfo;
  onRemove: (v: VoiceInfo) => void;
  removing: boolean;
}) {
  return (
    <div className="bg-surface-800 rounded p-3 border border-surface-700 flex items-center gap-3">
      <span className="text-success">✓</span>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-surface-200 font-medium truncate">{voice.name}</div>
        <div className="text-xs text-surface-400">
          {voice.language}
          {voice.quality ? ` · ${voice.quality}` : ""}
          {voice.size_mb > 0 ? ` · ${voice.size_mb.toFixed(0)} MB` : ""}
        </div>
      </div>
      <button
        onClick={() => onRemove(voice)}
        disabled={removing}
        className="text-xs px-2 py-1 rounded bg-danger/10 text-danger hover:bg-danger/20 disabled:opacity-50"
      >
        {removing ? "…" : "Remove"}
      </button>
    </div>
  );
}
