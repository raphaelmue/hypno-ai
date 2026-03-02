/**
 * Root application component.
 *
 * Manages the top-level layout and coordinates between panels:
 * - Sidebar (session tree, variables, model status)
 * - Script editor (main content area)
 * - Voice/render settings (right panel)
 * - AI assistant (slide-out overlay)
 * - Model manager (full-screen panel)
 * - First-launch wizard (rendered as Model Manager with isFirstLaunch=true)
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AIAssistant,
  ModelManager,
  ScriptEditor,
  Sidebar,
  VoiceManager,
  VoiceRenderSettings,
} from "./components";
import type {
  AIGenerateParams,
  LintResult,
  ModelStatus,
  RenderProgress,
  RenderSettings,
  SessionInfo,
  SessionVariables,
  VoiceInfo,
} from "./types";
import { useRpc, showInFolder, showOpenDialog } from "./hooks/useRpc";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_RENDER_SETTINGS: RenderSettings = {
  engine: "piper",
  voice: "en_US-amy-medium",
  speed: 0.85,
  pitch: 0,
  emotion: "",
};

const POLL_INTERVAL_MS = 1000;
const AUTOSAVE_DELAY_MS = 1500;

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const rpc = useRpc();

  // View state
  const [showModelManager, setShowModelManager] = useState(false);
  const [isFirstLaunch, setIsFirstLaunch] = useState(false);
  const [showAIAssistant, setShowAIAssistant] = useState(false);
  const [showVoiceManager, setShowVoiceManager] = useState(false);

  // Sessions
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionsDir, setSessionsDir] = useState("");
  const isSavingRef = useRef(false);

  // Script state
  const [scriptContent, setScriptContent] = useState(
    `@{voice: en_US-amy-medium}\n@{speed: 0.85}\n\nClose your eyes and take a deep breath.\n\n@{pause: 4s}\n\nNow slowly release the air from your lungs.\n`
  );
  const [lintResult, setLintResult] = useState<LintResult | null>(null);
  const [isLinting, setIsLinting] = useState(false);

  // Variables
  const [variables, setVariables] = useState<SessionVariables>({});

  // Render state
  const [renderSettings, setRenderSettings] = useState<RenderSettings>(DEFAULT_RENDER_SETTINGS);
  const [outputPath, setOutputPath] = useState("");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [renderProgress, setRenderProgress] = useState<RenderProgress | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Voices
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);

  // AI generation
  const [isGenerating, setIsGenerating] = useState(false);

  // ---------------------------------------------------------------------------
  // Session helpers
  // ---------------------------------------------------------------------------

  const refreshSessions = useCallback(async () => {
    try {
      const result = await rpc.sessionsList();
      setSessions(result.sessions);
      if (result.sessions_dir) setSessionsDir(result.sessions_dir);
    } catch {
      // browser dev mode — ignore
    }
  }, [rpc]);

  // Auto-save the active session (debounced)
  const autosaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  activeSessionIdRef.current = activeSessionId;

  const scheduleAutosave = useCallback(
    (content: string, settings: RenderSettings) => {
      if (autosaveRef.current) clearTimeout(autosaveRef.current);
      autosaveRef.current = setTimeout(async () => {
        const id = activeSessionIdRef.current;
        if (!id || isSavingRef.current) return;
        isSavingRef.current = true;
        try {
          await rpc.sessionsSave({
            id,
            script_content: content,
            render_settings: settings,
          });
          // Update modified_at in local list
          setSessions((prev) =>
            prev.map((s) =>
              s.id === id ? { ...s, modified_at: new Date().toISOString() } : s
            )
          );
        } catch {
          // ignore — sidecar not running
        } finally {
          isSavingRef.current = false;
        }
      }, AUTOSAVE_DELAY_MS);
    },
    [rpc]
  );

  // ---------------------------------------------------------------------------
  // Bootstrap — check first launch & load voices/model status/sessions
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const init = async () => {
      try {
        const [voiceResult, status, activeEng, sessionsResult] = await Promise.all([
          rpc.listVoices("all"),
          rpc.modelsStatus(),
          rpc.enginesActive(),
          rpc.sessionsList(),
        ]);
        setVoices(voiceResult.voices);
        setModelStatus(status);
        setRenderSettings((prev) => ({ ...prev, engine: activeEng.engine, voice: "" }));
        setSessions(sessionsResult.sessions);
        if (sessionsResult.sessions_dir) setSessionsDir(sessionsResult.sessions_dir);

        // First launch: no voices installed
        if (voiceResult.voices.length === 0) {
          setIsFirstLaunch(true);
          setShowModelManager(true);
        }
      } catch {
        // Sidecar not running in browser dev mode — show placeholder
      }
    };
    init();
  }, []);

  // ---------------------------------------------------------------------------
  // Session actions
  // ---------------------------------------------------------------------------

  const handleNewSession = useCallback(async () => {
    try {
      const result = await rpc.sessionsCreate({
        name: "New Session",
        script_content: "",
        render_settings: DEFAULT_RENDER_SETTINGS,
      });
      const newSession: SessionInfo = {
        id: result.id,
        name: result.name,
        path: result.path,
        modified_at: new Date().toISOString(),
        is_draft: false,
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(result.id);
      setScriptContent("");
      setRenderSettings(DEFAULT_RENDER_SETTINGS);
      setOutputPath(result.output_path);
      setRenderProgress(null);
    } catch {
      // browser dev mode — just clear the editor
      setScriptContent("");
      setActiveSessionId(null);
    }
  }, [rpc]);

  const handleSelectSession = useCallback(
    async (id: string) => {
      if (id === activeSessionId) return;
      try {
        const data = await rpc.sessionsLoad(id);
        setActiveSessionId(id);
        setScriptContent(data.script_content);
        setOutputPath(data.output_path);
        setRenderProgress(null);
        if (data.render_settings && Object.keys(data.render_settings).length > 0) {
          setRenderSettings((prev) => ({ ...prev, ...data.render_settings }));
        }
      } catch (e) {
        console.error("Failed to load session:", e);
      }
    },
    [activeSessionId, rpc]
  );

  const handleDeleteSession = useCallback(
    async (id: string) => {
      try {
        await rpc.sessionsDelete(id);
        setSessions((prev) => prev.filter((s) => s.id !== id));
        if (activeSessionId === id) {
          setActiveSessionId(null);
          setScriptContent("");
          setOutputPath("");
          setRenderProgress(null);
        }
      } catch (e) {
        console.error("Failed to delete session:", e);
      }
    },
    [activeSessionId, rpc]
  );

  const handleRenameSession = useCallback(
    async (id: string, name: string) => {
      try {
        await rpc.sessionsRename(id, name);
        setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, name } : s)));
      } catch (e) {
        console.error("Failed to rename session:", e);
      }
    },
    [rpc]
  );

  const handleChangeSessionsDir = useCallback(async () => {
    try {
      const result = await showOpenDialog({
        title: "Choose sessions folder",
        properties: ["openDirectory", "createDirectory"],
      });
      if (result.canceled || !result.filePaths[0]) return;
      const newDir = result.filePaths[0];
      await rpc.sessionsDirSet(newDir);
      setSessionsDir(newDir);
      await refreshSessions();
    } catch (e) {
      console.error("Failed to change sessions dir:", e);
    }
  }, [rpc, refreshSessions]);

  // ---------------------------------------------------------------------------
  // Script change — triggers auto-save
  // ---------------------------------------------------------------------------

  const handleScriptChange = useCallback(
    (content: string) => {
      setScriptContent(content);
      scheduleAutosave(content, renderSettings);
    },
    [scheduleAutosave, renderSettings]
  );

  const handleSettingsChange = useCallback(
    (settings: RenderSettings) => {
      setRenderSettings(settings);
      scheduleAutosave(scriptContent, settings);
    },
    [scheduleAutosave, scriptContent]
  );

  // ---------------------------------------------------------------------------
  // Lint
  // ---------------------------------------------------------------------------

  const handleLint = useCallback(async () => {
    setIsLinting(true);
    try {
      const stubResult: LintResult = {
        valid: true,
        warnings: [],
        paragraph_count: scriptContent.split(/\n\n+/).filter((p) => {
          const t = p.trim();
          return t && !t.startsWith("@{");
        }).length,
        pause_count: (scriptContent.match(/@\{pause:/g) || []).length,
        section_count: (scriptContent.match(/@\{section:/g) || []).length,
        estimated_duration_s:
          scriptContent.split(/\n\n+/).reduce((acc, p) => {
            const words = p.trim().split(/\s+/).length;
            return acc + (words / (130 * 0.85)) * 60;
          }, 0) +
          (scriptContent.match(/@\{pause:\s*(\d+)/g) || []).reduce(
            (acc, m) => acc + parseInt(m.replace(/@\{pause:\s*/, ""), 10),
            0
          ),
        variables: Array.from(scriptContent.matchAll(/\{\{(\w+)\}\}/g)).map(
          (m) => m[1]
        ),
        pacing: scriptContent
          .split(/\n\n+/)
          .filter((p) => {
            const t = p.trim();
            return t && !t.startsWith("@{");
          })
          .map((_, i) => ({
            paragraph: i,
            wpm: Math.round(130 * 0.85),
          })),
      };
      setLintResult(stubResult);
    } finally {
      setIsLinting(false);
    }
  }, [scriptContent]);

  // Auto-lint on script change (debounced)
  useEffect(() => {
    const t = setTimeout(handleLint, 800);
    return () => clearTimeout(t);
  }, [scriptContent]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const startPolling = useCallback(
    (jobId: string) => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const progress = await rpc.renderProgress(jobId);
          setRenderProgress(progress);
          if (progress.state === "done" || progress.state === "failed" || progress.state === "cancelled") {
            clearInterval(pollRef.current!);
            pollRef.current = null;
            setIsRendering(false);
            setActiveJobId(null);
          }
        } catch {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          setIsRendering(false);
        }
      }, POLL_INTERVAL_MS);
    },
    [rpc]
  );

  const handleRender = useCallback(async () => {
    if (!renderSettings.voice) return;
    setIsRendering(true);
    setRenderProgress(null);
    try {
      const { job_id } = await rpc.renderStart(
        outputPath,
        {
          scriptContent,
          variables,
          voice: renderSettings.voice,
          engine: renderSettings.engine,
          speed: renderSettings.speed,
        }
      );
      setActiveJobId(job_id);
      startPolling(job_id);
    } catch (e) {
      console.error("Render failed:", e);
      setIsRendering(false);
    }
  }, [scriptContent, renderSettings, outputPath, variables, rpc, startPolling]);

  const handleEngineChange = useCallback(async (engine: string) => {
    try {
      await rpc.enginesUse(engine);
    } catch (e) {
      console.error("Failed to set engine:", e);
    }
    try {
      const result = await rpc.listVoices("all");
      setVoices(result.voices ?? []);
    } catch {
      // ignore
    }
  }, [rpc]);

  const handleCancelRender = useCallback(async () => {
    if (!activeJobId) return;
    await rpc.renderCancel(activeJobId);
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setIsRendering(false);
    setActiveJobId(null);
  }, [activeJobId, rpc]);

  const handleClearCache = useCallback(async () => {
    try {
      const result = await rpc.cacheClear();
      console.log(`Cache cleared: ${result.cleared_files} files, ${result.freed_mb} MB freed`);
    } catch (e) {
      console.error("Cache clear failed:", e);
    }
  }, [rpc]);

  const handleOpenInFolder = useCallback(() => {
    if (outputPath) showInFolder(outputPath);
  }, [outputPath]);

  // ---------------------------------------------------------------------------
  // AI generation
  // ---------------------------------------------------------------------------

  const handleGenerate = useCallback(
    async (params: AIGenerateParams, _onChunk: (chunk: string) => void) => {
      setIsGenerating(true);
      setScriptContent("");
      let generated = "";
      try {
        await rpc.generateScript(params, (chunk) => {
          if (chunk.chunk) {
            generated += chunk.chunk;
            setScriptContent((prev) => prev + chunk.chunk);
          }
        });
        // Create a draft session for the generated script
        try {
          const result = await rpc.sessionsCreate({
            name: `AI Draft — ${params.theme || params.template}`,
            script_content: generated,
            render_settings: renderSettings,
            is_draft: true,
          });
          const newSession: SessionInfo = {
            id: result.id,
            name: result.name,
            path: result.path,
            modified_at: new Date().toISOString(),
            is_draft: true,
          };
          setSessions((prev) => [newSession, ...prev]);
          setActiveSessionId(result.id);
          setOutputPath(result.output_path);
        } catch {
          // ignore — sidecar not running
        }
      } catch (e) {
        console.error("Generation failed:", e);
      } finally {
        setIsGenerating(false);
        setShowAIAssistant(false);
      }
    },
    [rpc, renderSettings]
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const engines = ["piper", "coqui", "kokoro", "styletts2", "f5tts", "bark"];

  return (
    <div className="flex h-screen bg-surface-950 text-surface-100 overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        sessionsDir={sessionsDir}
        onChangeSessionsDir={handleChangeSessionsDir}
        variables={variables}
        onVariablesChange={setVariables}
        lintResult={lintResult}
        modelStatus={modelStatus}
        onOpenModelManager={() => setShowModelManager(true)}
        installedModelCount={voices.length}
      />

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Title bar */}
        <div className="flex items-center justify-between px-4 py-2 bg-surface-900 border-b border-surface-700 shrink-0">
          <span className="text-sm font-medium text-surface-300">
            {activeSessionId
              ? (sessions.find((s) => s.id === activeSessionId)?.name ?? "HypnoAI")
              : "HypnoAI"}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-surface-500">
              Engine: {renderSettings.engine}
            </span>
            <button
              onClick={() => setShowAIAssistant(true)}
              className="text-xs px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 text-surface-200"
            >
              AI Assistant
            </button>
            <button
              onClick={() => setShowModelManager(true)}
              className="text-xs px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 text-surface-200"
            >
              Models
            </button>
          </div>
        </div>

        {/* Editor + settings */}
        <div className="flex flex-1 min-h-0">
          {/* Script editor */}
          <div className="flex-1 min-w-0 flex flex-col">
            <ScriptEditor
              value={scriptContent}
              onChange={handleScriptChange}
              lintResult={lintResult}
              onLint={handleLint}
              isLinting={isLinting}
            />
          </div>

          {/* Right panel: Voice/Render settings */}
          <div className="w-56 shrink-0 border-l border-surface-700 bg-surface-900 overflow-y-auto">
            <VoiceRenderSettings
              settings={renderSettings}
              onSettingsChange={handleSettingsChange}
              voices={voices}
              engines={engines}
              renderProgress={renderProgress}
              isRendering={isRendering}
              onRender={handleRender}
              onCancelRender={handleCancelRender}
              outputPath={outputPath}
              onOutputPathChange={setOutputPath}
              onManageVoices={() => setShowVoiceManager(true)}
              onEngineChange={handleEngineChange}
              onClearCache={handleClearCache}
              onOpenInFolder={handleOpenInFolder}
            />
          </div>
        </div>
      </div>

      {/* AI Assistant slide-out */}
      <AIAssistant
        visible={showAIAssistant}
        onClose={() => setShowAIAssistant(false)}
        onGenerate={handleGenerate}
        isGenerating={isGenerating}
        onCancel={() => setIsGenerating(false)}
      />

      {/* Voice Manager */}
      {showVoiceManager && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-2xl h-[80vh] rounded-lg overflow-hidden shadow-2xl border border-surface-700">
            <VoiceManager
              activeEngine={renderSettings.engine}
              onClose={() => setShowVoiceManager(false)}
              onVoicesChanged={async () => {
                const result = await rpc.listVoices("all");
                setVoices(result.voices ?? []);
              }}
            />
          </div>
        </div>
      )}

      {/* Model Manager / First-Launch Wizard */}
      {showModelManager && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-2xl h-[80vh] rounded-lg overflow-hidden shadow-2xl border border-surface-700">
            <ModelManager
              isFirstLaunch={isFirstLaunch}
              onClose={() => {
                setShowModelManager(false);
                setIsFirstLaunch(false);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
