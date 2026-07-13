import React, { useState, useEffect } from 'react';
import '../styles/ComparisonView.css';

const DB_SPECIES = ['human', 'arabidopsis'];

export default function ComparisonView({ gene, currentSpecies }) {
  const defaultOther = DB_SPECIES.find(s => s !== currentSpecies) || DB_SPECIES[0];
  const [comparisonSpecies, setComparisonSpecies] = useState([currentSpecies, defaultOther]);
  const [orthologyData, setOrthologyData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const otherSpecies = DB_SPECIES.filter(s => !comparisonSpecies.includes(s));

  useEffect(() => {
    const fetchOrthologyData = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/v1/genes/orthology/${gene.id}?species=${comparisonSpecies.join(',')}`);
        const data = await response.json();
        setOrthologyData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchOrthologyData();
  }, [gene.id, comparisonSpecies]);

  const handleAddSpecies = (species) => {
    setComparisonSpecies([...comparisonSpecies, species]);
  };

  const handleRemoveSpecies = (species) => {
    setComparisonSpecies(comparisonSpecies.filter(s => s !== species));
  };

  // Compute shared regulators across all found species
  const sharedRegulators = new Set();
  if (orthologyData) {
    const foundPanels = comparisonSpecies
      .filter(sp => orthologyData[sp]?.found)
      .map(sp => new Set((orthologyData[sp]?.regulators || []).map(r => r.symbol.toUpperCase())));
    if (foundPanels.length >= 2) {
      foundPanels[0].forEach(sym => {
        if (foundPanels.every(s => s.has(sym))) sharedRegulators.add(sym);
      });
    }
  }

  return (
    <div className="comparison-view">
      <div className="comparison-toolbar">
        <div className="comparison-title">
          <h2>Regulatory comparison: {gene.symbol}</h2>
          <p>Compare regulatory networks across species</p>
        </div>

        {otherSpecies.length > 0 && (
          <div className="species-selector">
            <select
              className="species-select"
              onChange={(e) => {
                if (e.target.value) {
                  handleAddSpecies(e.target.value);
                  e.target.value = '';
                }
              }}
            >
              <option value="">+ Add species...</option>
              {otherSpecies.map(s => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {sharedRegulators.size > 0 && (
        <div className="shared-regulators-bar">
          <span className="shared-label">Shared regulators:</span>
          {[...sharedRegulators].map(sym => (
            <span key={sym} className="shared-badge">{sym}</span>
          ))}
        </div>
      )}

      {loading ? (
        <div className="loading-state">
          <div className="spinner">...</div>
          <p>Loading orthology data...</p>
        </div>
      ) : (
        <div className="comparison-grid">
          {comparisonSpecies.map((species) => (
            <SpeciesPanel
              key={species}
              species={species}
              gene={gene}
              data={orthologyData?.[species]}
              onRemove={() => handleRemoveSpecies(species)}
              sharedRegulators={sharedRegulators}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SpeciesPanel({ species, gene, data, onRemove, sharedRegulators }) {
  const [expandedRegulators, setExpandedRegulators] = useState(false);
  const [expandedTargets, setExpandedTargets] = useState(false);

  const found = data?.found !== false;
  const regulators = data?.regulators || [];
  const targets = data?.targets || [];

  const displayRegulators = expandedRegulators ? regulators : regulators.slice(0, 5);
  const displayTargets = expandedTargets ? targets : targets.slice(0, 5);

  const getSpeciesLabel = (sp) => {
    const labels = { human: 'Human', arabidopsis: 'Arabidopsis' };
    return labels[sp] || sp.charAt(0).toUpperCase() + sp.slice(1);
  };

  const orthologSymbol = data?.ortholog_symbol || gene.symbol;

  return (
    <div className={`species-panel ${!found ? 'species-panel-not-found' : ''}`}>
      <div className="panel-header">
        <div>
          <h3 className="panel-species">{getSpeciesLabel(species)}</h3>
          <div className="panel-gene">{orthologSymbol}</div>
        </div>
        <button className="remove-button" onClick={onRemove} title="Remove species">x</button>
      </div>

      {!found ? (
        <div className="not-found-message">
          <div className="not-found-icon">--</div>
          <p>No ortholog for <strong>{gene.symbol}</strong> found in {getSpeciesLabel(species)}</p>
          <p className="not-found-hint">Symbol-based lookup found no match in the database</p>
        </div>
      ) : (
        <>
          <div className="panel-stats">
            <div className="stat">
              <span className="stat-number">{regulators.length}</span>
              <span className="stat-label">Regulators</span>
            </div>
            <div className="stat">
              <span className="stat-number">{targets.length}</span>
              <span className="stat-label">Targets</span>
            </div>
          </div>

          <div className="panel-section">
            <h4 className="section-title">Regulators ({regulators.length})</h4>
            <div className="gene-list">
              {displayRegulators.map((reg) => (
                <div key={reg.id} className={`gene-item ${sharedRegulators.has(reg.symbol.toUpperCase()) ? 'gene-item-shared' : ''}`}>
                  <div className="gene-info">
                    <span className="gene-symbol">{reg.symbol}</span>
                    {reg.is_tf && <span className="tf-badge">TF</span>}
                    {sharedRegulators.has(reg.symbol.toUpperCase()) && <span className="shared-badge">shared</span>}
                  </div>
                  <div className="gene-meta">
                    <span className={`regulation-badge ${reg.regulation_type}`}>
                      {reg.regulation_type === 'activation' ? 'A' : reg.regulation_type === 'repression' ? 'R' : '?'}
                    </span>
                    <span className="confidence">
                      {(reg.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            {regulators.length > 5 && (
              <button className="expand-link" onClick={() => setExpandedRegulators(!expandedRegulators)}>
                {expandedRegulators ? '- Collapse' : `+ ${regulators.length - 5} more`}
              </button>
            )}
          </div>

          <div className="panel-section">
            <h4 className="section-title">Targets ({targets.length})</h4>
            <div className="gene-list">
              {displayTargets.map((tgt) => (
                <div key={tgt.id} className="gene-item">
                  <div className="gene-info">
                    <span className="gene-symbol">{tgt.symbol}</span>
                    {tgt.is_tf && <span className="tf-badge">TF</span>}
                  </div>
                  <div className="gene-meta">
                    <span className={`regulation-badge ${tgt.regulation_type}`}>
                      {tgt.regulation_type === 'activation' ? 'A' : tgt.regulation_type === 'repression' ? 'R' : '?'}
                    </span>
                    <span className="confidence">
                      {(tgt.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            {targets.length > 5 && (
              <button className="expand-link" onClick={() => setExpandedTargets(!expandedTargets)}>
                {expandedTargets ? '- Collapse' : `+ ${targets.length - 5} more`}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
