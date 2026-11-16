import React from 'react';

const WORKFLOW_TABS = [
  { id: 'home', label: 'Home' },
  { id: 'explore', label: 'Explore networks' },
  { id: 'design', label: 'Design experiments' },
  { id: 'toolbox', label: 'Analysis tools' },
];

export default function AppNavigation({ mode, onChange }) {
  return (
    <div className="app-navigation" role="tablist" aria-label="Primary workflows">
      <button className="app-brand" type="button" onClick={() => onChange('home')}>
        <span className="app-brand-mark">D</span>
        <span className="app-brand-copy">
          <strong>Darwin</strong>
          <small>Gene regulation atlas</small>
        </span>
      </button>
      {WORKFLOW_TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`app-navigation-tab${mode === tab.id ? ' active' : ''}`}
          onClick={() => onChange(tab.id)}
          aria-pressed={mode === tab.id}
        >
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
  );
}
