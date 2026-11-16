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

export default function ViewTabs({ viewMode, onViewChange, tabs = TABS, hasGene = true }) {
  return (
    <div className="view-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab ${viewMode === tab.id ? 'active' : ''}`}
          onClick={() => onViewChange(tab.id)}
          title={tab.requiresGene && !hasGene ? `${tab.label} — select a gene first` : tab.description || tab.label}
          role="tab"
          aria-selected={viewMode === tab.id}
        >
          {tab.icon && <span className="tab-icon">{tab.icon}</span>}
          <span className="tab-label">{tab.label}</span>
          {tab.requiresGene && !hasGene && <span className="tab-requirement" aria-hidden="true">•</span>}
        </button>
      ))}
    </div>
  );
}
