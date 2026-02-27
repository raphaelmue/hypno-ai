/**
 * Variables Panel — key-value fields for {{name}}, {{safe_place}}, etc.
 * Automatically populated from the script's variable references (via lint result).
 */
import React from "react";
import type { LintResult, SessionVariables } from "../types";

interface Props {
  variables: SessionVariables;
  onChange: (variables: SessionVariables) => void;
  lintResult: LintResult | null;
}

export function VariablesPanel({ variables, onChange, lintResult }: Props) {
  const knownVariables = lintResult?.variables ?? [];

  const handleChange = (key: string, value: string) => {
    onChange({ ...variables, [key]: value });
  };

  const allKeys = Array.from(
    new Set([...knownVariables, ...Object.keys(variables)])
  );

  return (
    <div className="p-3">
      <div className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-2">
        Variables
      </div>

      {allKeys.length === 0 ? (
        <div className="text-xs text-surface-500 italic">
          No variables detected. Use {"{{name}}"} in your script.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {allKeys.map((key) => (
            <div key={key}>
              <label className="block text-xs text-surface-400 mb-0.5 font-mono">
                {"{{"}
                {key}
                {"}}"}
              </label>
              <input
                type="text"
                value={variables[key] ?? ""}
                onChange={(e) => handleChange(key, e.target.value)}
                placeholder={`Enter ${key}…`}
                className="w-full px-2 py-1 text-xs bg-surface-800 border border-surface-700 rounded text-surface-100 focus:outline-none focus:border-accent placeholder-surface-600"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
