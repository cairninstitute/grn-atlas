import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

const TYPE_COLORS = { exact: '#22c55e', synonym: '#3b82f6', partial: '#eab308', ortholog: '#f97316', unresolved: '#ef4444' };

export default function LiteratureGroundingPanel({ currentSpecies }) {
  const [terms, setTerms] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!terms.trim()) return;
    setLoading(true); setError(null);
    try {
      const termList = terms.split(/[,\n]+/).map(t => t.trim()).filter(Boolean);
      const data = await analysisAPI.literatureGrounding(termList, currentSpecies);
      setResult(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field" style={{ flex: 1 }}>
          <label>Gene names / symbols from literature (comma or newline-separated)</label>
          <textarea value={terms} onChange={e => setTerms(e.target.value)} placeholder="MYB75, AN2, PAP1, TP53" rows={3} style={{ width: '100%' }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !terms.trim()}>
          {loading ? 'Mapping...' : 'Ground terms'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result && (
        <div>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.n_resolved}/{result.n_terms}</div>
              <div className="stat-label">Resolved</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{(result.resolution_rate * 100).toFixed(0)}%</div>
              <div className="stat-label">Resolution rate</div>
            </div>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead><tr><th>Input</th><th>Match type</th><th>Atlas gene</th><th>Species</th><th>Confidence</th></tr></thead>
              <tbody>
                {result.mappings.map((m, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600 }}>{m.input_term}</td>
                    <td><span style={{ color: TYPE_COLORS[m.match_type], fontWeight: 600 }}>{m.match_type}</span></td>
                    <td className="mono">{m.gene_id || '—'}</td>
                    <td>{m.species || '—'}</td>
                    <td>{m.confidence?.toFixed(2)}</td>
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
