import { useState, useEffect } from 'react';
import type { ConnectionStatus } from '../lib/types';
import { getHealth } from '../lib/api';

export function useConnectionStatus() {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [lastCheck, setLastCheck] = useState<Date | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const checkConnection = async () => {
      try {
        const health = await getHealth();
        if (mounted) {
          if (health.status === 'healthy' && !health.fail_closed) {
            setStatus('connected');
          } else if (health.status === 'degraded') {
            setStatus('connected'); // Still connected but degraded
          } else {
            setStatus('backend_error');
          }
          setLastCheck(new Date());
          setErrorMessage(null);
        }
      } catch (error) {
        if (mounted) {
          setStatus('disconnected');
          setErrorMessage(error instanceof Error ? error.message : 'Connection failed');
          setLastCheck(new Date());
        }
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 5000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { status, lastCheck, errorMessage };
}
