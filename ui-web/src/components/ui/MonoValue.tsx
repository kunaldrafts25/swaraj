import React from 'react';

interface MonoValueProps {
  value: string | null | undefined;
  copyable?: boolean;
  maxLength?: number;
  className?: string;
}

export function MonoValue({ value, copyable = true, maxLength = 64, className = '' }: MonoValueProps) {
  if (value === null || value === undefined) {
    return <span className={`font-mono text-sovereign-muted ${className}`}>—</span>;
  }

  const displayValue = value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;

  const handleCopy = async () => {
    if (copyable && navigator.clipboard) {
      await navigator.clipboard.writeText(value);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <code className={`font-mono text-sm text-sovereign-text bg-sovereign-card2 px-2 py-1 rounded ${className}`}>
        {displayValue}
      </code>
      {copyable && value.length <= maxLength && (
        <button
          onClick={handleCopy}
          className="text-xs text-sovereign-muted hover:text-sovereign-text transition-colors"
          title="Copy to clipboard"
        >
          📋
        </button>
      )}
    </div>
  );
}
