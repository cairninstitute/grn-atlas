import React from 'react';
import '../styles/ViewTabs.css';

const TABS = [
  { id: 'network', label: 'Network', icon: '🔗' },
  { id: 'pathways', label: 'Pathways', icon: '🛤️' },
  { id: 'comparison', label: 'Comparison', icon: '⚖️' },
  { id: 'design', label: 'Design', icon: '✏️' }
];

export default function ViewTabs({ viewMode, onViewChange }) {
  return (
    <div className="view-tabs">
      {TABS.map((tab) => (
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
