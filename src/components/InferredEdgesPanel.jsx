import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';

export default function InferredEdgesPanel({ onShareGenes: _onShareGenes, sharedGeneSet }) {
  const [species, setSpecies] = useState('human');
  const [geneId, setGeneId] = useState('');
  const [direction, setDirection] = useState('both');
  const [method, setMethod] = useState('any');
  const [minImportance, setMinImportance] = useState(0.01);
  const [compareCurated, setCompareCurated] = useState(false);
  const [top, setTop] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (sharedGeneSet?.genes?.length === 1) {
      setGeneId(sharedGeneSet.genes[0]);
    }
  }, [sharedGeneSet]);

  const run = async () => {
    if (!geneId.trim()) { setError('Gene ID is required'); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.inferredEdges({
        species, geneId: geneId.trim(), direction,
        method: method === 'any' ? null : method,
        minImportance, compareCurated, top,
      });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const maxImportance = result ? Math.max(...result.edges.map(e => e.importance)) : 1;

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
          <label>Gene ID</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)}
            placeholder="e.g. TP53" />
        </div>
        <div className="field">
          <label>Direction</label>
          <select value={direction} onChange={e => setDirection(e.target.value)}>
            <option value="both">Both</option>
            <option value="regulators">Regulators</option>
            <option value="targets">Targets</option>
          </select>
        </div>
        <div className="field">
          <label>Method</label>
          <select value={method} onChange={e => setMethod(e.target.value)}>
            <option value="any">Any</option>
            <option value="GRNBoost2">GRNBoost2</option>
            <option value="GENIE3">GENIE3</option>
          </select>
        </div>
        <div className="field">
          <label>Min Importance</label>
          <input type="number" value={minImportance} onChange={e => setMinImportance(+e.target.value)}
            min={0} step={0.01} style={{ width: 80 }} />
        </div>
        <div className="field">
          <label>
            <input type="checkbox" checked={compareCurated}
              onChange={e => setCompareCurated(e.target.checked)} />
            Compare Curated
          </label>
        </div>
        <div className="field">
          <label>Top</label>
          <input type="number" value={top} onChange={e => setTop(+e.target.value)}
            min={1} max={500} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Querying...' : 'Query Inferred Edges'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.returned}</div>
              <div className="stat-label">Returned</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.total_available}</div>
              <div className="stat-label">Total available</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.method}</div>
              <div className="stat-label">Method</div>
            </div>
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Rank</th><th>Source</th><th>Target</th><th>Method</th>
                  <th>Importance</th><th></th>
                  {compareCurated && <th>Curated Support</th>}
                </tr>
              </thead>
              <tbody>
                {result.edges.map((e, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td className="mono">{e.source_symbol}</td>
                    <td className="mono">{e.target_symbol}</td>
                    <td>{e.method}</td>
                    <td>{e.importance.toFixed(4)}</td>
                    <td>
                      <span className="pvalue-bar" style={{
                        width: `${(e.importance / maxImportance) * 100}px`,
                        background: 'var(--primary)',
                      }} />
                    </td>
                    {compareCurated && <td>{e.curated_support ? 'Yes' : 'No'}</td>}
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
