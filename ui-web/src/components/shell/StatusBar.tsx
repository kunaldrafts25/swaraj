import React from 'react';
import { Shield, AlertTriangle, XCircle } from 'lucide-react';

interface StatusBarProps {
  securityStatus?: 'clean' | 'failed';
  egressCount?: number;
  hardwareTier?: string | null;
}

export function StatusBar({ securityStatus = 'clean', egressCount = 0, hardwareTier }: StatusBarProps) {
  const getSecurityIcon = () => {
    if (securityStatus === 'clean') {
      return <Shield size={14} className="text-sovereign-success" />;
    }
    return <XCircle size={14} className="text-sovereign-error" />;
  };

  return (
    <footer className="h-8 bg-sovereign-card border-t border-white/10 flex items-center justify-between px-4 text-xs">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1">
          {getSecurityIcon()}
          <span className={securityStatus === 'clean' ? 'text-sovereign-success' : 'text-sovereign-error'}>
            {securityStatus === 'clean' ? 'SECURE' : 'SECURITY FAILED'}
          </span>
        </div>
        <div className="text-sovereign-muted">
          Egress events: <span className="font-mono text-sovereign-text">{egressCount}</span>
        </div>
      </div>
      <div className="text-sovereign-muted">
        {hardwareTier ? (
          <span>Hardware: <span className="font-mono text-sovereign-text">{hardwareTier}</span></span>
        ) : (
          <span>Hardware: <span className="text-sovereign-muted">Unknown</span></span>
        )}
      </div>
    </footer>
  );
}
