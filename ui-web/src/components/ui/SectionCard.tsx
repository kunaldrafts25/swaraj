import React from 'react';
import { LucideIcon } from 'lucide-react';

interface SectionCardProps {
  title: React.ReactNode;
  subtitle?: string;
  icon?: LucideIcon;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function SectionCard({
  title,
  subtitle,
  icon: Icon,
  badge,
  actions,
  children,
  className = '',
}: SectionCardProps) {
  return (
    <div className={`glass-card p-5 ${className}`}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-2.5">
          {Icon && (
            <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 shadow-sm shadow-cyan-500/10">
              <Icon size={16} />
            </div>
          )}
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold tracking-wide text-slate-100 uppercase">
                {title}
              </h3>
              {badge}
            </div>
            {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
          </div>
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      <div>{children}</div>
    </div>
  );
}
