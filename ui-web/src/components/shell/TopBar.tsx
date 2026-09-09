import React from 'react';
import { useConnectionStatus } from '../../hooks/useConnectionStatus';
import { Wifi, WifiOff, AlertCircle } from 'lucide-react';

export function TopBar() {
  const { status, errorMessage } = useConnectionStatus();

  const getStatusColor = () => {
    switch (status) {
      case 'connected':
        return 'text-sovereign-success';
      case 'connecting':
        return 'text-sovereign-warning';
      case 'disconnected':
      case 'backend_error':
      case 'stream_error':
        return 'text-sovereign-error';
      default:
        return 'text-sovereign-muted';
    }
  };

  const getStatusIcon = () => {
    if (status === 'connected') {
      return <Wifi size={16} className={getStatusColor()} />;
    }
    return <WifiOff size={16} className={getStatusColor()} />;
  };

  return (
    <header className="h-14 bg-sovereign-card border-b border-white/10 flex items-center justify-between px-4">
      <div className="flex items-center gap-2">
        {getStatusIcon()}
        <span className={`text-sm ${getStatusColor()}`}>
          {status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting...' : 'Disconnected'}
        </span>
        {errorMessage && (
          <span className="text-xs text-sovereign-muted ml-2">{errorMessage}</span>
        )}
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-sovereign-muted">SWARAJ v2.0.0</span>
      </div>
    </header>
  );
}
