import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

interface MonoValueProps {
  value: string | null | undefined;
  copyable?: boolean;
  maxLength?: number;
  className?: string;
  badgeLabel?: string;
}

export function MonoValue({
  value,
  copyable = true,
  maxLength = 64,
  className = '',
  badgeLabel,
}: MonoValueProps) {
  const [copied, setCopied] = useState(false);

  if (value === null || value === undefined) {
    return <span className={`font-mono text-slate-500 text-xs ${className}`}>—</span>;
  }

  const displayValue = value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;

  const handleCopy = async () => {
    if (!copyable || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Failed to copy');
    }
  };

  return (
    <div className="inline-flex items-center gap-1.5 max-w-full">
      {badgeLabel && (
        <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/25">
          {badgeLabel}
        </span>
      )}
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900/80 border border-slate-800 text-slate-200 hover:border-slate-700 transition-colors">
        <code className={`font-mono text-xs select-all text-cyan-300/90 ${className}`}>
          {displayValue}
        </code>
        {copyable && (
          <button
            onClick={handleCopy}
            className="p-0.5 text-slate-400 hover:text-cyan-400 transition-colors rounded hover:bg-slate-800"
            title="Copy full value"
            aria-label="Copy to clipboard"
          >
            {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          </button>
        )}
      </div>
    </div>
  );
}
