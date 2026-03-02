/**
 * Voice & Render Settings panel — engine/voice dropdowns, speed/pitch sliders,
 * progress bar, audio player, and Render button.
 */
import { useRef } from "react";
import type { RenderProgress, RenderSettings, VoiceInfo } from "../types";
import { localFileUrl, showSaveDialog } from "../hooks/useRpc";

interface Props {
  settings: RenderSettings;
  onSettingsChange: (s: RenderSettings) => void;
  voices: VoiceInfo[];
  engines: string[];
  renderProgress: RenderProgress | null;
  isRendering: boolean;
  onRender: () => void;
  onCancelRender: () => void;
  outputPath: string;
  onOutputPathChange: (path: string) => void;
  onManageVoices?: () => void;
  onEngineChange?: (engine: string) => void;
  onClearCache: () => void;
  onOpenInFolder: () => void;
}

const EMOTIONS = ["", "soothing", "warm", "whisper", "confident", "calm"];

function ProgressBar({ progress }: { progress: RenderProgress }) {
  const pct =
    progress.total > 0
      ? Math.round((progress.current_paragraph / progress.total) * 100)
      : 0;

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between text-xs text-surface-400 mb-1">
        <span>
          {progress.state === "rendering" && (
            <>
              Paragraph {progress.current_paragraph}/{progress.total}
            </>
          )}
          {progress.state === "done" && "Done"}
          {progress.state === "failed" && (
            <span className="text-danger">Failed: {progress.error}</span>
          )}
          {progress.state === "cancelled" && "Cancelled"}
        </span>
        <span>{pct}%</span>
      </div>
      <div className="w-full bg-surface-700 rounded-full h-1.5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            progress.state === "done"
              ? "bg-success"
              : progress.state === "failed"
              ? "bg-danger"
              : "bg-accent"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {progress.state === "rendering" && (
        <div className="text-xs text-surface-500 mt-1">
          {Math.round(progress.elapsed_s)}s elapsed
        </div>
      )}
    </div>
  );
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  onChange,
  format,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
}) {
  return (
    <div>
      <div className="flex justify-between text-xs text-surface-400 mb-1">
        <span>{label}</span>
        <span className="font-mono text-surface-300">
          {format ? format(value) : value}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-accent"
      />
    </div>
  );
}

export function VoiceRenderSettings({
  settings,
  onSettingsChange,
  voices,
  engines,
  renderProgress,
  isRendering,
  onRender,
  onCancelRender,
  outputPath,
  onOutputPathChange,
  onManageVoices,
  onEngineChange,
  onClearCache,
  onOpenInFolder,
}: Props) {
  const set = (patch: Partial<RenderSettings>) =>
    onSettingsChange({ ...settings, ...patch });

  const filteredVoices = voices.filter(
    (v) => v.engine === settings.engine || settings.engine === "all"
  );

  const audioRef = useRef<HTMLAudioElement>(null);
  const isDone = renderProgress?.state === "done";

  const handleBrowse = async () => {
    const result = await showSaveDialog({
      title: "Save session as…",
      defaultPath: outputPath || "session.wav",
      filters: [{ name: "Audio", extensions: ["wav"] }],
    });
    if (!result.canceled && result.filePath) {
      onOutputPathChange(result.filePath);
    }
  };

  return (
    <div className="p-3 flex flex-col gap-3">
      <div className="text-xs font-medium text-surface-400 uppercase tracking-wide">
        Voice & Render Settings
      </div>

      {/* Engine */}
      <div>
        <label className="block text-xs text-surface-400 mb-1">Engine</label>
        <select
          value={settings.engine}
          onChange={(e) => {
            set({ engine: e.target.value, voice: "" });
            onEngineChange?.(e.target.value);
          }}
          className="w-full px-2 py-1 text-xs bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent"
        >
          {engines.map((e) => (
            <option key={e} value={e}>
              {e}
            </option>
          ))}
        </select>
      </div>

      {/* Voice */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <label className="text-xs text-surface-400">Voice</label>
          {onManageVoices && (
            <button
              onClick={onManageVoices}
              className="text-[10px] text-accent hover:underline"
            >
              Manage
            </button>
          )}
        </div>
        <select
          value={settings.voice}
          onChange={(e) => set({ voice: e.target.value })}
          className="w-full px-2 py-1 text-xs bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent"
        >
          <option value="">— select voice —</option>
          {filteredVoices.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name} ({v.language}, {v.quality})
            </option>
          ))}
        </select>
      </div>

      {/* Emotion */}
      <div>
        <label className="block text-xs text-surface-400 mb-1">Emotion</label>
        <select
          value={settings.emotion}
          onChange={(e) => set({ emotion: e.target.value })}
          className="w-full px-2 py-1 text-xs bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent"
        >
          {EMOTIONS.map((em) => (
            <option key={em} value={em}>
              {em || "default"}
            </option>
          ))}
        </select>
      </div>

      {/* Speed slider */}
      <SliderField
        label="Speed"
        value={settings.speed}
        min={0.5}
        max={2.0}
        step={0.05}
        onChange={(v) => set({ speed: v })}
        format={(v) => `${v.toFixed(2)}×`}
      />

      {/* Pitch slider */}
      <SliderField
        label="Pitch"
        value={settings.pitch}
        min={-6}
        max={6}
        step={0.5}
        onChange={(v) => set({ pitch: v })}
        format={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}st`}
      />

      {/* Output path + browse */}
      <div>
        <label className="block text-xs text-surface-400 mb-1">Output file</label>
        <div className="flex gap-1">
          <input
            type="text"
            value={outputPath}
            onChange={(e) => onOutputPathChange(e.target.value)}
            className="flex-1 min-w-0 px-2 py-1 text-xs bg-surface-800 border border-surface-700 rounded text-surface-100 font-mono focus:outline-none focus:border-accent"
            placeholder="Click Browse…"
            readOnly
          />
          <button
            onClick={handleBrowse}
            className="px-2 py-1 text-xs rounded bg-surface-700 hover:bg-surface-600 text-surface-200 shrink-0"
          >
            Browse
          </button>
        </div>
      </div>

      {/* Render / Cancel button */}
      <div className="pt-1">
        {isRendering ? (
          <button
            onClick={onCancelRender}
            className="w-full py-1.5 text-xs rounded bg-danger/20 hover:bg-danger/30 text-danger"
          >
            ✕ Cancel
          </button>
        ) : (
          <button
            onClick={onRender}
            disabled={!settings.voice || !outputPath}
            className="w-full py-1.5 text-xs rounded bg-accent text-surface-950 hover:bg-accent-hover font-medium disabled:opacity-50"
          >
            ⏺ Render
          </button>
        )}
      </div>

      {/* Progress bar */}
      {renderProgress && <ProgressBar progress={renderProgress} />}

      {/* Audio player — shown after a successful render */}
      {isDone && outputPath && (
        <div className="border border-surface-700 rounded-lg p-2 bg-surface-800 flex flex-col gap-2">
          <div className="text-xs text-surface-400 font-medium">Playback</div>
          <audio
            ref={audioRef}
            src={localFileUrl(outputPath)}
            controls
            className="w-full h-8"
            style={{ colorScheme: "dark" }}
          />
          <button
            onClick={onOpenInFolder}
            className="w-full py-1 text-xs rounded bg-surface-700 hover:bg-surface-600 text-surface-300"
          >
            Show in Folder
          </button>
        </div>
      )}

      {/* Clear cache — maintenance action */}
      <div className="pt-1 border-t border-surface-800">
        <button
          onClick={onClearCache}
          className="w-full py-1 text-[10px] text-surface-500 hover:text-surface-300 hover:bg-surface-800 rounded transition-colors"
          title="Delete all cached render chunks to free disk space"
        >
          Clear render cache
        </button>
      </div>
    </div>
  );
}
