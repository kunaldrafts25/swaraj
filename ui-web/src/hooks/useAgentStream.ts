import { useState, useEffect, useRef } from 'react';
import type { AgentState, ConnectionStatus } from '../lib/types';

export function useAgentStream(runId: string | null) {
  const [agentState, setAgentState] = useState<AgentState | null>(null);
  const [streamStatus, setStreamStatus] = useState<ConnectionStatus>('disconnected');
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) {
      setStreamStatus('disconnected');
      return;
    }

    setStreamStatus('connecting');

    const url = `/api/agent/stream/${runId}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setStreamStatus('connected');
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AgentState;
        setAgentState(data);
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

  return { agentState, streamStatus };
}
