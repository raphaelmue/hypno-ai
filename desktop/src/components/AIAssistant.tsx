/**
 * AI Assistant panel — template wizard for LLM-driven script generation.
 * Slide-out panel with session type, duration, theme, provider, and Generate button.
 * Streams output directly into the parent's script editor.
 */
import { useState } from "react";
import type { AIGenerateParams } from "../types";

interface Props {
  onGenerate: (params: AIGenerateParams, onChunk: (chunk: string) => void) => void;
  isGenerating: boolean;
  onCancel?: () => void;
  visible: boolean;
  onClose: () => void;
}

const TEMPLATES = [
  { id: "progressive_relaxation", name: "Progressive Relaxation", category: "Relaxation" },
  { id: "sleep_induction", name: "Sleep Induction", category: "Sleep" },
  { id: "focus_enhancement", name: "Focus Enhancement", category: "Focus" },
  { id: "habit_change", name: "Habit Change", category: "Habit" },
  { id: "anxiety_relief", name: "Anxiety Relief", category: "Anxiety" },
  { id: "confidence_boost", name: "Confidence Boost", category: "Self-esteem" },
  { id: "pain_management", name: "Pain Management", category: "Pain" },
  { id: "custom", name: "Custom", category: "General" },
];

const PROVIDERS = ["ollama", "openai", "anthropic"];
const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "de", name: "German" },
];

export function AIAssistant({ onGenerate, isGenerating, onCancel, visible, onClose }: Props) {
  const [template, setTemplate] = useState("progressive_relaxation");
  const [language, setLanguage] = useState("en");
  const [duration, setDuration] = useState(20);
  const [theme, setTheme] = useState("relaxation and calm");
  const [provider, setProvider] = useState("ollama");
  const [name, setName] = useState("");

  const handleGenerate = () => {
    const params: AIGenerateParams = {
      template,
      language,
      variables: name ? { name } : {},
      provider,
      duration,
      theme,
    };
    onGenerate(params, () => {});
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="w-80 bg-surface-900 border-l border-surface-700 flex flex-col h-full shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-surface-700">
          <span className="text-sm font-medium text-surface-200">AI Script Assistant</span>
          <button
            onClick={onClose}
            className="text-surface-400 hover:text-surface-200 text-lg leading-none"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
          {/* Step 1 label */}
          <div className="text-xs text-surface-500 uppercase tracking-wide">
            Step 1 — Session type
          </div>

          {/* Template selector */}
          <div>
            <label className="block text-xs text-surface-400 mb-1">Template</label>
            <select
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              className="w-full px-2 py-1.5 text-sm bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent"
            >
              {TEMPLATES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.category})
                </option>
              ))}
            </select>
          </div>

          {/* Language */}
          <div>
            <label className="block text-xs text-surface-400 mb-1">Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full px-2 py-1.5 text-sm bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>

          {/* Duration */}
          <div>
            <div className="flex justify-between text-xs text-surface-400 mb-1">
              <span>Duration</span>
              <span className="font-mono text-surface-300">{duration} min</span>
            </div>
            <input
              type="range"
              min={5}
              max={60}
              step={5}
              value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value))}
              className="w-full accent-accent"
            />
          </div>

          {/* Theme */}
          <div>
            <label className="block text-xs text-surface-400 mb-1">Theme / goal</label>
            <input
              type="text"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="e.g. deep sleep, stress relief…"
              className="w-full px-2 py-1.5 text-sm bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent placeholder-surface-600"
            />
          </div>

          {/* Client name variable */}
          <div>
            <label className="block text-xs text-surface-400 mb-1">
              Client name ({"{{name}}"})
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="optional"
              className="w-full px-2 py-1.5 text-sm bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent placeholder-surface-600"
            />
          </div>

          <div className="border-t border-surface-700 pt-3">
            <div className="text-xs text-surface-500 uppercase tracking-wide mb-3">
              Step 2 — Provider
            </div>

            {/* Provider */}
            <div>
              <label className="block text-xs text-surface-400 mb-1">LLM provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="w-full px-2 py-1.5 text-sm bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent"
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>

            {provider === "ollama" && (
              <p className="text-xs text-surface-500 mt-1.5">
                Requires Ollama running locally at localhost:11434.
              </p>
            )}
            {(provider === "openai" || provider === "anthropic") && (
              <p className="text-xs text-warning mt-1.5">
                API key required — configure in hypnoai.toml.
              </p>
            )}
          </div>
        </div>

        {/* Generate button */}
        <div className="p-4 border-t border-surface-700">
          {isGenerating ? (
            <div className="flex flex-col gap-2">
              <div className="text-xs text-surface-400 text-center animate-pulse">
                Generating script…
              </div>
              {onCancel && (
                <button
                  onClick={onCancel}
                  className="w-full py-2 rounded bg-danger/20 text-danger text-sm hover:bg-danger/30"
                >
                  Cancel
                </button>
              )}
            </div>
          ) : (
            <button
              onClick={handleGenerate}
              className="w-full py-2 rounded bg-accent text-surface-950 text-sm font-medium hover:bg-accent-hover"
            >
              Generate Script
            </button>
          )}
          <p className="text-xs text-surface-500 text-center mt-2">
            AI output is a draft — always review before rendering.
          </p>
        </div>
      </div>
    </div>
  );
}
