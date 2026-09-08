import React from 'react';

type StatusType = 'success' | 'warning' | 'error' | 'neutral';

interface StatusPillProps {
  status: StatusType;
  label: string;
  size?: 'sm' | 'md';
}

export function StatusPill({ status, label, size = 'sm' }: StatusPillProps) {
  const getColorClass = () => {
    switch (status) {
      case 'success':
        return 'bg-sovereign-success/10 text-sovereign-success border-sovereign-success/20';
      case 'warning':
        return 'bg-sovereign-warning/10 text-sovereign-warning border-sovereign-warning/20';
      case 'error':
        return 'bg-sovereign-error/10 text-sovereign-error border-sovereign-error/20';
      default:
        return 'bg-sovereign-card3 text-sovereign-muted border-white/10';
    }
  };

  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span className={`inline-flex items-center rounded-full border ${getColorClass()} ${sizeClass} font-medium`}>
      {label}
    </span>
  );
}
