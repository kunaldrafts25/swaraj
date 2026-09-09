import React from 'react';
import { ShieldCheck, ShieldAlert, Cpu } from 'lucide-react';

interface StatusBarProps {
  securityStatus?: 'clean' | 'failed';
  egressCount?: number;
  hardwareTier?: string | null;
}

export function StatusBar({ securityStatus = 'clean', hardwareTier }: StatusBarProps) {
  const ok = securityStatus === 'clean';
  return (
    <footer
      className="h-6 flex items-center justify-between px-5 text-[11px] shrink-0 select-none border-t"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          {ok
            ? <ShieldCheck size={11} className="text-green-400" />
            : <ShieldAlert size={11} style={{ color: '#EF4444' }} />
          }
          <span style={{ color: ok ? '#86EFAC' : '#FCA5A5' }}>
            {ok ? 'Network Isolated' : 'Egress Violation'}
          </span>
        </div>
        <span>•</span>
        <span>Ed25519 Attestation Active</span>
      </div>

      <div className="flex items-center gap-1.5">
        <Cpu size={11} />
        <span>{hardwareTier ?? 'CPU'} · Local Inference</span>
      </div>
    </footer>
  );
}
