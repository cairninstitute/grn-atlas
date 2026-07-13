import React from 'react';
import '../styles/Toolbar.css';

export default function Toolbar({ gene, stats }) {
  if (!gene) return null;

  const regulatorCount = stats?.regulators?.length || 0;
  const targetCount = stats?.targets?.length || 0;
  const pathCount = stats?.paths?.length || 0;

  return (
    <div className="toolbar">
      <div className="toolbar-gene-info">
        <h2 className="gene-symbol">{gene.symbol}</h2>
        <span className="gene-name">{gene.name}</span>
      </div>

      <div className="toolbar-badges">
        <div className="badge">
          <span className="badge-label">Species</span>
          <span className="badge-value">{gene.species}</span>
        </div>
        {gene.is_tf && (
          <div className="badge tf-badge">
            <span className="badge-label">Type</span>
            <span className="badge-value">Transcription Factor</span>
          </div>
        )}
      </div>

      <div className="toolbar-stats">
        <div className="stat-item">
          <span className="stat-label">Regulators</span>
          <span className="stat-value">{regulatorCount}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Targets</span>
          <span className="stat-value">{targetCount}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Paths</span>
          <span className="stat-value">{pathCount}</span>
        </div>
      </div>

      <div className="toolbar-actions">
        <button className="action-button" title="Export network">
          ⬇ Export
        </button>
        <button className="action-button" title="Share">
          🔗 Share
        </button>
      </div>
    </div>
  );
}
