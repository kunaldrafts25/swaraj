import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getEgressStatus } from '../lib/api';
import { useEgressStream } from '../hooks/useEgressStream';
import { useAppStore } from '../store/useAppStore';
import {
  Radio,
  ShieldCheck,
  ShieldAlert,
  WifiOff,
  Search,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  Clock,
  Filter,
} from 'lucide-react';
import { toast } from 'sonner';

type FilterType = 'all' | 'loopback' | 'alerts';

export default function Egress() {
  const currentRunId = useAppStore((s) => s.currentRunId);
  const runId = currentRunId ?? 'global';

  const [filterType, setFilterType] = useState<FilterType>('all');
  const [search, setSearch] = useState('');

  const { egressStatus, eventCount } = useEgressStream(runId);

  const { data: statusData, refetch } = useQuery({
    queryKey: ['egress-status', runId],
    queryFn: () => getEgressStatus(runId),
    refetchInterval: 4000,
  });

  const status = egressStatus ?? statusData;
  const securityOk = (status?.security_status ?? 'clean') === 'clean';
  const killSwitch = status?.kill_switch_triggered ?? false;
  const events: any[] = status?.events ?? [];
  const isSafe = securityOk && !killSwitch;

  const filtered = events.filter((e) => {
    if (filterType === 'loopback' && !e.is_loopback) return false;
    if (filterType === 'alerts' && e.event_type !== 'security_alert') return false;
    if (search) {
      const hay = `${e.address ?? ''} ${e.event_type ?? ''} ${e.port ?? ''}`.toLowerCase();
      if (!hay.includes(search.toLowerCase())) return false;
    }
    return true;
  });

  return (
    <div className="flex-1 overflow-auto" style={{ background: 'var(--bg-base)' }}>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Radio size={18} style={{ color: '#818CF8' }} />
            Network Monitor
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            All network activity is monitored. The system is designed to run fully offline.
          </p>
        </div>

        {/* Status banner */}
        <div
          className="card p-5 flex items-center gap-4"
          style={{
            borderColor: isSafe ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.25)',
            background: isSafe ? 'rgba(34,197,94,0.05)' : 'rgba(239,68,68,0.06)',
          }}
        >
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
            style={{
              background: isSafe ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.12)',
              border: `1px solid ${isSafe ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.3)'}`,
            }}
          >
            {killSwitch ? (
              <WifiOff size={22} style={{ color: '#EF4444' }} />
            ) : isSafe ? (
              <ShieldCheck size={22} className="text-green-400" />
            ) : (
              <ShieldAlert size={22} style={{ color: '#EF4444' }} />
            )}
          </div>

          <div className="flex-1">
            <div className="font-semibold text-sm" style={{ color: isSafe ? '#86EFAC' : '#FCA5A5' }}>
              {killSwitch
                ? 'Kill switch activated — all network blocked'
                : isSafe
                ? 'System isolated — no outbound traffic detected'
                : 'Security alert — unexpected network activity'}
            </div>
            <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {events.length} total events · {eventCount} streamed
            </div>
          </div>

          <button onClick={() => refetch()} className="btn btn-secondary btn-sm gap-1.5">
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Total Events', value: events.length },
            { label: 'Loopback', value: events.filter((e) => e.is_loopback).length, color: '#818CF8' },
            { label: 'Alerts', value: events.filter((e) => e.event_type === 'security_alert').length, color: '#EF4444' },
            { label: 'Run', value: runId === 'global' ? 'Global' : runId.slice(0, 8) + '…', mono: true },
          ].map(({ label, value, color, mono }) => (
            <div key={label} className="card p-3">
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</div>
              <div className={`text-lg font-bold mt-0.5 ${mono ? 'font-mono text-sm' : ''}`} style={{ color: color ?? 'var(--text-primary)' }}>
                {value}
              </div>
            </div>
          ))}
        </div>

        {/* Filter + search */}
        <div className="flex items-center gap-3 flex-wrap">
          {(['all', 'loopback', 'alerts'] as FilterType[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilterType(f)}
              className="btn btn-sm capitalize"
              style={{
                background: filterType === f ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
                color: filterType === f ? '#A5B4FC' : 'var(--text-secondary)',
                border: `1px solid ${filterType === f ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
              }}
            >
              <Filter size={11} /> {f}
            </button>
          ))}
          <div className="relative flex-1 min-w-0" style={{ maxWidth: 260 }}>
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search events…"
              className="input pl-8 text-sm"
              style={{ paddingTop: '0.4rem', paddingBottom: '0.4rem' }}
            />
          </div>
        </div>

        {/* Events table */}
        {filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon"><CheckCircle2 size={20} /></div>
            <div className="empty-state-title">No events</div>
            <p className="empty-state-desc">
              {isSafe ? 'Network is clean — no outbound connections recorded.' : 'No events match the current filter.'}
            </p>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}>
                    {['Type', 'Address', 'Port', 'Loopback', 'Direction', 'Time'].map((h) => (
                      <th key={h} className="text-left px-4 py-2.5 font-medium" style={{ color: 'var(--text-muted)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 100).map((e, i) => (
                    <tr
                      key={i}
                      className="border-b transition-colors"
                      style={{ borderColor: 'var(--border)' }}
                      onMouseEnter={el => (el.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                      onMouseLeave={el => (el.currentTarget.style.background = 'transparent')}
                    >
                      <td className="px-4 py-2">
                        {e.event_type === 'security_alert' ? (
                          <span className="badge badge-red flex items-center gap-1 w-fit"><AlertTriangle size={9} /> Alert</span>
                        ) : (
                          <span className="badge badge-neutral">{e.event_type ?? 'event'}</span>
                        )}
                      </td>
                      <td className="px-4 py-2 font-mono" style={{ color: 'var(--text-secondary)' }}>{e.address ?? '—'}</td>
                      <td className="px-4 py-2 font-mono" style={{ color: 'var(--text-muted)' }}>{e.port ?? '—'}</td>
                      <td className="px-4 py-2">
                        {e.is_loopback
                          ? <span className="text-green-400">✓</span>
                          : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                      </td>
                      <td className="px-4 py-2" style={{ color: 'var(--text-muted)' }}>
                        {e.direction === 'outbound' ? (
                          <span className="flex items-center gap-1" style={{ color: '#FCA5A5' }}><ArrowUpRight size={11} /> Out</span>
                        ) : 'In'}
                      </td>
                      <td className="px-4 py-2 font-mono" style={{ color: 'var(--text-muted)' }}>
                        {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filtered.length > 100 && (
              <div className="px-4 py-2 text-xs text-center border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                Showing 100 of {filtered.length} events
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
