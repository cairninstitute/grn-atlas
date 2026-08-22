import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

const TIER_COLORS = { strong: '#22c55e', moderate: '#eab308', weak: '#f97316', minimal: '#ef4444' };

export default function CisSupportAuditPanel({ currentGene, currentSpecies }) {
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState(currentGene?.id || '');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!sourceId || !targetId) return;
    setLoading(true); setError(null);
    try {
      const data = await analysisAPI.cisSupportAudit(sourceId, targetId, currentSpecies);
      if (data.detail) throw new Error(data.detail);
      setResult(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Source TF</label>
          <input type="text" value={sourceId} onChange={e => setSourceId(e.target.value)} placeholder="e.g. AT1G56650" />
        </div>
        <div className="field">
          <label>Target gene</label>
          <input type="text" value={targetId} onChange={e => setTargetId(e.target.value)} placeholder="e.g. AT5G42910" />
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !sourceId || !targetId}>
          {loading ? 'Auditing...' : 'Audit edge'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result && (
        <div>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value" style={{ color: TIER_COLORS[result.confidence_tier] }}>{result.confidence_tier}</div>
              <div className="stat-label">Confidence tier</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.n_supporting_layers}/4</div>
              <div className="stat-label">Evidence layers</div>
            </div>
          </div>
          {result.missing_layers.length > 0 && (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 12 }}>
              Missing: {result.missing_layers.join(', ')}
            </div>
          )}
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead><tr><th>Layer</th><th>Present</th><th>Details</th></tr></thead>
              <tbody>
                {Object.entries(result.layers).map(([layer, info]) => (
                  <tr key={layer}>
                    <td style={{ fontWeight: 600 }}>{layer.replace(/_/g, ' ')}</td>
                    <td>{info.present ? 'Yes' : 'No'}</td>
                    <td className="mono" style={{ fontSize: '0.8rem' }}>
                      {info.present ? JSON.stringify(Object.fromEntries(
                        Object.entries(info).filter(([k]) => k !== 'present').slice(0, 3)
                      )) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
