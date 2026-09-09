import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRegistry } from '../lib/api';
import {
  Box,
  HardDrive,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Cpu,
  BarChart2,
  Hash,
  Layers,
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';

const CAPABILITY_COLORS = ['#6366F1', '#818CF8', '#A78BFA', '#7C3AED', '#4F46E5'];

function ScoreBars({ capabilities }: { capabilities: Record<string, number> }) {
  const data = Object.entries(capabilities)
    .map(([name, score]) => ({ name: name.replace(/_/g, ' '), score: Math.round(score * 100) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);

  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={data} layout="vertical" margin={{ left: 0, right: 8, top: 0, bottom: 0 }}>
        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#545E75' }} tickLine={false} axisLine={false} />
        <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 10, fill: '#8B93A8' }} tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{ background: '#1C2333', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: '#EDF0F7' }}
          itemStyle={{ color: '#818CF8' }}
          formatter={(v: number) => [`${v}%`, 'Score']}
        />
        {data.map((_, i) => (
          <Bar key={i} dataKey="score" radius={3}>
            <Cell fill={CAPABILITY_COLORS[i % CAPABILITY_COLORS.length]} fillOpacity={0.85} />
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function checksumBadge(status: string) {
  if (status === 'verified' || status === 'match') return <span className="badge badge-green"><CheckCircle2 size={10} /> Verified</span>;
  if (status === 'placeholder') return <span className="badge badge-amber"><AlertCircle size={10} /> Placeholder</span>;
  if (status === 'mismatch') return <span className="badge badge-red"><XCircle size={10} /> Mismatch</span>;
  if (status === 'missing') return <span className="badge badge-red"><XCircle size={10} /> Missing</span>;
  return <span className="badge badge-neutral">{status}</span>;
}

export default function Registry() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['registry'],
    queryFn: getRegistry,
    refetchInterval: 15000,
  });

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="spinner" />
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading model registry…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-8">
        <div className="callout callout-danger flex items-center gap-2">
          <AlertCircle size={16} />
          <span>{(error as Error).message}</span>
        </div>
      </div>
    );
  }

  const models = data?.models ?? [];
  const verified = models.filter((m: any) => m.verified).length;

  return (
    <div className="flex-1 overflow-auto" style={{ background: 'var(--bg-base)' }}>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Box size={18} style={{ color: '#818CF8' }} />
              Model Registry
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
              All AI models are stored locally. SHA-256 checksums verified before use.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="badge badge-indigo">
              <Box size={10} /> {models.length} models
            </span>
            <span className={`badge ${verified > 0 ? 'badge-green' : 'badge-amber'}`}>
              <CheckCircle2 size={10} /> {verified} verified
            </span>
          </div>
        </div>

        {/* Model cards */}
        {models.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon"><Box size={20} /></div>
            <div className="empty-state-title">No models loaded</div>
            <p className="empty-state-desc">Add a GGUF model manifest to the registry manifests directory.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {models.map((m: any, idx: number) => (
              <div key={m.model_id ?? idx} className="card overflow-hidden">
                {/* Card header */}
                <div className="px-5 py-4 flex items-start gap-4 border-b" style={{ borderColor: 'var(--border)' }}>
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.2)' }}>
                    <Cpu size={18} style={{ color: '#818CF8' }} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{m.name ?? m.model_id}</span>
                      {m.verified
                        ? <span className="badge badge-green"><CheckCircle2 size={10} /> Verified</span>
                        : <span className="badge badge-amber"><AlertCircle size={10} /> Not verified</span>
                      }
                      {m.hardware_tier && <span className="badge badge-neutral"><Cpu size={9} /> {m.hardware_tier}</span>}
                    </div>

                    {m.description && (
                      <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--text-muted)' }}>{m.description}</p>
                    )}

                    <div className="flex items-center gap-3 mt-1.5 text-xs flex-wrap" style={{ color: 'var(--text-muted)' }}>
                      {m.parameter_count && (
                        <span className="flex items-center gap-1"><Layers size={10} /> {m.parameter_count}</span>
                      )}
                      {m.quantization && (
                        <span className="flex items-center gap-1"><BarChart2 size={10} /> {m.quantization}</span>
                      )}
                      {m.file_size_gb && (
                        <span className="flex items-center gap-1"><HardDrive size={10} /> {m.file_size_gb} GB</span>
                      )}
                      <span>{checksumBadge(m.checksum_status)}</span>
                    </div>
                  </div>
                </div>

                {/* Capability bars */}
                {m.capabilities && Object.keys(m.capabilities).length > 0 && (
                  <div className="px-5 py-4">
                    <div className="text-xs font-medium mb-3" style={{ color: 'var(--text-muted)' }}>Capability Scores</div>
                    <ScoreBars capabilities={m.capabilities} />
                  </div>
                )}

                {/* SHA */}
                {m.sha256 && (
                  <div className="px-5 pb-4 pt-0">
                    <div className="mono-block flex items-center gap-2">
                      <Hash size={11} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                      <span className="text-[11px] truncate">{m.sha256}</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
