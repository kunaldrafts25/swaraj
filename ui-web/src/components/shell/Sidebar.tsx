import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  MessageSquarePlus,
  MessageSquare,
  Radio,
  Box,
  ClipboardList,
  ShieldCheck,
  Cpu,
  Zap,
  GitMerge,
  Trash2,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getApprovals } from '../../lib/api';
import { useAppStore } from '../../store/useAppStore';
import {
  ChatSession,
  getStoredSessions,
  getActiveSessionId,
  setActiveSessionId,
  createNewSession,
  deleteSession,
  getUserRole,
} from '../../lib/chatStorage';

const navItems = [
  {
    path: '/',
    label: 'Chat',
    icon: MessageSquare,
  },
  {
    path: '/approvals',
    label: 'Approvals',
    icon: ClipboardList,
  },
  {
    path: '/egress',
    label: 'Network Monitor',
    icon: Radio,
  },
  {
    path: '/registry',
    label: 'Model Registry',
    icon: Box,
  },
  {
    path: '/trace',
    label: 'Traces',
    icon: GitMerge,
  },
];

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const currentRunId = useAppStore((s) => s.currentRunId);
  const hardwareTier = useAppStore((s) => s.hardwareTier);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionIdState] = useState<string | null>(getActiveSessionId());
  const userRole = getUserRole();

  const reloadSessions = () => {
    setSessions(getStoredSessions());
    setActiveSessionIdState(getActiveSessionId());
  };

  useEffect(() => {
    reloadSessions();
    const interval = setInterval(reloadSessions, 2000);
    return () => clearInterval(interval);
  }, []);

  const { data: approvals } = useQuery({
    queryKey: ['approvals'],
    queryFn: getApprovals,
    refetchInterval: 8000,
  });

  const pendingCount = (approvals ?? []).filter((a: any) => a.status === 'pending').length;

  const handleSelectSession = (id: string) => {
    setActiveSessionId(id);
    setActiveSessionIdState(id);
    window.dispatchEvent(new StorageEvent('storage', { key: 'swaraj_active_session_id_v1', newValue: id }));
    if (location.pathname !== '/') {
      navigate('/');
    }
  };

  const handleNewChat = () => {
    const s = createNewSession(userRole);
    setActiveSessionId(s.id);
    setActiveSessionIdState(s.id);
    setSessions(getStoredSessions());
    window.dispatchEvent(new StorageEvent('storage', { key: 'swaraj_active_session_id_v1', newValue: s.id }));
    if (location.pathname !== '/') {
      navigate('/');
    }
  };

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteSession(id);
    reloadSessions();
    window.dispatchEvent(new StorageEvent('storage', { key: 'swaraj_active_session_id_v1', newValue: getActiveSessionId() }));
  };

  return (
    <aside
      className="w-64 shrink-0 flex flex-col border-r h-full overflow-hidden"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      {/* Brand Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-indigo-600 shadow-sm">
            <ShieldCheck size={16} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              SWARAJ AI
            </div>
            <div className="text-[10px] text-emerald-400 font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Sovereign Offline
            </div>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 transition-all shadow-sm"
        >
          <MessageSquarePlus size={15} />
          <span>New Conversation</span>
        </button>
      </div>

      {/* Recent Chats Section (Local Storage Memory) */}
      <div className="flex-1 flex flex-col min-h-0 px-3">
        <div className="text-[11px] font-medium uppercase tracking-wider px-2 py-1.5" style={{ color: 'var(--text-muted)' }}>
          Recent Memory ({sessions.length})
        </div>

        <div className="flex-1 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
          {sessions.length === 0 ? (
            <div className="px-2 py-4 text-center text-xs text-muted">
              No previous chats in memory.
            </div>
          ) : (
            sessions.map((s) => {
              const isActive = s.id === activeSessionId && location.pathname === '/';
              return (
                <div
                  key={s.id}
                  onClick={() => handleSelectSession(s.id)}
                  className={`group flex items-center justify-between px-2.5 py-2 rounded-lg text-xs cursor-pointer transition-colors ${
                    isActive
                      ? 'bg-indigo-600/15 text-indigo-300 font-medium border border-indigo-500/30'
                      : 'text-zinc-300 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <MessageSquare size={13} className="shrink-0 text-zinc-500 group-hover:text-zinc-300" />
                    <span className="truncate">{s.title || 'Untitled conversation'}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteSession(e, s.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 text-zinc-400 hover:text-red-400 transition-all shrink-0 ml-1"
                    title="Delete from memory"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* System Navigation */}
      <div className="px-3 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="text-[11px] font-medium uppercase tracking-wider px-2 py-1 text-muted">
          Workspace
        </div>
        <nav className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isApprovals = item.path === '/approvals';
            const isTrace = item.path === '/trace';

            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                    isActive
                      ? 'bg-white/10 text-white font-medium'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'
                  }`
                }
              >
                <Icon size={14} className="shrink-0" />
                <span className="flex-1 truncate">{item.label}</span>

                {isApprovals && pendingCount > 0 && (
                  <span className="bg-amber-500/20 text-amber-300 text-[10px] font-mono px-1.5 py-0.5 rounded-full">
                    {pendingCount}
                  </span>
                )}
                {isTrace && currentRunId && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Hardware / Sovereign containment footer */}
      <div className="p-3 mt-1">
        <div
          className="p-2.5 rounded-xl border text-xs space-y-1.5"
          style={{ background: 'var(--bg-base)', borderColor: 'var(--border)' }}
        >
          <div className="flex items-center justify-between text-[11px]">
            <span className="flex items-center gap-1.5 text-zinc-400">
              <Cpu size={12} />
              Compute
            </span>
            <span className="font-mono text-indigo-400 font-medium">
              {hardwareTier ? hardwareTier.replace('_', ' ') : 'CPU'}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <span className="flex items-center gap-1.5 text-zinc-400">
              <Zap size={12} />
              Persona
            </span>
            <span className="capitalize text-zinc-300 font-medium">{userRole}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
