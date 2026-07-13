import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function ModulePanel() {
  const [species, setSpecies] = useState('human');
  const [algorithm, setAlgorithm] = useState('louvain');
  const [geneId, setGeneId] = useState('');
  const [resolution, setResolution] = useState(0.01);
  const [topModules, setTopModules] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [expanded, setExpanded] = useState({});

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.modules({
        species, algorithm, geneId: geneId.trim() || null, resolution, topModules,
      });
      if (data.error) throw new Error(data.error);
      setResult(data);
      setExpanded({});
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const toggle = (id) => setExpanded(prev => ({ ...prev, [id]: !prev[id] }));

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
          <label>Algorithm</label>
          <select value={algorithm} onChange={e => setAlgorithm(e.target.value)}>
            <option value="louvain">Louvain</option>
            <option value="leiden">Leiden</option>
            <option value="infomap">Infomap</option>
            <option value="label_propagation">Label Propagation</option>
          </select>
        </div>
        <div className="field">
          <label>Gene ID (optional)</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)}
            placeholder="e.g. TP53" />
        </div>
        <div className="field">
          <label>Resolution</label>
          <input type="number" value={resolution} onChange={e => setResolution(+e.target.value)}
            min={0} step={0.01} style={{ width: 80 }} />
        </div>
        <div className="field">
          <label>Top Modules</label>
          <input type="number" value={topModules} onChange={e => setTopModules(+e.target.value)}
            min={1} max={100} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Detecting...' : 'Detect Modules'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.total_genes}</div>
              <div className="stat-label">Total genes</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.total_edges}</div>
              <div className="stat-label">Total edges</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.num_modules}</div>
              <div className="stat-label">Modules</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.modularity?.toFixed(4) ?? '-'}</div>
              <div className="stat-label">Modularity</div>
            </div>
          </div>

          {result.query_gene_module != null && (
            <div className="analysis-stats" style={{ marginTop: 4 }}>
              <div className="analysis-stat">
                <div className="stat-value">Module {result.query_gene_module}</div>
                <div className="stat-label">Query gene belongs to</div>
              </div>
            </div>
          )}

          <div className="analysis-table-wrap">
            {result.modules.map(m => (
              <div key={m.module_id} style={{
                border: '1px solid var(--border)',
                borderRadius: 6,
                marginBottom: 8,
                padding: '8px 12px',
                background: result.query_gene_module === m.module_id
                  ? 'var(--highlight, rgba(var(--primary-rgb, 99,102,241), 0.08))'
                  : undefined,
              }}>
                <div style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                  onClick={() => toggle(m.module_id)}>
                  <strong>Module {m.module_id}</strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {m.size} genes, {m.num_tfs} TFs | Hub: {m.hub_tf?.symbol || '-'}
                    {expanded[m.module_id] ? ' ▲' : ' ▼'}
                  </span>
                </div>
                {expanded[m.module_id] && (
                  <div style={{ marginTop: 8, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {(m.top_genes || []).map(g => `${g.symbol}${g.is_tf ? ' (TF)' : ''}`).join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
