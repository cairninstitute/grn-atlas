import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function MultiomeAuditPanel({ currentGene, currentSpecies }) {
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState(currentGene?.id || '');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!sourceId || !targetId) return;
    setLoading(true); setError(null);
    try {
      const data = await analysisAPI.multiomeAudit(sourceId, targetId, currentSpecies);
      setResult(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  const layerIcon = (present) => present ? '✅' : '❌';

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Source TF</label>
          <input type="text" value={sourceId} onChange={e => setSourceId(e.target.value)} placeholder="TF gene ID" />
        </div>
        <div className="field">
          <label>Target gene</label>
          <input type="text" value={targetId} onChange={e => setTargetId(e.target.value)} placeholder="Target gene ID" />
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !sourceId || !targetId}>
          {loading ? 'Checking...' : 'Audit evidence'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result && (
        <div>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.n_supporting_layers}/5</div>
              <div className="stat-label">Layers present</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{(result.evidence_weight * 100).toFixed(0)}%</div>
              <div className="stat-label">Evidence weight</div>
            </div>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead><tr><th>Layer</th><th>Status</th><th>Details</th></tr></thead>
              <tbody>
                {Object.entries(result.layers).map(([layer, info]) => (
                  <tr key={layer}>
                    <td style={{ fontWeight: 600 }}>{layer}</td>
                    <td>{layerIcon(info.present)}</td>
                    <td className="mono" style={{ fontSize: '0.8rem' }}>
                      {info.present ? JSON.stringify(Object.fromEntries(
                        Object.entries(info).filter(([k]) => k !== 'present').slice(0, 2)
                      )) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.conflicting_evidence.length > 0 && (
            <div className="analysis-error" style={{ marginTop: 12 }}>
              Conflicting evidence: {result.conflicting_evidence.join('; ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
