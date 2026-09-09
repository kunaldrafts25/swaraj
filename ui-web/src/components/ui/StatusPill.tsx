import React from 'react';

type StatusType = 'success' | 'warning' | 'error' | 'neutral' | 'info' | 'purple';

interface StatusPillProps {
  status: StatusType | string;
  label: string;
  size?: 'sm' | 'md';
  showDot?: boolean;
}

export function StatusPill({ status, label, size = 'sm', showDot = true }: StatusPillProps) {
  const getStyles = () => {
    switch (status) {
      case 'success':
        return {
          container: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25 shadow-sm shadow-emerald-500/10',
          dot: 'bg-emerald-400',
        };
      case 'warning':
        return {
          container: 'bg-amber-500/10 text-amber-400 border-amber-500/25 shadow-sm shadow-amber-500/10',
          dot: 'bg-amber-400',
        };
      case 'error':
        return {
          container: 'bg-rose-500/10 text-rose-400 border-rose-500/25 shadow-sm shadow-rose-500/10',
          dot: 'bg-rose-400',
        };
      case 'info':
        return {
          container: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/25 shadow-sm shadow-cyan-500/10',
          dot: 'bg-cyan-400',
        };
      case 'purple':
        return {
          container: 'bg-purple-500/10 text-purple-400 border-purple-500/25 shadow-sm shadow-purple-500/10',
          dot: 'bg-purple-400',
        };
      default:
        return {
          container: 'bg-slate-800/60 text-slate-300 border-slate-700/50',
          dot: 'bg-slate-400',
        };
    }
  };

  const { container, dot } = getStyles();
  const sizeClass = size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3.5 py-1 text-sm';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${container} ${sizeClass} font-medium tracking-wide transition-all`}
    >
      {showDot && <span className={`w-1.5 h-1.5 rounded-full ${dot} animate-pulse`} />}
      <span>{label}</span>
    </span>
  );
}
