import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

const PATTERN_LABELS = {
  autoregulation: 'Autoregulation',
  feed_forward_loop: 'Feed-Forward Loop',
  bi_fan: 'Bi-Fan',
};

export default function NetworkPatternsPanel() {
  const [geneIds, setGeneIds] = useState('');
  const [species, setSpecies] = useState('');
  const [types, setTypes] = useState({ ffl: true, autoregulation: true, bifan: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const run = async () => {
    if (!geneIds.trim() && !species) { setError('Provide gene IDs or species'); return; }
    setLoading(true);
    setError(null);
    try {
      const ids = geneIds.trim() ? geneIds.split(/[,\s]+/).map(s => s.trim()).filter(Boolean) : null;
      const patternTypes = Object.entries(types).filter(([, v]) => v).map(([k]) => k);
      const data = await analysisAPI.networkPatterns({
        geneIds: ids, species: species || null, patternTypes, limit: 100,
      });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field" style={{ minWidth: 200 }}>
          <label>Gene IDs (comma separated)</label>
          <input type="text" value={geneIds} onChange={e => setGeneIds(e.target.value)}
            placeholder="TP53,MYC,E2F1,NFKB1..." />
        </div>
        <div className="field">
          <label>Or species</label>
          <select value={species} onChange={e => setSpecies(e.target.value)}>
            <option value="">--</option>
            <option value="human">Human</option>
            <option value="mouse">Mouse</option>
            <option value="arabidopsis">Arabidopsis</option>
            <option value="tomato">Tomato</option>
            <option value="petunia">Petunia</option>
          </select>
        </div>
        <div className="field">
          <label>Pattern types</label>
          <div className="checkbox-group">
            {[['ffl', 'FFL'], ['autoregulation', 'Auto'], ['bifan', 'Bi-fan']].map(([k, l]) => (
              <label key={k}>
                <input type="checkbox" checked={types[k]}
                  onChange={e => setTypes(prev => ({ ...prev, [k]: e.target.checked }))} />
                {l}
              </label>
            ))}
          </div>
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Scanning...' : 'Detect Patterns'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.summary.total}</div>
              <div className="stat-label">Patterns found</div>
            </div>
            {Object.entries(result.summary.by_type || {}).map(([t, c]) => (
              <div className="analysis-stat" key={t}>
                <div className="stat-value">{c}</div>
                <div className="stat-label">{PATTERN_LABELS[t] || t}</div>
              </div>
            ))}
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr><th>Type</th><th>Genes</th><th>Details</th></tr>
              </thead>
              <tbody>
                {result.patterns.map((p, i) => (
                  <tr key={i}>
                    <td>{PATTERN_LABELS[p.type] || p.type}</td>
                    <td>{p.genes.map(g => g.symbol).join(' → ')}</td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {p.genes.map(g => `${g.symbol} (${g.role || ''})`).join(', ')}
                    </td>
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
