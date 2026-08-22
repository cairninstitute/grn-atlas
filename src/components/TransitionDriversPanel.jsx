import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function TransitionDriversPanel({ currentSpecies, sharedGeneSet }) {
  const [geneIds, setGeneIds] = useState(sharedGeneSet?.genes?.join(', ') || '');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!geneIds.trim()) return;
    setLoading(true); setError(null);
    try {
      const ids = geneIds.split(/[,\s]+/).filter(Boolean);
      const data = await analysisAPI.transitionDrivers({ gene_ids: ids, species: currentSpecies });
      setResult(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field" style={{ flex: 1 }}>
          <label>Transition DEGs (comma-separated gene IDs)</label>
          <input type="text" value={geneIds} onChange={e => setGeneIds(e.target.value)}
                 placeholder="Gene IDs from transition/branch point" style={{ width: '100%' }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !geneIds.trim()}>
          {loading ? 'Finding drivers...' : 'Find transition drivers'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result?.drivers && (
        <div>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.drivers.length}</div>
              <div className="stat-label">Driver TFs found</div>
            </div>
          </div>
          {result.drivers.length > 0 && (
            <div className="analysis-table-wrap">
              <table className="analysis-table">
                <thead><tr><th>TF</th><th>Regulon</th><th>Overlap</th><th>p-value</th><th>Overlap genes</th></tr></thead>
                <tbody>
                  {result.drivers.slice(0, 25).map((d, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{d.tf_symbol}</td>
                      <td>{d.regulon_size}</td>
                      <td>{d.overlap_count}</td>
                      <td className="mono">{d.p_value?.toExponential(2)}</td>
                      <td className="mono" style={{ fontSize: '0.75rem' }}>{d.overlap_genes?.slice(0, 5).join(', ')}{d.overlap_genes?.length > 5 ? '...' : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {result?.status === 'ready' && (
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          Provide transition DEGs to identify driver TFs.
        </div>
      )}
    </div>
  );
}
