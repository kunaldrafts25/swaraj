import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getApprovals, approveRequest, denyRequest } from '../lib/api';
import { SectionCard } from '../components/ui/SectionCard';
import { StatusPill } from '../components/ui/StatusPill';
import { ClipboardCheck, CheckCircle, XCircle } from 'lucide-react';

export default function Approvals() {
  const queryClient = useQueryClient();

  const { data: approvals, isLoading } = useQuery({
    queryKey: ['approvals'],
    queryFn: getApprovals,
    refetchInterval: 5000,
  });

  const approveMutation = useMutation({
    mutationFn: ({ id, comments }: { id: string; comments?: string }) =>
      approveRequest(id, 'approver_user', comments),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      toast.success('Approval granted');
    },
    onError: (error) => {
      toast.error(`Failed to approve: ${error.message}`);
    },
  });

  const denyMutation = useMutation({
    mutationFn: ({ id, comments }: { id: string; comments?: string }) =>
      denyRequest(id, 'approver_user', comments),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      toast.success('Request denied');
    },
    onError: (error) => {
      toast.error(`Failed to deny: ${error.message}`);
    },
  });

  if (isLoading) {
    return (
      <div className="flex-1 p-6">
        <p className="text-sovereign-muted">Loading approvals...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-4">
        <SectionCard title="Approval Queue">
          {approvals && approvals.length === 0 ? (
            <div className="flex items-center gap-2 text-sovereign-muted">
              <ClipboardCheck size={16} />
              <span>No pending approvals</span>
            </div>
          ) : (
            <div className="space-y-3">
              {approvals?.map((approval) => (
                <div key={approval.approval_id} className="p-4 bg-sovereign-card2 rounded-lg border border-white/10">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm text-sovereign-muted">{approval.approval_id}</span>
                      <StatusPill
                        status={approval.status === 'pending' ? 'warning' : approval.status === 'approved' ? 'success' : 'error'}
                        label={approval.status}
                      />
                    </div>
                    <span className="text-xs text-sovereign-muted">{new Date(approval.requested_at).toLocaleString()}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm mb-3">
                    <div>
                      <p className="text-sovereign-muted mb-1">User</p>
                      <span className="font-mono text-sovereign-text">{approval.user_id}</span>
                    </div>
                    <div>
                      <p className="text-sovereign-muted mb-1">Role</p>
                      <span className="font-mono text-sovereign-text">{approval.role}</span>
                    </div>
                    <div className="col-span-2">
                      <p className="text-sovereign-muted mb-1">Action</p>
                      <span className="text-sovereign-text">{approval.action}</span>
                    </div>
                    {approval.artifact && (
                      <div className="col-span-2">
                        <p className="text-sovereign-muted mb-1">Artifact</p>
                        <span className="font-mono text-sovereign-text">{approval.artifact}</span>
                      </div>
                    )}
                    <div className="col-span-2">
                      <p className="text-sovereign-muted mb-1">Policy Reason</p>
                      <p className="text-sovereign-text text-xs">{approval.policy_reason}</p>
                    </div>
                  </div>
                  {approval.status === 'pending' && (
                    <div className="flex items-center gap-2 mt-3">
                      <button
                        onClick={() => approveMutation.mutate({ id: approval.approval_id })}
                        disabled={approveMutation.isPending}
                        className="btn-primary flex items-center gap-1 text-sm py-1"
                      >
                        <CheckCircle size={14} />
                        Approve
                      </button>
                      <button
                        onClick={() => denyMutation.mutate({ id: approval.approval_id })}
                        disabled={denyMutation.isPending}
                        className="bg-sovereign-error text-white px-3 py-1 rounded-md text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-1"
                      >
                        <XCircle size={14} />
                        Deny
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
