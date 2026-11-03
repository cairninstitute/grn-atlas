import React from 'react';

const WORKFLOW_TABS = [
  { id: 'explore', label: 'Explore', icon: '🔗' },
  { id: 'design', label: 'Design', icon: '✏️' },
  { id: 'toolbox', label: 'Toolbox', icon: '🔬' },
];

export default function AppNavigation({ mode, onChange }) {
  return (
    <div className="app-navigation" role="tablist" aria-label="Primary workflows">
      <span className="app-brand">Darwin</span>
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
