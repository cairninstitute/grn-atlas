import React from 'react';

const WORKFLOW_TABS = [
  { id: 'home', label: 'Home', icon: '🏠' },
  { id: 'gene', label: 'Start from a gene', icon: '🧬' },
  { id: 'dataset', label: 'Unified workflow', icon: '📥' },
  { id: 'decision', label: 'Decide and hand off', icon: '🧭' },
  { id: 'advanced', label: 'Advanced tools', icon: '🔬' },
];

export default function AppNavigation({ mode, onChange }) {
  return (
    <div className="app-navigation" role="tablist" aria-label="Primary workflows">
      {WORKFLOW_TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`app-navigation-tab${mode === tab.id ? ' active' : ''}`}
          onClick={() => onChange(tab.id)}
          aria-pressed={mode === tab.id}
        >
          <span className="app-navigation-icon">{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
}
