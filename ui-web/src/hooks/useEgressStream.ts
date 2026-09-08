import { useState, useEffect, useRef } from 'react';
import type { EgressStatus, ConnectionStatus } from '../lib/types';

export function useEgressStream(runId: string | null) {
  const [egressStatus, setEgressStatus] = useState<EgressStatus | null>(null);
  const [streamStatus, setStreamStatus] = useState<ConnectionStatus>('disconnected');
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) {
      setStreamStatus('disconnected');
      return;
    }

    setStreamStatus('connecting');

    const url = `/api/egress/stream?run_id=${runId}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setStreamStatus('connected');
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as EgressStatus;
        setEgressStatus(data);
      } catch {
        // Ignore parse errors
      }
    };

    eventSource.onerror = () => {
      setStreamStatus('stream_error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [runId]);

  return { egressStatus, streamStatus, eventCount: egressStatus?.event_count ?? 0 };
}
