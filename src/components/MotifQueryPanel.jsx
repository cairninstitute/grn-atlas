import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function MotifQueryPanel() {
  const [geneId, setGeneId] = useState('');
  const [tfGeneId, setTfGeneId] = useState('');
  const [species, setSpecies] = useState('');
  const [maxPvalue, setMaxPvalue] = useState(0.0001);
  const [top, setTop] = useState(100);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const run = async () => {
    if (!geneId.trim() && !tfGeneId.trim()) { setError('Provide Gene ID or TF Gene ID'); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.motifQuery({
        geneId: geneId.trim(), tfGeneId: tfGeneId.trim(),
        species: species || null, maxPvalue, top,
      });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const maxScore = result ? Math.max(...result.hits.map(h => h.score)) : 1;

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Gene ID</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)}
            placeholder="e.g. ENSG00000141510" />
        </div>
        <div className="field">
          <label>TF Gene ID</label>
          <input type="text" value={tfGeneId} onChange={e => setTfGeneId(e.target.value)}
            placeholder="e.g. TP53" />
        </div>
        <div className="field">
          <label>Species (optional)</label>
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
          <label>Max P-value</label>
          <input type="number" value={maxPvalue} onChange={e => setMaxPvalue(+e.target.value)}
            min={0} step={0.0001} style={{ width: 100 }} />
        </div>
        <div className="field">
          <label>Top</label>
          <input type="number" value={top} onChange={e => setTop(+e.target.value)}
            min={1} max={1000} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Querying...' : 'Query Motifs'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.total_hits}</div>
              <div className="stat-label">Total hits</div>
            </div>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>TF Symbol</th><th>Target Gene</th><th>Motif Name</th>
                  <th>Score</th><th>P-value</th><th></th><th>Strand</th>
                </tr>
              </thead>
              <tbody>
                {result.hits.map((h, i) => (
                  <tr key={i}>
                    <td><strong>{h.tf_symbol}</strong></td>
                    <td className="mono">{h.target_symbol}</td>
                    <td>{h.jaspar_id}</td>
                    <td>{h.score.toFixed(2)}</td>
                    <td>{h.p_value.toExponential(2)}</td>
                    <td>
                      <span className="pvalue-bar" style={{
                        width: `${(h.score / maxScore) * 100}px`,
                        background: 'var(--primary)',
                      }} />
                    </td>
                    <td>{h.strand}</td>
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
