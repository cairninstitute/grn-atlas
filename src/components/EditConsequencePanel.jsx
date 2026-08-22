import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function EditConsequencePanel({ currentGene, currentSpecies }) {
  const [geneId, setGeneId] = useState(currentGene?.id || '');
  const [editType, setEditType] = useState('promoter_disruption');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!geneId) return;
    setLoading(true); setError(null);
    try {
      const data = await analysisAPI.editConsequence(geneId, editType, { species: currentSpecies });
      if (data.detail) throw new Error(data.detail);
      setResult(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Gene ID</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)} placeholder="e.g. AT1G56650" />
        </div>
        <div className="field">
          <label>Edit type</label>
          <select value={editType} onChange={e => setEditType(e.target.value)}>
            <option value="promoter_disruption">Promoter disruption</option>
            <option value="coding_disruption">Coding disruption</option>
            <option value="motif_disruption">Motif disruption</option>
          </select>
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !geneId}>
          {loading ? 'Predicting...' : 'Predict consequences'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result && (
        <div>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.n_consequences}</div>
              <div className="stat-label">Affected edges</div>
            </div>
            {result.is_tf && (
              <div className="analysis-stat">
                <div className="stat-value">{result.downstream_cascade_size}</div>
                <div className="stat-label">Downstream cascade</div>
              </div>
            )}
          </div>
          {result.consequences.length > 0 && (
            <div className="analysis-table-wrap">
              <table className="analysis-table">
                <thead><tr><th>Affected edge</th><th>Direction</th><th>Confidence</th><th>Mechanism</th></tr></thead>
                <tbody>
                  {result.consequences.slice(0, 25).map((c, i) => (
                    <tr key={i}>
                      <td className="mono">{c.affected_edge}</td>
                      <td>{c.direction}</td>
                      <td>{c.confidence?.toFixed(2)}</td>
                      <td style={{ fontSize: '0.8rem' }}>{c.mechanism}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div style={{ marginTop: 10, fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
            {result.uncertainty}
          </div>
        </div>
      )}
    </div>
  );
}
