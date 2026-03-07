/**
 * Pacing Heatmap — gutter overlay color-coding each paragraph by WPM.
 *
 * Green = 60–80 WPM (ideal for hypnosis)
 * Yellow = 80–100 WPM (borderline)
 * Red = >100 WPM (too fast)
 * Blue = <60 WPM (very slow — fine for deep induction)
 */
import type { PacingEntry } from "../types";

interface Props {
  pacing: PacingEntry[];
  paragraphCount: number;
  visible: boolean;
}

function wpmColor(wpm: number): string {
  if (wpm <= 60) return "bg-blue-400/60";
  if (wpm <= 80) return "bg-green-400/60";
  if (wpm <= 100) return "bg-yellow-400/60";
  return "bg-red-400/60";
}

function wpmLabel(wpm: number): string {
  if (wpm <= 60) return "slow";
  if (wpm <= 80) return "ideal";
  if (wpm <= 100) return "fast";
  return "too fast";
}

export function PacingHeatmap({ pacing, paragraphCount, visible }: Props) {
  if (!visible || pacing.length === 0) return null;

  return (
    <div className="flex flex-col gap-0.5 p-2 bg-surface-900 rounded border border-surface-700 min-w-[160px]">
      <div className="text-xs text-surface-400 font-mono mb-1 uppercase tracking-wide">
        Pacing
      </div>
      {pacing.map((entry) => (
        <div
          key={entry.paragraph}
          className="flex items-center gap-2 group"
          title={`Paragraph ${entry.paragraph + 1}: ${entry.wpm} WPM (${wpmLabel(entry.wpm)})`}
        >
          <div className="text-xs text-surface-500 w-4 text-right font-mono">
            {entry.paragraph + 1}
          </div>
          <div
            className={`h-4 rounded flex-1 ${wpmColor(entry.wpm)} flex items-center px-1`}
          >
            <span className="text-[10px] font-mono text-white/80">
              {entry.wpm}
            </span>
          </div>
          <div className="text-[10px] text-surface-400 w-12">
            {wpmLabel(entry.wpm)}
          </div>
        </div>
      ))}
      {pacing.length < paragraphCount && (
        <div className="text-[10px] text-surface-500 italic mt-1">
          Render to see full heatmap
        </div>
      )}
      <div className="border-t border-surface-700 mt-2 pt-2 flex flex-col gap-1">
        <div className="text-[10px] text-surface-400 flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-blue-400/60" /> slow ≤60
        </div>
        <div className="text-[10px] text-surface-400 flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-green-400/60" /> ideal 60–80
        </div>
        <div className="text-[10px] text-surface-400 flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-yellow-400/60" /> fast 80–100
        </div>
        <div className="text-[10px] text-surface-400 flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-red-400/60" /> too fast &gt;100
        </div>
      </div>
    </div>
  );
}
