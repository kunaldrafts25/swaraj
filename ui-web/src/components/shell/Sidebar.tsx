import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FileText, GitGraph, Activity, Database, ClipboardCheck } from 'lucide-react';

const navItems = [
  { path: '/', label: 'Home', icon: FileText },
  { path: '/trace', label: 'Trace', icon: GitGraph },
  { path: '/egress', label: 'Egress', icon: Activity },
  { path: '/registry', label: 'Registry', icon: Database },
  { path: '/approvals', label: 'Approvals', icon: ClipboardCheck },
];

export function Sidebar() {
  const location = useLocation();

  return (
    <aside className="w-64 bg-sovereign-card border-r border-white/10 flex flex-col">
      <div className="p-4 border-b border-white/10">
        <h1 className="text-lg font-bold text-sovereign-text">SWARAJ v2</h1>
        <p className="text-xs text-sovereign-muted">Mission Control</p>
      </div>
      <nav className="flex-1 p-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2 rounded-md mb-1 transition-colors ${
                isActive
                  ? 'bg-sovereign-card3 text-sovereign-text'
                  : 'text-sovereign-muted hover:bg-sovereign-card2 hover:text-sovereign-text'
              }`}
            >
              <Icon size={18} />
              <span className="text-sm">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
