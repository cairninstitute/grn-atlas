import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function CentralityPanel() {
  const [species, setSpecies] = useState('human');
  const [metric, setMetric] = useState('out_degree');
  const [top, setTop] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.centrality({ species, metric, top });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const maxScore = result ? Math.max(...result.results.map(r => r.score)) : 1;

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Species</label>
          <select value={species} onChange={e => setSpecies(e.target.value)}>
            <option value="human">Human</option>
            <option value="mouse">Mouse</option>
            <option value="arabidopsis">Arabidopsis</option>
            <option value="tomato">Tomato</option>
            <option value="petunia">Petunia</option>
          </select>
        </div>
        <div className="field">
          <label>Metric</label>
          <select value={metric} onChange={e => setMetric(e.target.value)}>
            <option value="out_degree">Out-degree (targets)</option>
            <option value="in_degree">In-degree (regulators)</option>
            <option value="degree">Total degree</option>
            <option value="betweenness">Betweenness</option>
            <option value="closeness">Closeness</option>
            <option value="eigenvector">Eigenvector</option>
          </select>
        </div>
        <div className="field">
          <label>Top N</label>
          <input type="number" value={top} onChange={e => setTop(+e.target.value)} min={5} max={200} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Computing...' : 'Compute Centrality'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <div className="analysis-table-wrap">
          <table className="analysis-table">
            <thead>
              <tr><th>Rank</th><th>Gene</th><th>Symbol</th><th>TF</th><th>Score</th><th></th></tr>
            </thead>
            <tbody>
              {result.results.map((r, i) => (
                <tr key={r.gene_id}>
                  <td>{i + 1}</td>
                  <td className="mono">{r.gene_id}</td>
                  <td><strong>{r.symbol}</strong></td>
                  <td>{r.is_tf ? 'Yes' : ''}</td>
                  <td>{r.score}</td>
                  <td>
                    <span className="pvalue-bar" style={{
                      width: `${(r.score / maxScore) * 100}px`,
                      background: r.is_tf ? 'var(--primary)' : 'var(--accent)',
                    }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
