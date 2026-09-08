import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getHealth, decideRouter, startAgentRun, getHardwareStatus } from '../lib/api';
import { useAppStore } from '../store/useAppStore';
import { SectionCard } from '../components/ui/SectionCard';
import { StatusPill } from '../components/ui/StatusPill';
import { MonoValue } from '../components/ui/MonoValue';
import { Send, FileCheck, AlertCircle } from 'lucide-react';

export default function Home() {
  const [taskDescription, setTaskDescription] = useState('');
  const setCurrentRunId = useAppStore((state) => state.setCurrentRunId);
  const setSelectedModel = useAppStore((state) => state.setSelectedModel);
  const setHardwareTier = useAppStore((state) => state.setHardwareTier);

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 5000,
  });

  const { data: hardware } = useQuery({
    queryKey: ['hardware'],
    queryFn: getHardwareStatus,
    refetchInterval: 10000,
  });

  const routerMutation = useMutation({
    mutationFn: (desc: string) => decideRouter(desc, undefined),
    onSuccess: (data) => {
      setSelectedModel(data.selected_model);
      setHardwareTier(data.hardware_tier);
      toast.success('Routing decision received');
    },
    onError: (error) => {
      toast.error(`Routing failed: ${error.message}`);
    },
  });

  const agentMutation = useMutation({
    mutationFn: async () => {
      const result = await startAgentRun(taskDescription, 'inspector_user', 'Inspector');
      setCurrentRunId(result.run_id);
      return result;
    },
    onSuccess: () => {
      toast.success('Agent run started');
    },
    onError: (error) => {
      toast.error(`Agent execution failed: ${error.message}`);
    },
  });

  const handleSubmit = async () => {
    if (!taskDescription.trim()) {
      toast.error('Please enter a task description');
      return;
    }

    // First get routing decision
    routerMutation.mutate(taskDescription);

    // Then start agent run
    agentMutation.mutate();
  };

  if (healthLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sovereign-muted">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-6">
        <SectionCard title="Task Input">
          <textarea
            value={taskDescription}
            onChange={(e) => setTaskDescription(e.target.value)}
            placeholder="Describe your task (e.g., 'Generate approval note from refinery inspection report')"
            className="input-field w-full h-32 resize-none mb-4"
          />
          <button
            onClick={handleSubmit}
            disabled={routerMutation.isPending || agentMutation.isPending}
            className="btn-primary flex items-center gap-2"
          >
            <Send size={16} />
            {agentMutation.isPending ? 'Starting...' : 'Execute Task'}
          </button>
        </SectionCard>

        {health && (
          <SectionCard title="System Status">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Registry Ready</p>
                <StatusPill
                  status={health.registry_ready ? 'success' : 'error'}
                  label={health.registry_ready ? 'Yes' : 'No'}
                />
              </div>
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Fail-Closed State</p>
                <StatusPill
                  status={health.fail_closed ? 'warning' : 'success'}
                  label={health.fail_closed ? 'Active' : 'Inactive'}
                />
              </div>
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Model Artifact</p>
                <StatusPill
                  status={health.model_artifact_present ? 'success' : 'error'}
                  label={health.model_artifact_present ? 'Present' : 'Missing'}
                />
              </div>
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Checksum State</p>
                <span className="font-mono text-sm text-sovereign-text">{health.checksum_verification_state}</span>
              </div>
            </div>
          </SectionCard>
        )}

        {hardware && (
          <SectionCard title="Hardware Tier">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Tier</p>
                <span className="font-mono text-sm text-sovereign-text">{hardware.tier}</span>
              </div>
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Calibrated</p>
                <StatusPill
                  status={hardware.calibrated ? 'success' : 'warning'}
                  label={hardware.calibrated ? 'Yes' : 'No'}
                />
              </div>
              {hardware.measured_latency_ms_per_500_tokens && (
                <div>
                  <p className="text-sm text-sovereign-muted mb-1">Measured Latency</p>
                  <MonoValue value={`${hardware.measured_latency_ms_per_500_tokens} ms/500 tokens`} />
                </div>
              )}
            </div>
          </SectionCard>
        )}

        {routerMutation.data && (
          <SectionCard title="Routing Decision">
            <div className="space-y-3">
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Selected Model</p>
                <MonoValue value={routerMutation.data.selected_model} />
              </div>
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Confidence</p>
                <span className="font-mono text-sm text-sovereign-text">{(routerMutation.data.confidence * 100).toFixed(1)}%</span>
              </div>
              <div>
                <p className="text-sm text-sovereign-muted mb-1">Reasoning</p>
                <p className="text-sm text-sovereign-text">{routerMutation.data.reasoning}</p>
              </div>
            </div>
          </SectionCard>
        )}
      </div>
    </div>
  );
}
