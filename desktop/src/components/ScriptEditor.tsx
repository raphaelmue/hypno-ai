/**
 * Script Editor — plain textarea with directive syntax highlighting overlay
 * and inline pacing heatmap toggle.
 *
 * Full Monaco/CodeMirror integration is a Phase 5 polish item; this component
 * provides a functional editor backed by a <textarea> with styled directive
 * hint overlay rendered on top.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { LintResult } from "../types";
import { PacingHeatmap } from "./PacingHeatmap";

interface Props {
  value: string;
  onChange: (value: string) => void;
  lintResult: LintResult | null;
  onLint: () => void;
  isLinting: boolean;
}


export function ScriptEditor({
  value,
  onChange,
  lintResult,
  onLint,
  isLinting,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [showHeatmap, setShowHeatmap] = useState(true);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Tab inserts 2 spaces
      if (e.key === "Tab") {
        e.preventDefault();
        const el = e.currentTarget;
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const newValue = value.substring(0, start) + "  " + value.substring(end);
        onChange(newValue);
        requestAnimationFrame(() => {
          el.selectionStart = el.selectionEnd = start + 2;
        });
      }
    },
    [value, onChange]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-700 bg-surface-900">
        <span className="text-sm font-medium text-surface-300">Script Editor</span>
        <div className="flex-1" />
        <button
          onClick={() => setShowHeatmap((v) => !v)}
          className={`text-xs px-2 py-1 rounded ${
            showHeatmap
              ? "bg-accent/20 text-accent"
              : "text-surface-400 hover:text-surface-300"
          }`}
          title="Toggle pacing heatmap"
        >
          Heatmap
        </button>
        <button
          onClick={onLint}
          disabled={isLinting || !value.trim()}
          className="text-xs px-2 py-1 rounded bg-surface-700 hover:bg-surface-600 text-surface-200 disabled:opacity-50"
        >
          {isLinting ? "Checking…" : "Lint"}
        </button>
      </div>

      {/* Lint warnings banner */}
      {lintResult && lintResult.warnings.length > 0 && (
        <div className="bg-warning/10 border-b border-warning/30 px-3 py-2">
          <div className="text-xs text-warning font-medium mb-1">
            {lintResult.warnings.length} warning{lintResult.warnings.length !== 1 ? "s" : ""}
          </div>
          <ul className="space-y-0.5">
            {lintResult.warnings.map((w, i) => (
              <li key={i} className="text-xs text-surface-300">
                · {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Editor body */}
      <div className="flex flex-1 min-h-0 overflow-auto">
        {/* Line numbers */}
        <div className="py-4 px-2 text-surface-600 text-xs font-mono select-none bg-surface-950 border-r border-surface-800 min-w-[3rem] text-right">
          {value.split("\n").map((_, i) => (
            <div key={i} className="leading-6">
              {i + 1}
            </div>
          ))}
        </div>

        {/* Textarea */}
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full h-full min-h-[300px] resize-none bg-transparent text-surface-100 font-mono text-sm leading-6 p-4 outline-none caret-accent"
            placeholder={`@{voice: en_US-amy-medium}\n@{speed: 0.85}\n\nClose your eyes and take a deep breath.\n\n@{pause: 4s}\n\nNow slowly release...`}
            spellCheck={false}
          />
        </div>

        {/* Pacing heatmap sidebar */}
        {showHeatmap && lintResult && (
          <div className="p-2 border-l border-surface-800 bg-surface-950">
            <PacingHeatmap
              pacing={lintResult.pacing}
              paragraphCount={lintResult.paragraph_count}
              visible={showHeatmap}
            />
          </div>
        )}
      </div>

      {/* Status bar */}
      {lintResult && (
        <div className="flex items-center gap-4 px-3 py-1.5 border-t border-surface-700 bg-surface-900 text-xs text-surface-400">
          <span>{lintResult.paragraph_count} paragraphs</span>
          <span>{lintResult.pause_count} pauses</span>
          <span>
            ~{Math.floor(lintResult.estimated_duration_s / 60)}m{" "}
            {Math.round(lintResult.estimated_duration_s % 60)}s
          </span>
          {lintResult.variables.length > 0 && (
            <span>vars: {lintResult.variables.join(", ")}</span>
          )}
          <span
            className={lintResult.valid ? "text-success" : "text-warning"}
          >
            {lintResult.valid ? "✓ valid" : `⚠ ${lintResult.warnings.length} warnings`}
          </span>
        </div>
      )}
    </div>
  );
}
