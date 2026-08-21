import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';

export default function OmicsImportPanel({ currentSpecies }) {
  const [name, setName] = useState('');
  const [species, setSpecies] = useState('');
  const [dataType, setDataType] = useState('bulk');
  const [input, setInput] = useState('');
  const [contrastInput, setContrastInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [validation, setValidation] = useState(null);

  useEffect(() => { loadDatasets(); }, []);

  const loadDatasets = async () => {
    try {
      const data = await analysisAPI.listImportedDatasets();
      setDatasets(data.datasets || []);
    } catch {}
  };

  const parseMatrix = () => {
    const lines = input.trim().split('\n').filter(l => l.trim());
    if (!lines.length) return {};
    const geneValues = {};
    for (const line of lines) {
      const parts = line.trim().split(/[\t,]+/);
      if (parts.length >= 2) {
        const gid = parts[0];
        geneValues[gid] = parts.slice(1).map(v => parseFloat(v) || 0);
      }
    }
    return geneValues;
  };

  const parseContrasts = () => {
    if (!contrastInput.trim()) return null;
    const lines = contrastInput.trim().split('\n').filter(l => l.trim());
    const degs = {};
    let groupA = 'group_A', groupB = 'group_B';
    for (const line of lines) {
      if (line.startsWith('#')) {
        const parts = line.replace('#', '').trim().split(/\s+vs\s+/i);
        if (parts.length === 2) { groupA = parts[0]; groupB = parts[1]; }
        continue;
      }
      const parts = line.trim().split(/[\t,]+/);
      if (parts.length >= 2) degs[parts[0]] = parseFloat(parts[1]) || 0;
    }
    return Object.keys(degs).length ? [{ group_a: groupA, group_b: groupB, deg: degs }] : null;
  };

  const runImport = async () => {
    const geneValues = parseMatrix();
    if (Object.keys(geneValues).length < 3) {
      setError('Provide at least 3 genes in the matrix');
      return;
    }
    setLoading(true); setError(null);
    try {
      const sp = species || currentSpecies || 'human';
      const data = await analysisAPI.importOmics({
        name: name || 'Untitled dataset',
        species: sp, data_type: dataType,
        gene_values: geneValues,
        contrasts: parseContrasts(),
      });
      if (data.detail) throw new Error(data.detail);
      setResult(data);
      loadDatasets();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const runValidation = async (dsId) => {
    try {
      const data = await analysisAPI.validateImport(dsId);
      setValidation(data);
    } catch (e) { setError(e.message); }
  };

  return (
    <div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginBottom: 12 }}>
        Import gene expression data for use with cell-type, activity, and enrichment workflows.
        Paste a gene×sample matrix (gene_id, value1, value2, ...) — one gene per line, tab or comma separated.
      </p>

      {datasets.length > 0 && (
        <div style={{ marginBottom: 16, padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
          <strong>Imported datasets ({datasets.length})</strong>
          <div style={{ fontSize: '0.82rem', marginTop: 4 }}>
            {datasets.map(ds => (
              <div key={ds.dataset_id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '2px 0' }}>
                <span>{ds.name}</span>
                <span style={{ color: 'var(--text-3)' }}>{ds.species} · {ds.data_type} · {ds.n_features} genes</span>
                <button className="btn-small" onClick={() => runValidation(ds.dataset_id)}>Validate</button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="analysis-form">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div className="field" style={{ flex: 1, minWidth: 150 }}>
            <label>Dataset name</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="My experiment" />
          </div>
          <div className="field">
            <label>Species</label>
            <select value={species} onChange={e => setSpecies(e.target.value)}>
              <option value="">Auto</option>
              <option value="human">Human</option>
              <option value="mouse">Mouse</option>
              <option value="arabidopsis">Arabidopsis</option>
              <option value="tomato">Tomato</option>
              <option value="petunia">Petunia</option>
              <option value="rice">Rice</option>
            </select>
          </div>
          <div className="field">
            <label>Data type</label>
            <select value={dataType} onChange={e => setDataType(e.target.value)}>
              <option value="bulk">Bulk RNA-seq</option>
              <option value="pseudobulk">Pseudobulk</option>
              <option value="scRNA">scRNA-seq</option>
            </select>
          </div>
        </div>
        <div className="field" style={{ marginTop: 8 }}>
          <label>Gene × Sample matrix</label>
          <textarea value={input} onChange={e => setInput(e.target.value)} rows={6}
            placeholder={"TP53\t5.2\t3.1\t7.8\nMDM2\t2.3\t4.5\t1.2\nCDKN1A\t8.1\t6.2\t9.3"} />
        </div>
        <div className="field" style={{ marginTop: 8 }}>
          <label>DEG contrast (optional: # group_A vs group_B, then gene_id log2FC)</label>
          <textarea value={contrastInput} onChange={e => setContrastInput(e.target.value)} rows={4}
            placeholder={"# treated vs control\nTP53\t2.5\nMDM2\t-1.8\nCDKN1A\t3.1"} />
        </div>
        <button className="btn-run" onClick={runImport} disabled={loading} style={{ marginTop: 8 }}>
          {loading ? 'Importing…' : 'Import Dataset'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <div className="analysis-stats" style={{ marginTop: 12 }}>
          <div className="analysis-stat"><div className="stat-value">{result.dataset_id}</div><div className="stat-label">Dataset ID</div></div>
          <div className="analysis-stat"><div className="stat-value">{result.n_features}</div><div className="stat-label">Features</div></div>
          <div className="analysis-stat"><div className="stat-value">{result.n_samples}</div><div className="stat-label">Samples</div></div>
          <div className="analysis-stat"><div className="stat-value">{result.n_clusters}</div><div className="stat-label">Clusters</div></div>
        </div>
      )}

      {validation && (
        <div style={{ marginTop: 12, padding: '10px 14px', background: 'var(--bg-2)', borderRadius: 6 }}>
          <strong>Validation: {validation.match_pct}% gene overlap with atlas</strong>
          <div style={{ fontSize: '0.82rem', marginTop: 4 }}>
            {validation.matched} / {validation.imported_features} imported genes found in {validation.species} atlas ({validation.atlas_genes} genes)
          </div>
          {!validation.valid && (
            <div style={{ color: '#e05050', fontSize: '0.82rem', marginTop: 4 }}>
              Low overlap — check species and gene ID format
            </div>
          )}
        </div>
      )}
    </div>
  );
}
