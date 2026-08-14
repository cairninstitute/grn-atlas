import React from 'react';
import '../styles/ViewTabs.css';

const TABS = [
  { id: 'workflow', label: 'Workflow', icon: '🧭' },
  { id: 'network', label: 'Explorer', icon: '🔗' },
  { id: 'organism', label: 'Organism', icon: '🌐' },
  { id: 'pathways', label: 'Paths', icon: '🛤️' },
  { id: 'comparison', label: 'Orthology', icon: '⚖️' },
  { id: 'genome', label: 'Genome', icon: '🧬' },
  { id: 'design', label: 'Design', icon: '✏️' },
  { id: 'analysis', label: 'Lab', icon: '🔬' }
];

export default function ViewTabs({ viewMode, onViewChange, tabs = TABS }) {
  return (
    <div className="view-tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab ${viewMode === tab.id ? 'active' : ''}`}
          onClick={() => onViewChange(tab.id)}
          title={tab.label}
        >
          <span className="tab-icon">{tab.icon}</span>
          <span className="tab-label">{tab.label}</span>
        </button>
      ))}
    </div>
  );
}
