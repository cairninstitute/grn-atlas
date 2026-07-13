import React, { useState, useEffect } from 'react';
import '../styles/ComparisonView.css';

export default function ComparisonView({ gene, currentSpecies }) {
  const [comparisonSpecies, setComparisonSpecies] = useState([currentSpecies, 'arabidopsis']);
  const [orthologyData, setOrthologyData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Available species for comparison
  const availableSpecies = [
    'human', 'arabidopsis', 'rice', 'tomato', 'potato', 
    'soybean', 'poplar', 'sorghum', 'grape'
  ];

  const otherSpecies = availableSpecies.filter(s => !comparisonSpecies.includes(s));

  // Fetch orthology and regulatory data for all species
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

  // Add species to comparison
  const handleAddSpecies = (species) => {
    setComparisonSpecies([...comparisonSpecies, species]);
  };

  // Remove species from comparison
  const handleRemoveSpecies = (species) => {
    setComparisonSpecies(comparisonSpecies.filter(s => s !== species));
  };

  return (
    <div className="comparison-view">
      {/* Toolbar */}
      <div className="comparison-toolbar">
        <div className="comparison-title">
          <h2>Regulatory comparison: {gene.symbol}</h2>
          <p>Compare regulatory networks across species</p>
        </div>

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
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {loading ? (
        <div className="loading-state">
          <div className="spinner">⟳</div>
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
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Species comparison panel
function SpeciesPanel({ species, gene, data, onRemove }) {
  const [expandedRegulators, setExpandedRegulators] = useState(false);
  const [expandedTargets, setExpandedTargets] = useState(false);

  const regulators = data?.regulators || [];
  const targets = data?.targets || [];

  const displayRegulators = expandedRegulators ? regulators : regulators.slice(0, 5);
  const displayTargets = expandedTargets ? targets : targets.slice(0, 5);

  const getSpeciesLabel = (sp) => {
    const labels = {
      human: 'Human',
      arabidopsis: 'Arabidopsis',
      rice: 'Rice',
      tomato: 'Tomato',
      potato: 'Potato',
      soybean: 'Soybean',
      poplar: 'Poplar',
      sorghum: 'Sorghum',
      grape: 'Grape'
    };
    return labels[sp] || sp;
  };

  const orthologSymbol = data?.ortholog_symbol || gene.symbol;

  return (
    <div className="species-panel">
      <div className="panel-header">
        <div>
          <h3 className="panel-species">{getSpeciesLabel(species)}</h3>
          <div className="panel-gene">{orthologSymbol}</div>
        </div>
        <button 
          className="remove-button"
          onClick={onRemove}
          title="Remove species"
        >
          ×
        </button>
      </div>

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

      {/* Regulators */}
      <div className="panel-section">
        <h4 className="section-title">Regulators ({regulators.length})</h4>
        <div className="gene-list">
          {displayRegulators.map((reg) => (
            <div key={reg.id} className="gene-item">
              <div className="gene-info">
                <span className="gene-symbol">{reg.symbol}</span>
                {reg.is_tf && <span className="tf-badge">TF</span>}
              </div>
              <div className="gene-meta">
                <span className={`regulation-badge ${reg.regulation_type}`}>
                  {reg.regulation_type === 'activation' ? '✓' : reg.regulation_type === 'repression' ? '✗' : '?'}
                </span>
                <span className="confidence">
                  {(reg.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
        {regulators.length > 5 && (
          <button 
            className="expand-link"
            onClick={() => setExpandedRegulators(!expandedRegulators)}
          >
            {expandedRegulators ? '− Collapse' : `+ ${regulators.length - 5} more`}
          </button>
        )}
      </div>

      {/* Targets */}
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
                  {tgt.regulation_type === 'activation' ? '✓' : tgt.regulation_type === 'repression' ? '✗' : '?'}
                </span>
                <span className="confidence">
                  {(tgt.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
        {targets.length > 5 && (
          <button 
            className="expand-link"
            onClick={() => setExpandedTargets(!expandedTargets)}
          >
            {expandedTargets ? '− Collapse' : `+ ${targets.length - 5} more`}
          </button>
        )}
      </div>

      {/* Unique regulators */}
      {regulators.length > 0 && (
        <div className="panel-insight">
          <span className="insight-icon">💡</span>
          <span className="insight-text">
            {regulators.length} regulator(s) specific to {getSpeciesLabel(species)}
          </span>
        </div>
      )}
    </div>
  );
}
