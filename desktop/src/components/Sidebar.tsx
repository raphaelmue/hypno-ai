/**
 * Application sidebar — session manager, variables panel, and model quick-status.
 */
import { useEffect, useRef, useState } from "react";
import type { LintResult, ModelStatus, SessionInfo, SessionVariables } from "../types";
import { VariablesPanel } from "./VariablesPanel";

function NewSessionDialog({
  onConfirm,
  onCancel,
}: {
  onConfirm: (name: string) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("New Session");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.select();
  }, []);

  const commit = () => {
    const trimmed = name.trim();
    if (trimmed) onConfirm(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") commit();
    if (e.key === "Escape") onCancel();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-surface-800 border border-surface-600 rounded-lg shadow-xl p-4 w-72 flex flex-col gap-3">
        <div className="text-sm font-medium text-surface-200">New session</div>
        <input
          ref={inputRef}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full text-sm bg-surface-900 border border-surface-600 rounded px-2 py-1.5 text-surface-100 outline-none focus:border-accent"
          placeholder="Session name"
          autoFocus
        />
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="text-xs text-surface-400 hover:text-surface-200 px-3 py-1 rounded hover:bg-surface-700"
          >
            Cancel
          </button>
          <button
            onClick={commit}
            disabled={!name.trim()}
            className="text-xs bg-accent text-white px-3 py-1 rounded hover:bg-accent-hover disabled:opacity-40"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

interface Props {
  sessions: SessionInfo[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewSession: (name: string) => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, name: string) => void;
  sessionsDir: string;
  onChangeSessionsDir: () => void;
  variables: SessionVariables;
  onVariablesChange: (v: SessionVariables) => void;
  lintResult: LintResult | null;
  modelStatus: ModelStatus | null;
  onOpenModelManager: () => void;
  installedModelCount: number;
}

function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
  onRename,
}: {
  session: SessionInfo;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (name: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(session.name);
  const inputRef = useRef<HTMLInputElement>(null);

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditName(session.name);
    setIsEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  };

  const commitEdit = () => {
    setIsEditing(false);
    const trimmed = editName.trim();
    if (trimmed && trimmed !== session.name) {
      onRename(trimmed);
    } else {
      setEditName(session.name);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") commitEdit();
    if (e.key === "Escape") {
      setEditName(session.name);
      setIsEditing(false);
    }
  };

  return (
    <div
      className={`group flex items-center gap-1 px-2 py-1 rounded cursor-pointer ${
        isActive
          ? "bg-accent/20 text-accent"
          : "text-surface-300 hover:bg-surface-700"
      }`}
      onClick={onSelect}
    >
      {isEditing ? (
        <input
          ref={inputRef}
          value={editName}
          onChange={(e) => setEditName(e.target.value)}
          onBlur={commitEdit}
          onKeyDown={handleKeyDown}
          onClick={(e) => e.stopPropagation()}
          className="flex-1 min-w-0 text-xs bg-surface-800 border border-accent/50 rounded px-1 py-0 text-surface-100 outline-none"
          autoFocus
        />
      ) : (
        <span
          className="flex-1 min-w-0 text-xs truncate"
          title={session.name}
          onDoubleClick={startEdit}
        >
          {session.name}
        </span>
      )}
      {!isEditing && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="opacity-0 group-hover:opacity-100 text-surface-500 hover:text-danger text-xs leading-none shrink-0 transition-opacity"
          title="Delete session"
        >
          ✕
        </button>
      )}
    </div>
  );
}

function SessionTree({
  sessions,
  activeId,
  onSelect,
  onDelete,
  onRename,
}: {
  sessions: SessionInfo[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, name: string) => void;
}) {
  const saved = sessions.filter((s) => !s.is_draft);
  const drafts = sessions.filter((s) => s.is_draft);

  const renderSession = (s: SessionInfo) => (
    <SessionItem
      key={s.id}
      session={s}
      isActive={s.id === activeId}
      onSelect={() => onSelect(s.id)}
      onDelete={() => onDelete(s.id)}
      onRename={(name) => onRename(s.id, name)}
    />
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
  onDeleteSession,
  onRenameSession,
  sessionsDir,
  onChangeSessionsDir,
  variables,
  onVariablesChange,
  lintResult,
  modelStatus,
  onOpenModelManager,
  installedModelCount,
}: Props) {
  const [showNewDialog, setShowNewDialog] = useState(false);

  return (
    <div className="flex flex-col h-full bg-surface-900 border-r border-surface-700 w-48 shrink-0">
      {showNewDialog && (
        <NewSessionDialog
          onConfirm={(name) => {
            setShowNewDialog(false);
            onNewSession(name);
          }}
          onCancel={() => setShowNewDialog(false)}
        />
      )}
      {/* Session manager header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-surface-700">
        <span className="text-xs font-medium text-surface-400 uppercase tracking-wide">
          Sessions
        </span>
        <button
          onClick={() => setShowNewDialog(true)}
          className="text-surface-400 hover:text-accent text-lg leading-none"
          title="New session"
        >
          +
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto py-1">
        {sessions.length === 0 ? (
          <div className="px-3 py-2 text-xs text-surface-500 italic">No sessions yet</div>
        ) : (
          <SessionTree
            sessions={sessions}
            activeId={activeSessionId}
            onSelect={onSelectSession}
            onDelete={onDeleteSession}
            onRename={onRenameSession}
          />
        )}
      </div>

      {/* Sessions directory */}
      <div className="border-t border-surface-700 px-3 py-2">
        <div className="text-[10px] text-surface-500 uppercase tracking-wide mb-1">
          Sessions folder
        </div>
        <div
          className="text-[10px] text-surface-400 truncate mb-1"
          title={sessionsDir}
        >
          {sessionsDir ? sessionsDir.replace(/^.*[/\\]/, "…/") : "—"}
        </div>
        <button
          onClick={onChangeSessionsDir}
          className="text-[10px] text-accent hover:text-accent-hover"
        >
          Change…
        </button>
      </div>

      {/* Variables panel */}
      <div className="border-t border-surface-700">
        <VariablesPanel
          variables={variables}
          onChange={onVariablesChange}
          lintResult={lintResult}
        />
      </div>

      {/* Engine quick-status */}
      <div className="border-t border-surface-700 px-3 py-2">
        <div className="text-[10px] text-surface-500 uppercase tracking-wide mb-1">
          Engines
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
