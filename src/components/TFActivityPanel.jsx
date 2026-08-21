import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function TFActivityPanel({ currentSpecies, sharedGeneSet }) {
  const [input, setInput] = useState('');
  const [species, setSpecies] = useState('');
  const [method, setMethod] = useState('ulm');
  const [top, setTop] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [mode, setMode] = useState('tf');

  React.useEffect(() => {
    if (sharedGeneSet?.genes?.length > 1) {
      setInput(sharedGeneSet.genes.map(g => `${g}\t1.0`).join('\n'));
    }
  }, [sharedGeneSet]);

  const parseInput = () => {
    const vals = {};
    input.split('\n').forEach(line => {
      const parts = line.trim().split(/[\t,\s]+/);
      if (parts.length >= 2 && parts[0]) {
        vals[parts[0]] = parseFloat(parts[1]) || 0;
      } else if (parts.length === 1 && parts[0]) {
        vals[parts[0]] = 1.0;
      }
    });
    return vals;
  };

  const run = async () => {
    const geneValues = parseInput();
    if (Object.keys(geneValues).length < 3) {
      setError('Provide at least 3 genes (gene_id <tab> value)');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const sp = species || currentSpecies || undefined;
      let data;
      if (mode === 'tf') {
        data = await analysisAPI.tfActivity(geneValues, sp, { method, top });
      } else {
        data = await analysisAPI.pathwayActivity(geneValues, sp, { top });
      }
      if (data.error || data.detail) throw new Error(data.error || data.detail);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const items = result?.regulators || result?.pathways || [];
  const maxAbsScore = items.length ? Math.max(...items.map(r => Math.abs(r.activity_score))) : 1;

  return (
    <div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginBottom: 12 }}>
        Infer TF or pathway activity from gene-level statistics. Paste gene IDs with values
        (log2FC, z-scores, or expression) — one per line, tab-separated. Gene IDs alone default to value 1.0.
      </p>
      <div className="analysis-form">
        <div className="field" style={{ flex: 1, minWidth: 200 }}>
          <label>Gene values (gene_id &lt;tab&gt; value)</label>
          <textarea value={input} onChange={e => setInput(e.target.value)} rows={6}
            placeholder={"TP53\t3.2\nMDM2\t-1.5\nCDKN1A\t2.8\nBAX\t1.2"} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="field">
            <label>Mode</label>
            <select value={mode} onChange={e => setMode(e.target.value)}>
              <option value="tf">TF Activity</option>
              <option value="pathway">Pathway Activity</option>
            </select>
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
              <option value="rice">Rice</option>
            </select>
          </div>
          {mode === 'tf' && (
            <div className="field">
              <label>Method</label>
              <select value={method} onChange={e => setMethod(e.target.value)}>
                <option value="ulm">ULM (linear model)</option>
                <option value="wmean">Weighted mean</option>
              </select>
            </div>
          )}
          <div className="field">
            <label>Top N</label>
            <input type="number" value={top} onChange={e => setTop(+e.target.value)}
              min={5} max={200} style={{ width: 60 }} />
          </div>
          <button className="btn-run" onClick={run} disabled={loading}>
            {loading ? 'Scoring…' : `Score ${mode === 'tf' ? 'TF' : 'Pathway'} Activity`}
          </button>
        </div>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && items.length > 0 && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.input_genes}</div>
              <div className="stat-label">Input genes</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{items.length}</div>
              <div className="stat-label">{mode === 'tf' ? 'Active TFs' : 'Active pathways'}</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.species}</div>
              <div className="stat-label">Species</div>
            </div>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>{mode === 'tf' ? 'TF' : 'Pathway'}</th>
                  <th>Score</th>
                  <th>t-stat</th>
                  <th>P-value</th>
                  <th>FDR</th>
                  <th>Matched</th>
                  <th>Activity</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r, i) => (
                  <tr key={r.gene_id || r.pathway_id}>
                    <td>{i + 1}</td>
                    <td><strong>{r.symbol || r.pathway_name}</strong></td>
                    <td className="mono">{r.activity_score.toFixed(3)}</td>
                    <td className="mono">{r.t_statistic.toFixed(2)}</td>
                    <td className="mono">{r.p_value.toExponential(2)}</td>
                    <td className="mono">{(r.q_value || 0).toExponential(2)}</td>
                    <td>{r.matched_targets || r.matched_genes}</td>
                    <td>
                      <span style={{
                        display: 'inline-block',
                        width: `${(Math.abs(r.activity_score) / maxAbsScore) * 60}px`,
                        height: 12,
                        background: r.activity_score > 0 ? 'var(--accent, #4a9eff)' : '#e05050',
                        borderRadius: 2,
                      }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {result && items.length === 0 && (
        <p style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}>
          No significant {mode === 'tf' ? 'TF' : 'pathway'} activity found. Try more input genes or a lower threshold.
        </p>
      )}
    </div>
  );
}
