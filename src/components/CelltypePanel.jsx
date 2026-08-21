import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';

export default function CelltypePanel({ currentSpecies, sharedGeneSet }) {
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState('');
  const [clusters, setClusters] = useState([]);
  const [clusterId, setClusterId] = useState('');
  const [clusterB, setClusterB] = useState('');
  const [mode, setMode] = useState('regulation');
  const [geneInput, setGeneInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    analysisAPI.listImportedDatasets().then(d => setDatasets(d.datasets || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (sharedGeneSet?.genes?.length) {
      setGeneInput(sharedGeneSet.genes.join('\n'));
      setMode('upstream');
    }
  }, [sharedGeneSet]);

  const selectDataset = async (dsId) => {
    setDatasetId(dsId);
    try {
      const ds = await analysisAPI.getImportedDataset(dsId);
      setClusters(ds.clusters || []);
      if (ds.clusters?.length) setClusterId(ds.clusters[0].cluster_id);
    } catch {}
  };

  const run = async () => {
    if (!datasetId) { setError('Select an imported dataset first'); return; }
    if (!clusterId) { setError('Select a cluster'); return; }
    setLoading(true); setError(null);
    try {
      let data;
      if (mode === 'regulation') {
        data = await analysisAPI.celltypeRegulation(datasetId, clusterId, currentSpecies);
      } else if (mode === 'upstream') {
        const geneIds = geneInput.split(/[\n,\t]+/).map(g => g.trim()).filter(Boolean);
        if (geneIds.length < 2) { setError('Provide at least 2 gene IDs'); setLoading(false); return; }
        data = await analysisAPI.celltypeUpstream(datasetId, clusterId, geneIds, currentSpecies);
      } else {
        if (!clusterB) { setError('Select a second cluster for comparison'); setLoading(false); return; }
        data = await analysisAPI.celltypeCompare(datasetId, clusterId, clusterB, currentSpecies);
      }
      if (data.detail) throw new Error(data.detail);
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const items = result?.regulators || result?.differential_regulators || [];

  return (
    <div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginBottom: 12 }}>
        Analyze TF regulation in the context of specific cell types or clusters from imported datasets.
        Import a dataset first using the Omics Import panel.
      </p>

      {datasets.length === 0 ? (
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-3)' }}>
          No imported datasets. Use the Omics Import panel to add one.
        </div>
      ) : (
        <div className="analysis-form">
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <div className="field" style={{ flex: 1, minWidth: 150 }}>
              <label>Dataset</label>
              <select value={datasetId} onChange={e => selectDataset(e.target.value)}>
                <option value="">Select...</option>
                {datasets.map(ds => (
                  <option key={ds.dataset_id} value={ds.dataset_id}>{ds.name} ({ds.species})</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Mode</label>
              <select value={mode} onChange={e => setMode(e.target.value)}>
                <option value="regulation">Cluster TF regulators</option>
                <option value="upstream">Cluster-aware upstream</option>
                <option value="compare">Compare clusters</option>
              </select>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
            <div className="field">
              <label>{mode === 'compare' ? 'Cluster A' : 'Cluster'}</label>
              <select value={clusterId} onChange={e => setClusterId(e.target.value)}>
                {clusters.map(c => (
                  <option key={c.cluster_id} value={c.cluster_id}>{c.cluster_name} ({c.n_cells} cells)</option>
                ))}
              </select>
            </div>
            {mode === 'compare' && (
              <div className="field">
                <label>Cluster B</label>
                <select value={clusterB} onChange={e => setClusterB(e.target.value)}>
                  <option value="">Select...</option>
                  {clusters.filter(c => c.cluster_id !== clusterId).map(c => (
                    <option key={c.cluster_id} value={c.cluster_id}>{c.cluster_name} ({c.n_cells} cells)</option>
                  ))}
                </select>
              </div>
            )}
          </div>
          {mode === 'upstream' && (
            <div className="field" style={{ marginTop: 8 }}>
              <label>Gene IDs (one per line)</label>
              <textarea value={geneInput} onChange={e => setGeneInput(e.target.value)} rows={4}
                placeholder={"TP53\nMDM2\nCDKN1A"} />
            </div>
          )}
          <button className="btn-run" onClick={run} disabled={loading} style={{ marginTop: 8 }}>
            {loading ? 'Analyzing…' : 'Run'}
          </button>
        </div>
      )}

      {error && <div className="analysis-error">{error}</div>}

      {result && items.length > 0 && (
        <div className="analysis-table-wrap" style={{ marginTop: 12 }}>
          <table className="analysis-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>TF</th>
                {mode === 'compare' ? (
                  <>
                    <th>Targets Up</th><th>Targets Down</th><th>Diff. Activity</th><th>Direction</th>
                  </>
                ) : (
                  <>
                    <th>Overlap</th><th>Regulon</th>
                    {mode === 'regulation' && <th>P-value</th>}
                    <th>Expressed</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {items.map((r, i) => (
                <tr key={r.gene_id}>
                  <td>{i + 1}</td>
                  <td><strong>{r.symbol}</strong></td>
                  {mode === 'compare' ? (
                    <>
                      <td>{r.targets_up}</td><td>{r.targets_down}</td>
                      <td className="mono">{r.differential_activity.toFixed(4)}</td>
                      <td>{r.direction}</td>
                    </>
                  ) : (
                    <>
                      <td>{r.overlap}</td><td>{r.regulon_size}</td>
                      {mode === 'regulation' && <td className="mono">{r.p_value?.toExponential(2)}</td>}
                      <td>{r.expressed_in_cluster !== undefined ? (r.expressed_in_cluster ? 'Yes' : 'No') : (r.expressed ? 'Yes' : 'No')}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
