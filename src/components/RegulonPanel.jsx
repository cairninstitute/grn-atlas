import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';

export default function RegulonPanel({ onShareGenes, sharedGeneSet }) {
  const [geneId, setGeneId] = useState('');
  const [depth, setDepth] = useState(2);
  const [minConf, setMinConf] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (sharedGeneSet?.genes?.length === 1) {
      setGeneId(sharedGeneSet.genes[0]);
    }
  }, [sharedGeneSet]);

  const run = async () => {
    if (!geneId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.regulon(geneId.trim(), { depth, minConfidence: minConf });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const regulonGenes = result ? Object.keys(result.genes).filter(id => id !== result.gene_id) : [];
  const levelEntries = result ? Object.entries(result.level_counts || {}).filter(([k]) => k !== '0') : [];

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Gene ID</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)}
            placeholder="e.g. TP53" onKeyDown={e => e.key === 'Enter' && run()} />
        </div>
        <div className="field">
          <label>Depth</label>
          <input type="number" value={depth} onChange={e => setDepth(+e.target.value)}
            min={1} max={4} style={{ width: 60 }} />
        </div>
        <div className="field">
          <label>Min confidence</label>
          <input type="number" value={minConf} onChange={e => setMinConf(+e.target.value)}
            min={0} max={1} step={0.1} style={{ width: 70 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !geneId.trim()}>
          {loading ? 'Running...' : 'Extract Regulon'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.total}</div>
              <div className="stat-label">Total genes</div>
            </div>
            {levelEntries.map(([lvl, count]) => (
              <div className="analysis-stat" key={lvl}>
                <div className="stat-value">{count}</div>
                <div className="stat-label">Level {lvl}</div>
              </div>
            ))}
            {result.capped && (
              <div className="analysis-stat">
                <div className="stat-value" style={{ color: 'var(--warning-dark)' }}>Capped</div>
                <div className="stat-label">At 5000 genes</div>
              </div>
            )}
          </div>

          {onShareGenes && regulonGenes.length > 0 && (
            <div className="analysis-actions">
              <button className="btn-action" onClick={() =>
                onShareGenes('upstream', regulonGenes, `${result.symbol || geneId} regulon`)}>
                Find upstream regulators
              </button>
            </div>
          )}

          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr><th>Gene ID</th><th>Symbol</th><th>Level</th><th>TF</th></tr>
              </thead>
              <tbody>
                {Object.entries(result.genes)
                  .sort((a, b) => a[1].level - b[1].level)
                  .slice(0, 500)
                  .map(([id, g]) => (
                    <tr key={id}>
                      <td className="mono">{id}</td>
                      <td>{g.symbol}</td>
                      <td>{g.level}</td>
                      <td>{g.is_tf ? 'Yes' : ''}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
