import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getApprovals, approveRequest, denyRequest } from '../lib/api';
import {
  ClipboardList,
  CheckCircle,
  XCircle,
  Clock,
  User,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileText,
  Info,
  ShieldCheck,
} from 'lucide-react';

const REVIEWERS = [
  { id: 'approver_user', label: 'K. Sharma — Operations Head' },
  { id: 'admin_user', label: 'Root Administrator' },
];

type Filter = 'all' | 'pending' | 'decided';

export default function Approvals() {
  const qc = useQueryClient();
  const [reviewerId, setReviewerId] = useState('approver_user');
  const [comments, setComments] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState<Filter>('all');

  const { data: approvals, isLoading } = useQuery({
    queryKey: ['approvals'],
    queryFn: getApprovals,
    refetchInterval: 5000,
  });

  const approveMutation = useMutation({
    mutationFn: ({ id }: { id: string }) =>
      approveRequest(id, reviewerId, comments[id]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['approvals'] });
      toast.success('Request approved');
    },
    onError: (e: any) => toast.error(`Approval failed: ${e.message}`),
  });

  const denyMutation = useMutation({
    mutationFn: ({ id }: { id: string }) =>
      denyRequest(id, reviewerId, comments[id]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['approvals'] });
      toast.success('Request denied');
    },
    onError: (e: any) => toast.error(`Denial failed: ${e.message}`),
  });

  const toggleExpanded = (id: string) =>
    setExpanded((p) => ({ ...p, [id]: !p[id] }));

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="spinner" />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading approval queue…</p>
        </div>
      </div>
    );
  }

  const all = approvals ?? [];
  const pending = all.filter((a) => a.status === 'pending');
  const decided = all.filter((a) => a.status !== 'pending');
  const shown = filter === 'pending' ? pending : filter === 'decided' ? decided : all;

  return (
    <div className="flex-1 overflow-auto" style={{ background: 'var(--bg-base)' }}>
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <ClipboardList size={18} style={{ color: '#818CF8' }} />
              Approvals
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
              Review and authorise AI actions that require human sign-off.
            </p>
          </div>

          {/* Reviewer selector */}
          <div className="shrink-0">
            <label className="label">Reviewing as</label>
            <select
              id="reviewer-select"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              className="input text-sm"
              style={{ minWidth: '220px' }}
            >
              {REVIEWERS.map((r) => (
                <option key={r.id} value={r.id}>{r.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Pending', count: pending.length, color: '#F59E0B', active: filter === 'pending' },
            { label: 'Decided', count: decided.length, color: '#22C55E', active: filter === 'decided' },
            { label: 'Total', count: all.length, color: 'var(--text-secondary)', active: filter === 'all' },
          ].map(({ label, count, color, active }) => (
            <button
              key={label}
              onClick={() => setFilter(label.toLowerCase() as Filter)}
              className="card p-4 text-left transition-all"
              style={{ borderColor: active ? 'rgba(99,102,241,0.35)' : undefined }}
            >
              <div className="text-2xl font-bold" style={{ color }}>{count}</div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{label}</div>
            </button>
          ))}
        </div>

        {/* Empty state */}
        {shown.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">
              <ShieldCheck size={20} />
            </div>
            <div className="empty-state-title">
              {filter === 'pending' ? 'No pending approvals' : 'Nothing to show'}
            </div>
            <p className="empty-state-desc">
              {filter === 'pending'
                ? 'All AI actions are running autonomously or awaiting execution.'
                : 'No approval records match this filter.'}
            </p>
          </div>
        )}

        {/* Approval cards */}
        <div className="space-y-3">
          {shown.map((item: any) => {
            const isPending = item.status === 'pending';
            const isOpen = expanded[item.approval_id];

            return (
              <div
                key={item.approval_id}
                className="card overflow-hidden"
                style={{ borderColor: isPending ? 'rgba(245,158,11,0.2)' : 'var(--border)' }}
              >
                {/* Card header */}
                <div className="px-5 py-4 flex items-start gap-4">
                  {/* Status icon */}
                  <div className="mt-0.5 shrink-0">
                    {isPending ? (
                      <Clock size={18} style={{ color: '#F59E0B' }} />
                    ) : item.status === 'approved' ? (
                      <CheckCircle size={18} className="text-green-400" />
                    ) : (
                      <XCircle size={18} style={{ color: '#EF4444' }} />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                        {item.step_description || item.tool_call || 'Action requires approval'}
                      </span>
                      <span className={`badge ${isPending ? 'badge-amber' : item.status === 'approved' ? 'badge-green' : 'badge-red'}`}>
                        {item.status}
                      </span>
                      {item.risk_level && (
                        <span className="badge badge-neutral flex items-center gap-1">
                          <AlertTriangle size={9} />
                          {item.risk_level} risk
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 mt-1.5 text-xs flex-wrap" style={{ color: 'var(--text-muted)' }}>
                      {item.run_id && (
                        <span className="flex items-center gap-1">
                          <FileText size={10} />
                          Run: <span className="font-mono">{item.run_id.slice(0, 10)}</span>
                        </span>
                      )}
                      {item.user_id && (
                        <span className="flex items-center gap-1">
                          <User size={10} />
                          {item.user_id}
                        </span>
                      )}
                      {item.created_at && (
                        <span>
                          {new Date(item.created_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                        </span>
                      )}
                    </div>

                    {item.policy_reason && (
                      <div className="callout callout-warning mt-2 flex items-start gap-1.5">
                        <Info size={12} className="mt-0.5 shrink-0" style={{ color: '#F59E0B' }} />
                        <span>{item.policy_reason}</span>
                      </div>
                    )}
                  </div>

                  {/* Expand toggle */}
                  <button
                    onClick={() => toggleExpanded(item.approval_id)}
                    className="p-1.5 rounded-md transition-colors shrink-0"
                    style={{ color: 'var(--text-muted)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                </div>

                {/* Expanded: approve/deny controls */}
                {isOpen && isPending && (
                  <div className="px-5 pb-4 border-t pt-4 space-y-3" style={{ borderColor: 'var(--border)' }}>
                    <div>
                      <label className="label">Comment (optional)</label>
                      <textarea
                        value={comments[item.approval_id] ?? ''}
                        onChange={(e) =>
                          setComments((p) => ({ ...p, [item.approval_id]: e.target.value }))
                        }
                        placeholder="Add a note about your decision…"
                        className="input"
                        style={{ minHeight: '72px', resize: 'vertical' }}
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        id={`approve-btn-${item.approval_id}`}
                        onClick={() => approveMutation.mutate({ id: item.approval_id })}
                        disabled={approveMutation.isPending || denyMutation.isPending}
                        className="btn btn-success btn-sm gap-1.5"
                      >
                        <CheckCircle size={13} />
                        Approve
                      </button>
                      <button
                        id={`deny-btn-${item.approval_id}`}
                        onClick={() => denyMutation.mutate({ id: item.approval_id })}
                        disabled={approveMutation.isPending || denyMutation.isPending}
                        className="btn btn-danger btn-sm gap-1.5"
                      >
                        <XCircle size={13} />
                        Deny
                      </button>
                    </div>
                  </div>
                )}

                {/* Decided info */}
                {isOpen && !isPending && item.reviewer_comment && (
                  <div className="px-5 pb-4 border-t pt-4" style={{ borderColor: 'var(--border)' }}>
                    <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Reviewer note</div>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{item.reviewer_comment}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
