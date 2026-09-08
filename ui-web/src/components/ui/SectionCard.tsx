import React from 'react';

interface SectionCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

export function SectionCard({ title, children, className = '' }: SectionCardProps) {
  return (
    <div className={`bg-sovereign-card rounded-lg border border-white/10 p-4 ${className}`}>
      <h3 className="text-sovereign-text font-medium mb-3">{title}</h3>
      {children}
    </div>
  );
}
