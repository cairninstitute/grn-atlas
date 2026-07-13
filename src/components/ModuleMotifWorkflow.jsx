import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function ModuleMotifWorkflow() {
  const [species, setSpecies] = useState('human');
  const [algorithm, setAlgorithm] = useState('louvain');
  const [targetModule, setTargetModule] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(null);
  const [error, setError] = useState(null);
  const [modules, setModules] = useState(null);
  const [selectedModule, setSelectedModule] = useState(null);
  const [motifResults, setMotifResults] = useState(null);

  const detectModules = async () => {
    setLoading(true); setError(null); setModules(null); setSelectedModule(null); setMotifResults(null);
    try {
      setStep('Detecting modules...');
      const data = await analysisAPI.modules({ species, algorithm });
      if (data.error) throw new Error(data.error);
      setModules(data);
      setStep(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const enrichModule = async (mod) => {
    setSelectedModule(mod);
    setMotifResults(null);
    setLoading(true); setError(null);
    try {
      const geneIds = (mod.top_genes || []).map(g => g.gene_id);
      if (geneIds.length === 0) { setError('Module has no genes to enrich'); return; }
      setStep(`Running motif enrichment on ${geneIds.length} genes...`);
      const data = await analysisAPI.motifEnrich(geneIds, species);
      if (data.error) throw new Error(data.error);
      setMotifResults(data);
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
        Detect gene communities, then check which TF binding motifs are enriched in a module's promoters.
      </p>
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
          </select>
        </div>
        <button className="btn-run" onClick={detectModules} disabled={loading}>
          {loading && !modules ? step || 'Detecting...' : 'Detect Modules'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {modules && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{modules.num_modules}</div>
              <div className="stat-label">Modules</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{modules.modularity?.toFixed(3)}</div>
              <div className="stat-label">Modularity</div>
            </div>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '8px 0' }}>
            Click a module to run motif enrichment on its genes:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
            {modules.modules.map(m => (
              <button key={m.module_id} className="btn-action"
                onClick={() => enrichModule(m)}
                style={{
                  fontWeight: selectedModule?.module_id === m.module_id ? 700 : 400,
                  borderColor: selectedModule?.module_id === m.module_id ? 'var(--primary)' : undefined,
                }}>
                M{m.module_id} ({m.size} genes, hub: {m.hub_tf?.symbol || '?'})
              </button>
            ))}
          </div>
        </>
      )}

      {loading && selectedModule && (
        <div className="analysis-loading">{step}</div>
      )}

      {motifResults && (
        motifResults.results?.length > 0 ? (
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr><th>TF</th><th>Motif</th><th>Hits</th><th>P-value</th><th>Q-value</th></tr>
              </thead>
              <tbody>
                {motifResults.results.slice(0, 30).map((r, i) => (
                  <tr key={i}>
                    <td><strong>{r.tf_symbol || r.tf}</strong></td>
                    <td className="mono">{r.motif_id || r.jaspar_id}</td>
                    <td>{r.study_count}/{r.background_count}</td>
                    <td>{r.p_value.toExponential(2)}</td>
                    <td>{r.q_value?.toExponential(2) || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', padding: 12 }}>
            No significant motif enrichment found in module {selectedModule?.module_id}.
          </div>
        )
      )}
    </div>
  );
}
