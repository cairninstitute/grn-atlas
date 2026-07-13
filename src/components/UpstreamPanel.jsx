import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function UpstreamPanel({ sharedGeneSet }) {
  const [geneText, setGeneText] = useState('');
  const [species, setSpecies] = useState('');
  const [top, setTop] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [expanded, setExpanded] = useState({});

  React.useEffect(() => {
    if (sharedGeneSet?.genes?.length > 1) {
      setGeneText(sharedGeneSet.genes.join(', '));
    }
  }, [sharedGeneSet]);

  const run = async () => {
    const ids = geneText.split(/[,\n\s]+/).map(s => s.trim()).filter(Boolean);
    if (ids.length < 2) { setError('Provide at least 2 gene IDs'); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.upstreamRegulators(ids, species || undefined, { top });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const maxNegLog = result ? Math.max(...result.regulators.map(r => -Math.log10(Math.max(r.p_value, 1e-300)))) : 1;

  return (
    <div>
      <div className="analysis-form">
        <div className="field" style={{ flex: 1, minWidth: 200 }}>
          <label>Gene IDs (comma or newline separated)</label>
          <textarea value={geneText} onChange={e => setGeneText(e.target.value)}
            placeholder="BAX, BCL2, CDKN1A, MDM2, GADD45A..." />
        </div>
        <div className="field">
          <label>Species</label>
          <select value={species} onChange={e => setSpecies(e.target.value)}>
            <option value="">Auto-detect</option>
            <option value="human">Human</option>
            <option value="mouse">Mouse</option>
            <option value="arabidopsis">Arabidopsis</option>
            <option value="tomato">Tomato</option>
            <option value="petunia">Petunia</option>
          </select>
        </div>
        <div className="field">
          <label>Top N</label>
          <input type="number" value={top} onChange={e => setTop(+e.target.value)} min={5} max={200} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Analyzing...' : 'Find Upstream Regulators'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.input_genes}</div>
              <div className="stat-label">Input genes</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.regulators.length}</div>
              <div className="stat-label">Significant TFs</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.species}</div>
              <div className="stat-label">Species</div>
            </div>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr><th>Rank</th><th>TF</th><th>Overlap</th><th>Regulon</th><th>Coverage</th><th>P-value</th><th>Q-value</th><th>Significance</th></tr>
              </thead>
              <tbody>
                {result.regulators.map((r, i) => (
                  <React.Fragment key={r.gene_id}>
                    <tr onClick={() => setExpanded(prev => ({ ...prev, [r.gene_id]: !prev[r.gene_id] }))}
                      style={{ cursor: 'pointer' }}>
                      <td>{i + 1}</td>
                      <td><strong>{r.symbol}</strong></td>
                      <td>{r.overlap_count}</td>
                      <td>{r.regulon_size}</td>
                      <td>{(r.coverage * 100).toFixed(1)}%</td>
                      <td className="mono">{r.p_value.toExponential(2)}</td>
                      <td className="mono">{r.q_value.toExponential(2)}</td>
                      <td>
                        <span className="pvalue-bar" style={{
                          width: `${Math.min((-Math.log10(Math.max(r.p_value, 1e-300)) / maxNegLog) * 100, 100)}px`
                        }} />
                      </td>
                    </tr>
                    {expanded[r.gene_id] && (
                      <tr><td colSpan={8} style={{ background: 'var(--surface-1)', fontSize: '0.8rem', padding: '6px 10px' }}>
                        <strong>Overlap genes:</strong> {r.overlap_genes.join(', ')}
                      </td></tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
