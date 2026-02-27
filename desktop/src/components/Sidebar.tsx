/**
 * Application sidebar — session manager, variables panel, and model quick-status.
 */
import type { LintResult, ModelStatus, SessionVariables } from "../types";
import { VariablesPanel } from "./VariablesPanel";

interface Session {
  id: string;
  name: string;
  path: string;
  isDraft: boolean;
}

interface Props {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  variables: SessionVariables;
  onVariablesChange: (v: SessionVariables) => void;
  lintResult: LintResult | null;
  modelStatus: ModelStatus | null;
  onOpenModelManager: () => void;
  installedModelCount: number;
}

function SessionTree({
  sessions,
  activeId,
  onSelect,
}: {
  sessions: Session[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  const saved = sessions.filter((s) => !s.isDraft);
  const drafts = sessions.filter((s) => s.isDraft);

  const renderSession = (s: Session) => (
    <button
      key={s.id}
      onClick={() => onSelect(s.id)}
      className={`w-full text-left px-3 py-1.5 text-xs rounded truncate ${
        s.id === activeId
          ? "bg-accent/20 text-accent"
          : "text-surface-300 hover:bg-surface-700"
      }`}
      title={s.path}
    >
      {s.name}
    </button>
  );

  return (
    <div className="flex flex-col">
      {saved.length > 0 && (
        <div>
          <div className="px-3 py-1 text-[10px] text-surface-500 uppercase tracking-wide">
            My Scripts
          </div>
          {saved.map(renderSession)}
        </div>
      )}
      {drafts.length > 0 && (
        <div className="mt-2">
          <div className="px-3 py-1 text-[10px] text-surface-500 uppercase tracking-wide">
            AI Drafts
          </div>
          {drafts.map(renderSession)}
        </div>
      )}
    </div>
  );
}

export function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  variables,
  onVariablesChange,
  lintResult,
  modelStatus,
  onOpenModelManager,
  installedModelCount,
}: Props) {
  return (
    <div className="flex flex-col h-full bg-surface-900 border-r border-surface-700 w-48 shrink-0">
      {/* Session manager */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-surface-700">
        <span className="text-xs font-medium text-surface-400 uppercase tracking-wide">
          Sessions
        </span>
        <button
          onClick={onNewSession}
          className="text-surface-400 hover:text-accent text-lg leading-none"
          title="New script"
        >
          +
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-1">
        {sessions.length === 0 ? (
          <div className="px-3 py-2 text-xs text-surface-500 italic">No sessions yet</div>
        ) : (
          <SessionTree
            sessions={sessions}
            activeId={activeSessionId}
            onSelect={onSelectSession}
          />
        )}
      </div>

      {/* Variables panel */}
      <div className="border-t border-surface-700">
        <VariablesPanel
          variables={variables}
          onChange={onVariablesChange}
          lintResult={lintResult}
        />
      </div>

      {/* Model quick-status */}
      <div className="border-t border-surface-700 px-3 py-2">
        <div className="text-[10px] text-surface-500 uppercase tracking-wide mb-1">
          Models
        </div>
        {modelStatus ? (
          <div className="text-xs text-surface-400 space-y-0.5">
            {modelStatus.gpu_available ? (
              <div className="text-success text-[10px]">GPU ready</div>
            ) : (
              <div className="text-[10px]">CPU only</div>
            )}
            <div className="text-[10px]">{installedModelCount} installed</div>
            <div className="text-[10px]">{modelStatus.disk_used_mb.toFixed(0)} MB</div>
          </div>
        ) : (
          <div className="text-xs text-surface-500 italic">–</div>
        )}
        <button
          onClick={onOpenModelManager}
          className="mt-2 text-[10px] text-accent hover:text-accent-hover"
        >
          Manage…
        </button>
      </div>
    </div>
  );
}
