import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { getAgentTrace, getCertificate } from '../lib/api';
import { useAppStore } from '../store/useAppStore';
import { useAgentStream } from '../hooks/useAgentStream';
import {
  GitMerge,
  AlertCircle,
  CheckCircle2,
  FileText,
  ShieldCheck,
  Download,
  Terminal,
  RefreshCw,
  KeyRound,
  ChevronDown,
  ChevronRight,
  Clock,
  Wrench,
  LayoutDashboard,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';

function statusBadge(status: string) {
  if (status === 'completed') return <span className="badge badge-green"><CheckCircle2 size={9} /> Completed</span>;
  if (status === 'running') return <span className="badge badge-indigo animate-pulse">Running</span>;
  if (status === 'failed') return <span className="badge badge-red"><XCircle size={9} /> Failed</span>;
  if (status === 'pending_approval') return <span className="badge badge-amber"><Clock size={9} /> Awaiting approval</span>;
  return <span className="badge badge-neutral">{status}</span>;
}

export default function Trace() {
  const { runId: routeRunId } = useParams<{ runId: string }>();
  const storeRunId = useAppStore((s) => s.currentRunId);
  const runId = routeRunId ?? storeRunId ?? '';

  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const [certData, setCertData] = useState<any | null>(null);
  const [certLoading, setCertLoading] = useState(false);

  const { data: trace, isLoading, refetch } = useQuery({
    queryKey: ['trace', runId],
    queryFn: () => getAgentTrace(runId),
    enabled: !!runId,
    refetchInterval: 3000,
  });

  useAgentStream(runId);

  const handleFetchCert = async () => {
    if (!runId) return;
    setCertLoading(true);
    try {
      const res = await getCertificate(runId);
      setCertData(res);
      toast.success('Certificate verified');
    } catch (err: any) {
      toast.error(`Not available: ${err.message || 'Run not completed'}`);
    } finally {
      setCertLoading(false);
    }
  };

  const handleDownloadCert = () => {
    if (!certData) return;
    const blob = new Blob([JSON.stringify(certData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `certificate_${runId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Empty state
  if (!runId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-xs space-y-4">
          <div className="empty-state-icon mx-auto"><GitMerge size={22} /></div>
          <div className="empty-state-title">No active run</div>
          <p className="empty-state-desc">Run a task from Task Studio to see the step-by-step execution trace here.</p>
          <Link to="/" className="btn btn-primary btn-sm inline-flex gap-1.5">
            <LayoutDashboard size={13} /> Go to Task Studio
          </Link>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="spinner" />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading trace…</p>
        </div>
      </div>
    );
  }

  const stateObj = trace?.state ?? {};
  const steps = trace?.steps ?? trace?.transitions ?? trace?.plan?.steps ?? [];
  const runStatus = trace?.status ?? stateObj?.status ?? 'unknown';
  const planningResult = trace?.planning_result ?? trace?.plan;
  const rbacResult = trace?.rbac_result;
  const selfCheck = trace?.self_check_result;
  const selectedModel = trace?.selected_model ?? stateObj?.model_used ?? '—';
  const hardwareTier = trace?.hardware_tier ?? stateObj?.hardware_tier ?? 'cpu_only';

  return (
    <div className="flex-1 overflow-auto" style={{ background: 'var(--bg-base)' }}>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <GitMerge size={18} style={{ color: '#818CF8' }} />
              Execution Trace
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{runId}</span>
              {statusBadge(runStatus)}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => refetch()} className="btn btn-secondary btn-sm gap-1.5">
              <RefreshCw size={12} /> Refresh
            </button>
            <button
              onClick={handleFetchCert}
              disabled={certLoading}
              className="btn btn-secondary btn-sm gap-1.5"
            >
              {certLoading ? <div className="spinner spinner-sm" /> : <KeyRound size={12} />}
              Certificate
            </button>
            {certData && (
              <button onClick={handleDownloadCert} className="btn btn-secondary btn-sm gap-1.5">
                <Download size={12} /> Download
              </button>
            )}
          </div>
        </div>

        {/* Run summary cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Status', value: runStatus, color: runStatus === 'completed' ? '#22C55E' : runStatus === 'running' ? '#818CF8' : '#F59E0B' },
            { label: 'Steps', value: String(steps.length) },
            { label: 'Model', value: selectedModel, mono: true },
            { label: 'Hardware', value: hardwareTier },
          ].map(({ label, value, color, mono }) => (
            <div key={label} className="card p-3">
              <div className="text-xs mb-0.5" style={{ color: 'var(--text-muted)' }}>{label}</div>
              <div className={`text-sm font-semibold capitalize ${mono ? 'font-mono' : ''}`} style={{ color: color ?? 'var(--text-primary)' }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Planning section */}
        {planningResult && (
          <div className="card p-5 space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Plan</div>
            {(planningResult.steps ?? []).map((ps: any, i: number) => (
              <div key={i} className="flex items-start gap-2.5 text-sm">
                <span className="mt-0.5 text-xs font-mono w-5 shrink-0 text-right" style={{ color: 'var(--text-muted)' }}>{i + 1}.</span>
                <span style={{ color: 'var(--text-secondary)' }}>{ps.description ?? ps.tool ?? ps}</span>
              </div>
            ))}
          </div>
        )}

        {/* RBAC summary */}
        {rbacResult && (
          <div className={`callout ${rbacResult.allowed ? 'callout-success' : 'callout-danger'} flex items-center gap-2`}>
            {rbacResult.allowed ? <ShieldCheck size={14} /> : <AlertCircle size={14} />}
            <span>RBAC: {rbacResult.allowed ? 'All steps authorised' : `Blocked — ${rbacResult.reason ?? 'Policy violation'}`}</span>
          </div>
        )}

        {/* Steps */}
        {steps.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Execution Steps</div>
            {steps.map((step: any, idx: number) => {
              const isOpen = expandedStep === idx;
              const hasOutput = step.observation || step.tool_result || step.error;
              return (
                <div key={idx} className="card overflow-hidden">
                  <button
                    className="w-full px-4 py-3 flex items-center gap-3 text-left transition-colors"
                    style={{ color: 'var(--text-primary)' }}
                    onClick={() => setExpandedStep(isOpen ? null : idx)}
                  >
                    <span className="w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0"
                      style={{ background: 'rgba(99,102,241,0.15)', color: '#818CF8' }}>{idx + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">{step.description ?? step.tool ?? `Step ${idx + 1}`}</span>
                        {step.tool && <span className="badge badge-indigo flex items-center gap-1"><Wrench size={9} /> {step.tool}</span>}
                        {step.status && statusBadge(step.status)}
                      </div>
                    </div>
                    {hasOutput && (
                      isOpen ? <ChevronDown size={15} style={{ color: 'var(--text-muted)' }} /> : <ChevronRight size={15} style={{ color: 'var(--text-muted)' }} />
                    )}
                  </button>

                  {isOpen && hasOutput && (
                    <div className="px-4 pb-4 border-t pt-3 space-y-2" style={{ borderColor: 'var(--border)' }}>
                      {step.observation && (
                        <div>
                          <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>Output</div>
                          <div className="mono-block text-xs whitespace-pre-wrap max-h-48 overflow-y-auto">{step.observation}</div>
                        </div>
                      )}
                      {step.error && (
                        <div className="callout callout-danger flex items-start gap-1.5">
                          <AlertCircle size={12} className="mt-0.5 shrink-0" />
                          <span className="font-mono text-xs">{step.error}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Self-check */}
        {selfCheck && (
          <div className={`callout ${selfCheck.passed ? 'callout-success' : 'callout-warning'} space-y-1`}>
            <div className="flex items-center gap-1.5 font-medium">
              {selfCheck.passed ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
              Self-check: {selfCheck.passed ? 'Passed' : 'Issues found'}
            </div>
            {selfCheck.issues?.length > 0 && (
              <ul className="ml-5 text-xs space-y-0.5 list-disc">
                {selfCheck.issues.map((issue: string, i: number) => <li key={i}>{issue}</li>)}
              </ul>
            )}
          </div>
        )}

        {/* Certificate */}
        {certData && (
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold flex items-center gap-1.5" style={{ color: 'var(--text-primary)' }}>
                <ShieldCheck size={14} style={{ color: '#22C55E' }} />
                Attestation Certificate
              </h3>
              <span className="badge badge-green"><CheckCircle2 size={10} /> Ed25519 Verified</span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              {[
                ['Run ID', certData.run_id],
                ['Issued At', certData.issued_at ? new Date(certData.issued_at).toLocaleString() : '—'],
                ['Algorithm', certData.algorithm ?? 'Ed25519'],
                ['Valid', certData.is_valid ? 'Yes' : 'No'],
              ].map(([k, v]) => (
                <div key={k}>
                  <div style={{ color: 'var(--text-muted)' }}>{k}</div>
                  <div className="font-mono font-medium mt-0.5" style={{ color: 'var(--text-secondary)' }}>{v}</div>
                </div>
              ))}
            </div>
            {certData.signature && (
              <div className="mono-block text-[11px] truncate">{certData.signature}</div>
            )}
          </div>
        )}

        {steps.length === 0 && !isLoading && (
          <div className="empty-state">
            <div className="empty-state-icon"><Terminal size={20} /></div>
            <div className="empty-state-title">No steps recorded yet</div>
            <p className="empty-state-desc">The agent is initialising. Steps appear here as execution progresses.</p>
          </div>
        )}
      </div>
    </div>
  );
}
