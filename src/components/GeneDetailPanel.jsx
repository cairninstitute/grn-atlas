import React, { useState, useMemo } from 'react';
import '../styles/GeneDetailPanel.css';

export default function GeneDetailPanel({ gene, data }) {
  const [expandedRegulators, setExpandedRegulators] = useState(false);
  const [expandedTargets, setExpandedTargets] = useState(false);
  const [sortBy, setSortBy] = useState('confidence');

  const sortedRegulators = useMemo(() => {
    if (!data?.regulators) return [];
    const sorted = [...data.regulators];
    if (sortBy === 'confidence') {
      sorted.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    } else if (sortBy === 'name') {
      sorted.sort((a, b) => a.symbol.localeCompare(b.symbol));
    }
    return sorted;
  }, [data, sortBy]);

  const sortedTargets = useMemo(() => {
    if (!data?.targets) return [];
    const sorted = [...data.targets];
    if (sortBy === 'confidence') {
      sorted.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    } else if (sortBy === 'name') {
      sorted.sort((a, b) => a.symbol.localeCompare(b.symbol));
    }
    return sorted;
  }, [data, sortBy]);

  const getEvidenceBreakdown = () => {
    const sources = {};
    const allInteractions = [...(data?.regulators || []), ...(data?.targets || [])];
    
    allInteractions.forEach((interaction) => {
      interaction.source_databases?.forEach((source) => {
        sources[source] = (sources[source] || 0) + 1;
      });
    });

    return sources;
  };

  const evidenceBreakdown = useMemo(() => getEvidenceBreakdown(), [data]);

  const displayRegulators = expandedRegulators ? sortedRegulators : sortedRegulators.slice(0, 3);
  const displayTargets = expandedTargets ? sortedTargets : sortedTargets.slice(0, 3);

  return (
    <div className="gene-detail-panel">
      {/* Gene Info Section */}
      <div className="detail-section">
        <h3 className="section-title">Gene information</h3>
        
        <div className="info-grid">
          <div className="info-item">
            <label>Symbol</label>
            <value className="value-primary">{gene.symbol}</value>
          </div>
          
          <div className="info-item">
            <label>Name</label>
            <value className="value-secondary">{gene.name}</value>
          </div>
          
          <div className="info-item">
            <label>Species</label>
            <value className="value-secondary">{gene.species}</value>
          </div>

          {gene.ensembl_id && (
            <div className="info-item">
              <label>Ensembl ID</label>
              <value className="value-mono">{gene.ensembl_id}</value>
            </div>
          )}

          {gene.is_tf && (
            <div className="info-item">
              <label>Type</label>
              <div className="badge-group">
                <span className="badge tf-badge">Transcription Factor</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Evidence Section */}
      <div className="detail-section">
        <h3 className="section-title">Evidence sources</h3>
        
        <div className="evidence-breakdown">
          {Object.entries(evidenceBreakdown).map(([source, count]) => {
            const percentage = ((count / Object.values(evidenceBreakdown).reduce((a, b) => a + b, 0)) * 100).toFixed(0);
            return (
              <div key={source} className="evidence-item">
                <div className="evidence-label">
                  <span className="evidence-name">{source}</span>
                  <span className="evidence-count">{count}</span>
                </div>
                <div className="evidence-bar">
                  <div className="evidence-bar-fill" style={{ width: `${percentage}%` }}></div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="confidence-guide">
          <div className="guide-title">Confidence scale</div>
          <div className="guide-item">
            <span className="guide-badge high">0.9+</span>
            <span>Literature validated</span>
          </div>
          <div className="guide-item">
            <span className="guide-badge medium">0.6–0.8</span>
            <span>Motif + evidence</span>
          </div>
          <div className="guide-item">
            <span className="guide-badge low">&lt;0.6</span>
            <span>Predicted</span>
          </div>
        </div>
      </div>

      <hr className="detail-divider" />

      {/* Regulators Section */}
      <div className="detail-section">
        <div className="section-header">
          <h3 className="section-title">Regulators ({sortedRegulators.length})</h3>
          <select 
            className="sort-select" 
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="confidence">Sort by confidence</option>
            <option value="name">Sort alphabetically</option>
          </select>
        </div>

        <div className="interaction-list">
          {displayRegulators.map((regulator) => (
            <div key={regulator.id} className="interaction-item">
              <div className="interaction-main">
                <span className="interaction-symbol">{regulator.symbol}</span>
                {regulator.is_tf && <span className="mini-badge">TF</span>}
              </div>
              
              <div className="interaction-details">
                <div className="regulation-type">
                  {regulator.regulation_type === 'activation' ? (
                    <span className="type-badge activation">✓ Activates</span>
                  ) : regulator.regulation_type === 'repression' ? (
                    <span className="type-badge repression">✗ Represses</span>
                  ) : (
                    <span className="type-badge unknown">? Unknown</span>
                  )}
                </div>
                
                <div className="confidence-display">
                  <span className="confidence-label">
                    {(regulator.confidence * 100).toFixed(0)}%
                  </span>
                  <div className="confidence-bar-mini">
                    <div 
                      className="confidence-bar-mini-fill" 
                      style={{ width: `${regulator.confidence * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>
              
              {regulator.source_databases && regulator.source_databases.length > 0 && (
                <div className="interaction-sources">
                  {regulator.source_databases.map((source, idx) => (
                    <span key={idx} className="source-tag">{source}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {sortedRegulators.length > 3 && (
          <button 
            className="expand-button"
            onClick={() => setExpandedRegulators(!expandedRegulators)}
          >
            {expandedRegulators ? '− Collapse' : `+ Show ${sortedRegulators.length - 3} more`}
          </button>
        )}
      </div>

      {/* Targets Section */}
      <div className="detail-section">
        <div className="section-header">
          <h3 className="section-title">Direct targets ({sortedTargets.length})</h3>
        </div>

        <div className="interaction-list">
          {displayTargets.map((target) => (
            <div key={target.id} className="interaction-item">
              <div className="interaction-main">
                <span className="interaction-symbol">{target.symbol}</span>
                {target.is_tf && <span className="mini-badge">TF</span>}
              </div>
              
              <div className="interaction-details">
                <div className="regulation-type">
                  {target.regulation_type === 'activation' ? (
                    <span className="type-badge activation">✓ Activated</span>
                  ) : target.regulation_type === 'repression' ? (
                    <span className="type-badge repression">✗ Repressed</span>
                  ) : (
                    <span className="type-badge unknown">? Unknown</span>
                  )}
                </div>
                
                <div className="confidence-display">
                  <span className="confidence-label">
                    {(target.confidence * 100).toFixed(0)}%
                  </span>
                  <div className="confidence-bar-mini">
                    <div 
                      className="confidence-bar-mini-fill" 
                      style={{ width: `${target.confidence * 100}%` }}
                    ></div>
                  </div>
                </div>
              </div>
              
              {target.source_databases && target.source_databases.length > 0 && (
                <div className="interaction-sources">
                  {target.source_databases.map((source, idx) => (
                    <span key={idx} className="source-tag">{source}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {sortedTargets.length > 3 && (
          <button 
            className="expand-button"
            onClick={() => setExpandedTargets(!expandedTargets)}
          >
            {expandedTargets ? '− Collapse' : `+ Show ${sortedTargets.length - 3} more`}
          </button>
        )}
      </div>
    </div>
  );
}
