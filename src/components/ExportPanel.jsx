import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';

export default function ExportPanel({ sharedGeneSet }) {
  const [geneIdsText, setGeneIdsText] = useState('');
  const [minConfidence, setMinConfidence] = useState(0);
  const [includeInferred, setIncludeInferred] = useState(true);
  const [signedOnly, setSignedOnly] = useState(false);
  const [includeSequenceContext, setIncludeSequenceContext] = useState(false);
  const [format, setFormat] = useState('json');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (sharedGeneSet?.genes?.length > 0) {
      setGeneIdsText(sharedGeneSet.genes.join(', '));
    }
  }, [sharedGeneSet]);

  const run = async () => {
    const ids = geneIdsText.split(/[,\s]+/).map(s => s.trim()).filter(Boolean);
    if (ids.length === 0) { setError('Provide at least one gene ID'); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.exportEdges({
        geneIds: ids, minConfidence, includeInferred,
        signedOnly, includeSequenceContext, format,
      });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!result) return;
    const isJson = format === 'json';
    const content = isJson ? JSON.stringify(result, null, 2) : result.tsv;
    const blob = new Blob([content], { type: isJson ? 'application/json' : 'text/tab-separated-values' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `grn_edges_export.${isJson ? 'json' : 'tsv'}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field" style={{ minWidth: 220 }}>
          <label>Gene IDs (comma-separated)</label>
          <textarea value={geneIdsText} onChange={e => setGeneIdsText(e.target.value)}
            placeholder="TP53, MYC, BRCA1..." rows={3} style={{ width: '100%' }} />
        </div>
        <div className="field">
          <label>Min Confidence</label>
          <input type="number" value={minConfidence} onChange={e => setMinConfidence(+e.target.value)}
            min={0} max={1} step={0.1} style={{ width: 70 }} />
        </div>
        <div className="field">
          <label>
            <input type="checkbox" checked={includeInferred}
              onChange={e => setIncludeInferred(e.target.checked)} />
            Include Inferred
          </label>
        </div>
        <div className="field">
          <label>
            <input type="checkbox" checked={signedOnly}
              onChange={e => setSignedOnly(e.target.checked)} />
            Signed Only
          </label>
        </div>
        <div className="field">
          <label>
            <input type="checkbox" checked={includeSequenceContext}
              onChange={e => setIncludeSequenceContext(e.target.checked)} />
            Include Sequence Context
          </label>
        </div>
        <div className="field">
          <label>Format</label>
          <select value={format} onChange={e => setFormat(e.target.value)}>
            <option value="json">JSON</option>
            <option value="tsv">TSV</option>
          </select>
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Exporting...' : 'Export Edges'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          <div className="analysis-stats">
            {result.edge_count != null && (
              <div className="analysis-stat">
                <div className="stat-value">{result.edge_count}</div>
                <div className="stat-label">Edges exported</div>
              </div>
            )}
            {result.gene_count != null && (
              <div className="analysis-stat">
                <div className="stat-value">{result.gene_count}</div>
                <div className="stat-label">Genes</div>
              </div>
            )}
          </div>
          <button className="btn-run" onClick={download} style={{ marginTop: 8 }}>
            Download {format.toUpperCase()}
          </button>
        </>
      )}
    </div>
  );
}
