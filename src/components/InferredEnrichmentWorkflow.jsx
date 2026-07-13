import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function InferredEnrichmentWorkflow() {
  const [species, setSpecies] = useState('arabidopsis');
  const [geneId, setGeneId] = useState('');
  const [method, setMethod] = useState('any');
  const [minImportance, setMinImportance] = useState(0.01);
  const [top, setTop] = useState(100);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(null);
  const [error, setError] = useState(null);
  const [edges, setEdges] = useState(null);
  const [enrichment, setEnrichment] = useState(null);

  const run = async () => {
    if (!geneId.trim()) { setError('Gene ID is required'); return; }
    setLoading(true); setError(null); setEdges(null); setEnrichment(null);
    try {
      setStep('Finding inferred targets...');
      const edgeData = await analysisAPI.inferredEdges({
        species, geneId: geneId.trim(),
        method: method === 'any' ? null : method,
        minImportance, top, direction: 'targets',
      });
      if (edgeData.error) throw new Error(edgeData.error);
      setEdges(edgeData);
      const targetIds = edgeData.edges.map(e => e.target_id);
      if (targetIds.length === 0) { setError('No inferred targets found'); return; }

      setStep(`Running GO enrichment on ${targetIds.length} targets...`);
      const enrichData = await analysisAPI.enrich(targetIds, species);
      if (enrichData.error) throw new Error(enrichData.error);
      setEnrichment(enrichData);
      setStep(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0 0 12px' }}>
        Find predicted targets of a TF via GRNBoost2/GENIE3, then run GO enrichment on the target set.
      </p>
      <div className="analysis-form">
        <div className="field">
          <label>Species</label>
          <select value={species} onChange={e => setSpecies(e.target.value)}>
            <option value="arabidopsis">Arabidopsis</option>
            <option value="tomato">Tomato</option>
            <option value="petunia">Petunia</option>
          </select>
        </div>
        <div className="field">
          <label>TF Gene ID</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)}
            placeholder="e.g. AT5G11260" />
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
          <label>Top Targets</label>
          <input type="number" value={top} onChange={e => setTop(+e.target.value)}
            min={1} max={500} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? step || 'Running...' : 'Infer → Enrich'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {edges && (
        <div className="analysis-stats">
          <div className="analysis-stat">
            <div className="stat-value">{edges.returned}</div>
            <div className="stat-label">Inferred targets</div>
          </div>
          <div className="analysis-stat">
            <div className="stat-value">{edges.total_available}</div>
            <div className="stat-label">Total available</div>
          </div>
        </div>
      )}

      {enrichment && enrichment.results?.length > 0 && (
        <div className="analysis-table-wrap">
          <table className="analysis-table">
            <thead>
              <tr><th>GO Term</th><th>Name</th><th>NS</th><th>Hits</th><th>P-value</th><th>Q-value</th></tr>
            </thead>
            <tbody>
              {enrichment.results.slice(0, 30).map((r, i) => (
                <tr key={i}>
                  <td className="mono">{r.go_id}</td>
                  <td>{r.name}</td>
                  <td>{r.namespace}</td>
                  <td>{r.study_count}/{r.background_count}</td>
                  <td>{r.p_value.toExponential(2)}</td>
                  <td>{r.q_value.toExponential(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {enrichment && enrichment.results?.length === 0 && (
        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', padding: 12 }}>
          No significant GO enrichment found in the inferred target set.
        </div>
      )}
    </div>
  );
}
