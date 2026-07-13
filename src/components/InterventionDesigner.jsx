import React, { useState, useEffect } from 'react';
import { geneLabel } from '../utils/geneLabel';
import { pathwayAPI } from '../services/apiService';
import '../styles/InterventionDesigner.css';

export default function InterventionDesigner({ gene, networkData }) {
  const [interventions, setInterventions] = useState([]);
  const [cascade, setCascade] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedIntervention, setSelectedIntervention] = useState(null);

  const regulators = networkData?.regulators || [];
  const targets = networkData?.targets || [];

  // Add an intervention
  const addIntervention = (regulator, action, strength = 1.5) => {
    const intervention = {
      id: Math.random().toString(36),
      target_tf: regulator.symbol,
      target_id: regulator.id,
      action, // 'enhance' or 'suppress'
      strength,
      confidence: regulator.confidence
    };
    setInterventions([...interventions, intervention]);
  };

  // Remove an intervention
  const removeIntervention = (id) => {
    setInterventions(interventions.filter(i => i.id !== id));
    if (selectedIntervention?.id === id) setSelectedIntervention(null);
  };

  // Update intervention strength
  const updateIntervention = (id, strength) => {
    setInterventions(interventions.map(i => 
      i.id === id ? { ...i, strength } : i
    ));
  };

  // Predict cascade effects
  const handlePredictCascade = async () => {
    if (interventions.length === 0) {
      setError('Add at least one intervention');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      // enhance -> over-express (oe), suppress -> knock-out (ko).
      const data = await pathwayAPI.perturb(
        interventions.map(i => ({
          gene_id: i.target_id,
          action: i.action === 'enhance' ? 'oe' : 'ko',
        })),
        { depth: 4 }
      );
      setCascade(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Download intervention design as JSON
  const downloadDesign = () => {
    const design = {
      target_gene: gene.symbol,
      target_gene_id: gene.id,
      timestamp: new Date().toISOString(),
      interventions: interventions.map(i => ({
        tf: i.target_tf,
        action: i.action,
        strength: i.strength,
        confidence: i.confidence
      })),
      predicted_effects: cascade?.effects || [],
      model: cascade?.note || null
    };

    const blob = new Blob([JSON.stringify(design, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${gene.symbol}_intervention_design.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="intervention-designer">
      <div className="designer-header">
        <div>
          <h2>Intervention Designer</h2>
          <p>Design regulatory changes to modify {geneLabel(gene).label}'s phenotype</p>
        </div>
        {interventions.length > 0 && (
          <button className="download-button" onClick={downloadDesign}>
            ⬇ Download design
          </button>
        )}
      </div>

      <div className="designer-layout">
        {/* Left panel: Regulators and interventions */}
        <div className="designer-panel regulators-panel">
          <h3 className="panel-title">Available regulators</h3>
          <div className="regulators-list">
            {regulators.length === 0 ? (
              <div className="empty-list">No regulators found</div>
            ) : (
              regulators.map((reg) => (
                <div key={reg.id} className="regulator-item">
                  <div className="regulator-info">
                    <div className="regulator-name">
                      <span className="symbol">{reg.symbol}</span>
                      {reg.is_tf && <span className="tf-badge">TF</span>}
                    </div>
                    <div className="regulator-meta">
                      <span className={`regulation-type ${reg.regulation_type}`}>
                        {reg.regulation_type === 'activation' ? '✓ Activates' : '✗ Represses'}
                      </span>
                      <span className="confidence">{(reg.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  
                  <div className="action-buttons">
                    <button 
                      className="action-btn enhance"
                      title="Enhance this regulator"
                      onClick={() => addIntervention(reg, 'enhance', 1.5)}
                    >
                      ↑ Enhance
                    </button>
                    <button 
                      className="action-btn suppress"
                      title="Suppress this regulator"
                      onClick={() => addIntervention(reg, 'suppress', 0.5)}
                    >
                      ↓ Suppress
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Middle panel: Intervention plan */}
        <div className="designer-panel design-panel">
          <h3 className="panel-title">Intervention plan</h3>
          
          {interventions.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">✏️</div>
              <p>Click "Enhance" or "Suppress" on the left to add interventions</p>
            </div>
          ) : (
            <div className="interventions-list">
              {interventions.map((intervention) => (
                <div 
                  key={intervention.id} 
                  className={`intervention-card ${intervention.action} ${selectedIntervention?.id === intervention.id ? 'selected' : ''}`}
                  onClick={() => setSelectedIntervention(intervention)}
                >
                  <div className="intervention-header">
                    <div className="intervention-name">
                      <span className="action-badge" style={{
                        backgroundColor: intervention.action === 'enhance' ? '#4CAF50' : '#F44336'
                      }}>
                        {intervention.action === 'enhance' ? '⬆' : '⬇'}
                      </span>
                      <span className="tf-name">{intervention.target_tf}</span>
                    </div>
                    <button 
                      className="remove-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeIntervention(intervention.id);
                      }}
                    >
                      ×
                    </button>
                  </div>

                  <div className="intervention-controls">
                    <label className="strength-label">
                      Strength:
                      <input
                        type="range"
                        min={intervention.action === 'enhance' ? '1' : '0'}
                        max={intervention.action === 'enhance' ? '3' : '1'}
                        step="0.1"
                        value={intervention.strength}
                        onChange={(e) => updateIntervention(intervention.id, parseFloat(e.target.value))}
                        className="strength-slider"
                      />
                      <span className="strength-value">
                        {intervention.action === 'enhance' ? 
                          `${intervention.strength.toFixed(1)}×` : 
                          `${(intervention.strength * 100).toFixed(0)}%`
                        }
                      </span>
                    </label>
                  </div>

                  <div className="intervention-meta">
                    <span className="confidence-note">
                      Evidence confidence: {(intervention.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {interventions.length > 0 && (
            <button 
              className="predict-button"
              onClick={handlePredictCascade}
              disabled={loading}
            >
              {loading ? '⟳ Predicting...' : '🔮 Predict cascade'}
            </button>
          )}

          {error && (
            <div className="error-message">{error}</div>
          )}
        </div>

        {/* Right panel: Predicted cascade */}
        <div className="designer-panel cascade-panel">
          <h3 className="panel-title">Predicted cascade</h3>
          
          {!cascade ? (
            <div className="empty-state">
              <div className="empty-icon">🔮</div>
              <p>Run prediction to see expected cascade effects</p>
            </div>
          ) : (
            <div className="cascade-container">
              {/* Cascade header */}
              <div className="cascade-header">
                <div className="cascade-stat">
                  <span className="stat-label">Affected</span>
                  <span className="stat-value">{cascade.stats?.affected || 0}</span>
                </div>
                <div className="cascade-stat">
                  <span className="stat-label">↑ up</span>
                  <span className="stat-value">{cascade.stats?.up || 0}</span>
                </div>
                <div className="cascade-stat">
                  <span className="stat-label">↓ down</span>
                  <span className="stat-value">{cascade.stats?.down || 0}</span>
                </div>
                <div className="cascade-stat">
                  <span className="stat-label">? unknown</span>
                  <span className="stat-value">{cascade.stats?.unknown || 0}</span>
                </div>
              </div>

              {cascade.note && <p className="cascade-note">{cascade.note}</p>}

              {/* Predicted effects (strongest first) */}
              <div className="cascade-levels">
                {cascade.effects && cascade.effects.length > 0 ? (
                  cascade.effects.slice(0, 40).map((effect, idx) => (
                    <div key={idx} className={`cascade-item level-${effect.level || 1}`}
                         title={effect.path?.join(' → ')}>
                      <div className="cascade-gene">
                        <span className="gene-symbol">{effect.symbol}</span>
                        <span className="gene-level">
                          L{effect.level}{effect.uses_inferred ? ' · inferred' : ''}
                        </span>
                      </div>

                      <div className="cascade-effect">
                        <span className={`effect-arrow ${effect.predicted_direction}`}>
                          {effect.predicted_direction === 'up' ? '↑'
                            : effect.predicted_direction === 'down' ? '↓' : '?'}
                        </span>
                        <span className="effect-magnitude">{effect.magnitude.toFixed(2)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty-cascade">No effects predicted</div>
                )}
              </div>

              {/* Summary statistics */}
              <div className="cascade-summary">
                <div className="summary-item">
                  <span className="summary-label">Interventions</span>
                  <span className="summary-value">{interventions.length}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Uses inferred edges</span>
                  <span className="summary-value">{cascade.stats?.uses_inferred ? 'yes' : 'no'}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
