import React, { useState, useEffect } from 'react';
import { useConnectionStatus } from '../../hooks/useConnectionStatus';
import { useAppStore } from '../../store/useAppStore';
import { Link } from 'react-router-dom';
import { Wifi, WifiOff, Activity } from 'lucide-react';

export function TopBar() {
  const { status } = useConnectionStatus();
  const currentRunId = useAppStore((s) => s.currentRunId);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const [time, setTime] = useState(() => new Date().toLocaleTimeString('en-IN', { hour12: false }));

  useEffect(() => {
    const t = setInterval(() => setTime(new Date().toLocaleTimeString('en-IN', { hour12: false })), 1000);
    return () => clearInterval(t);
  }, []);

  const connected = status === 'connected';

  return (
    <header
      className="h-12 flex items-center justify-between px-5 shrink-0 border-b"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      {/* Left */}
      <div className="flex items-center gap-4">
        <div className={`flex items-center gap-1.5 text-xs font-medium ${connected ? '' : ''}`}>
          {connected ? (
            <Wifi size={13} className="text-green-400" />
          ) : (
            <WifiOff size={13} style={{ color: '#EF4444' }} />
          )}
          <span style={{ color: connected ? '#86EFAC' : '#FCA5A5' }}>
            {connected ? 'Connected' : 'Connecting…'}
          </span>
        </div>

        {selectedModel && (
          <div className="hidden md:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md" style={{ background: 'var(--bg-base)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>
            <span style={{ color: 'var(--text-muted)' }}>Model:</span>
            <span className="font-mono font-medium" style={{ color: '#A5B4FC' }}>{selectedModel}</span>
          </div>
        )}
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        {currentRunId ? (
          <Link
            to="/trace"
            className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md transition-colors"
            style={{ background: 'rgba(99,102,241,0.1)', color: '#A5B4FC', border: '1px solid rgba(99,102,241,0.2)' }}
          >
            <Activity size={12} className="text-green-400 animate-pulse" />
            <span className="font-mono">Run {currentRunId.slice(0, 8)}</span>
          </Link>
        ) : (
          <span className="text-xs hidden sm:block" style={{ color: 'var(--text-muted)' }}>No active run</span>
        )}

        <div className="text-xs font-mono px-2 py-1 rounded-md" style={{ background: 'var(--bg-base)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
          {time}
        </div>
      </div>
    </header>
  );
}
