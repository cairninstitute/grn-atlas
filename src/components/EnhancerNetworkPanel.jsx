import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function EnhancerNetworkPanel({ currentGene, currentSpecies }) {
  const [geneId, setGeneId] = useState(currentGene?.id || '');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!geneId) return;
    setLoading(true); setError(null);
    try {
      const data = await analysisAPI.enhancerNetwork(geneId, { species: currentSpecies });
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
        <button className="btn-run" onClick={run} disabled={loading || !geneId}>
          {loading ? 'Loading...' : 'Show enhancer network'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result && (
        <div>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.n_linked_peaks}</div>
              <div className="stat-label">Linked peaks</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.enhancer_regulators.length}</div>
              <div className="stat-label">Enhancer TFs</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.co_linked_targets.length}</div>
              <div className="stat-label">Co-linked genes</div>
            </div>
          </div>
          {result.enhancer_regulators.length > 0 && (
            <div className="analysis-table-wrap">
              <table className="analysis-table">
                <thead><tr><th>TF</th><th>Peak</th><th>Motif score</th><th>Link score</th><th>Has edge</th></tr></thead>
                <tbody>
                  {result.enhancer_regulators.slice(0, 20).map((r, i) => (
                    <tr key={i}>
                      <td>{r.tf_symbol}</td>
                      <td className="mono">{r.peak_id}</td>
                      <td>{r.motif_score?.toFixed(2)}</td>
                      <td>{r.link_score?.toFixed(2)}</td>
                      <td>{r.has_regulatory_edge ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {result.n_linked_peaks === 0 && (
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              No enhancer/peak data linked to this gene. Import chromatin peaks first.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
