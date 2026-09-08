import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getAgentTrace } from '../lib/api';
import { SectionCard } from '../components/ui/SectionCard';
import { StatusPill } from '../components/ui/StatusPill';
import { GitGraph, AlertCircle, CheckCircle } from 'lucide-react';

export default function Trace() {
  const { runId = '' } = useParams<{ runId: string }>();
  
  // For demo, use a fixed runId or show message
  const { data: trace, isLoading } = useQuery({
    queryKey: ['trace', runId],
    queryFn: () => getAgentTrace(runId),
    enabled: !!runId,
  });

  if (!runId) {
    return (
      <div className="flex-1 p-6 flex items-center justify-center">
        <p className="text-sovereign-muted">No active run. Start a task from Home.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 p-6">
        <p className="text-sovereign-muted">Loading trace...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-4">
        <SectionCard title={`Trace: ${runId.slice(0, 8)}...`}>
          {trace && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-sm text-sovereign-muted">Status:</span>
                <StatusPill
                  status={trace.status === 'completed' ? 'success' : trace.status === 'failed' || trace.status === 'security_failed' ? 'error' : 'warning'}
                  label={trace.status}
                />
              </div>
              {trace.plan && (
                <div>
                  <p className="text-sm text-sovereign-muted mb-2">Plan Steps:</p>
                  <div className="space-y-1">
                    {trace.plan.steps.map((step, idx) => (
                      <div key={step.id} className={`flex items-center gap-2 p-2 rounded ${step.pruned ? 'bg-sovereign-card2 opacity-50' : 'bg-sovereign-card3'}`}>
                        <span className="font-mono text-xs text-sovereign-muted">{idx + 1}.</span>
                        <span className={`text-sm ${step.pruned ? 'line-through text-sovereign-muted' : 'text-sovereign-text'}`}>
                          {step.action}
                        </span>
                        {step.pruned && <span className="text-xs text-sovereign-error">(pruned)</span>}
                        {step.approval_required && <span className="text-xs text-sovereign-warning">(approval required)</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {trace.self_check_errors && trace.self_check_errors.length > 0 && (
                <div>
                  <p className="text-sm text-sovereign-muted mb-2">Self-Check Errors:</p>
                  <div className="space-y-1">
                    {trace.self_check_errors.map((error, idx) => (
                      <div key={idx} className="flex items-start gap-2 p-2 bg-sovereign-error/10 rounded border border-sovereign-error/20">
                        <AlertCircle size={14} className="text-sovereign-error mt-0.5" />
                        <div>
                          <p className="text-sm text-sovereign-text font-mono">{error.field}</p>
                          <p className="text-xs text-sovereign-muted">{error.issue}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex items-center gap-2">
                <span className="text-sm text-sovereign-muted">Certificate Eligible:</span>
                {trace.certificate_eligible ? (
                  <CheckCircle size={16} className="text-sovereign-success" />
                ) : (
                  <AlertCircle size={16} className="text-sovereign-error" />
                )}
              </div>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
