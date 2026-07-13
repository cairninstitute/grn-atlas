import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function InferredValidationWorkflow() {
  const [species, setSpecies] = useState('arabidopsis');
  const [geneId, setGeneId] = useState('');
  const [minImportance, setMinImportance] = useState(0.01);
  const [top, setTop] = useState(100);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const run = async () => {
    if (!geneId.trim()) { setError('Gene ID is required'); return; }
    setLoading(true); setError(null); setResult(null);
    try {
      const data = await analysisAPI.inferredEdges({
        species, geneId: geneId.trim(),
        minImportance, top, compareCurated: true,
      });
      if (data.error) throw new Error(data.error);

      const edges = data.edges || [];
      const supported = edges.filter(e => e.curated_support);
      const unsupported = edges.filter(e => !e.curated_support);

      setResult({ edges, supported, unsupported, meta: data });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0 0 12px' }}>
        Find GRNBoost2/GENIE3 predictions, then cross-reference with curated edges to validate which have experimental support.
      </p>
      <div className="analysis-form">
        <div className="field">
          <label>Species</label>
          <select value={species} onChange={e => setSpecies(e.target.value)}>
            <option value="arabidopsis">Arabidopsis</option>
            <option value="tomato">Tomato</option>
            <option value="petunia">Petunia</option>
            <option value="human">Human</option>
            <option value="mouse">Mouse</option>
          </select>
        </div>
        <div className="field">
          <label>Gene ID</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)}
            placeholder="e.g. AT5G11260" />
        </div>
        <div className="field">
          <label>Min Importance</label>
          <input type="number" value={minImportance} onChange={e => setMinImportance(+e.target.value)}
            min={0} step={0.01} style={{ width: 80 }} />
        </div>
        <div className="field">
          <label>Top</label>
          <input type="number" value={top} onChange={e => setTop(+e.target.value)}
            min={1} max={500} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Validating...' : 'Infer → Validate'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.edges.length}</div>
              <div className="stat-label">Inferred edges</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value" style={{ color: 'var(--success, #22c55e)' }}>{result.supported.length}</div>
              <div className="stat-label">Curated support</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.unsupported.length}</div>
              <div className="stat-label">Novel predictions</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">
                {result.edges.length > 0
                  ? `${((result.supported.length / result.edges.length) * 100).toFixed(1)}%`
                  : '-'}
              </div>
              <div className="stat-label">Validation rate</div>
            </div>
          </div>

          {result.supported.length > 0 && (
            <>
              <h4 style={{ fontSize: '0.85rem', margin: '12px 0 6px', color: 'var(--success, #22c55e)' }}>
                Validated by curated evidence ({result.supported.length})
              </h4>
              <div className="analysis-table-wrap" style={{ maxHeight: 200 }}>
                <table className="analysis-table">
                  <thead>
                    <tr><th>Source</th><th>Target</th><th>Method</th><th>Importance</th></tr>
                  </thead>
                  <tbody>
                    {result.supported.map((e, i) => (
                      <tr key={i}>
                        <td className="mono">{e.source_symbol}</td>
                        <td className="mono">{e.target_symbol}</td>
                        <td>{e.method}</td>
                        <td>{e.importance.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {result.unsupported.length > 0 && (
            <>
              <h4 style={{ fontSize: '0.85rem', margin: '12px 0 6px', color: 'var(--text-secondary)' }}>
                Novel predictions — no curated support ({result.unsupported.length})
              </h4>
              <div className="analysis-table-wrap" style={{ maxHeight: 200 }}>
                <table className="analysis-table">
                  <thead>
                    <tr><th>Source</th><th>Target</th><th>Method</th><th>Importance</th></tr>
                  </thead>
                  <tbody>
                    {result.unsupported.slice(0, 50).map((e, i) => (
                      <tr key={i}>
                        <td className="mono">{e.source_symbol}</td>
                        <td className="mono">{e.target_symbol}</td>
                        <td>{e.method}</td>
                        <td>{e.importance.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
