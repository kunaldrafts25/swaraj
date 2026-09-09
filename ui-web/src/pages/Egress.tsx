import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getEgressStatus } from '../lib/api';
import { SectionCard } from '../components/ui/SectionCard';
import { StatusPill } from '../components/ui/StatusPill';
import { Activity, Shield, AlertTriangle } from 'lucide-react';

// Mock hook since backend SSE not fully wired yet
function useMockEgress() {
  const [events, setEvents] = React.useState<Array<{ type: string; timestamp: string; is_loopback: boolean }>>([]);
  
  React.useEffect(() => {
    const interval = setInterval(() => {
      setEvents(prev => [...prev.slice(-9), {
        type: 'heartbeat',
        timestamp: new Date().toISOString(),
        is_loopback: true,
      }]);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return { events, status: 'clean' as const };
}

export default function Egress() {
  const { events, status } = useMockEgress();

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-4">
        <SectionCard title="Egress Monitor">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              {status === 'clean' ? (
                <Shield size={20} className="text-sovereign-success" />
              ) : (
                <AlertTriangle size={20} className="text-sovereign-error" />
              )}
              <StatusPill
                status={status === 'clean' ? 'success' : 'error'}
                label={status === 'clean' ? 'SECURE - No forbidden egress' : 'SECURITY ALERT'}
                size="md"
              />
            </div>
            
            <div>
              <p className="text-sm text-sovereign-muted mb-2">Recent Events ({events.length})</p>
              <div className="space-y-1 max-h-64 overflow-auto">
                {events.length === 0 ? (
                  <p className="text-sm text-sovereign-muted">No events recorded</p>
                ) : (
                  events.map((event, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2 bg-sovereign-card2 rounded">
                      <div className="flex items-center gap-2">
                        <Activity size={14} className="text-sovereign-info" />
                        <span className="text-xs font-mono text-sovereign-text">{event.type}</span>
                      </div>
                      <span className="text-xs text-sovereign-muted">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
