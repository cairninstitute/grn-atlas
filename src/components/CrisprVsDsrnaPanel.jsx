import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function CrisprVsDsrnaPanel({ currentGene, currentSpecies }) {
  const [geneIds, setGeneIds] = useState(currentGene?.id || '');
  const [intent, setIntent] = useState('knockdown');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!geneIds.trim()) return;
    setLoading(true); setError(null);
    try {
      const ids = geneIds.split(/[,\s]+/).filter(Boolean);
      const data = await analysisAPI.crisprVsDsrna(ids, currentSpecies, intent);
      setResult(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Gene IDs (comma-separated)</label>
          <input type="text" value={geneIds} onChange={e => setGeneIds(e.target.value)} placeholder="AT1G56650, AT5G42910" style={{ minWidth: 250 }} />
        </div>
        <div className="field">
          <label>Intent</label>
          <select value={intent} onChange={e => setIntent(e.target.value)}>
            <option value="knockdown">Knockdown</option>
            <option value="knockout">Knockout</option>
          </select>
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !geneIds.trim()}>
          {loading ? 'Comparing...' : 'Compare strategies'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result?.comparisons?.map((c, i) => (
        <div key={i} style={{ marginBottom: 16, border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>{c.symbol || c.gene_id} {c.is_tf && <span style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>(TF)</span>}</div>
          {!c.found ? <div style={{ color: 'var(--text-secondary)' }}>Gene not found</div> : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 8 }}>
                <div style={{ background: 'var(--surface-1)', padding: 10, borderRadius: 6 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>CRISPR</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {c.crispr.mode} · Specificity: {c.crispr.specificity} · {c.crispr.reversible ? 'Reversible' : 'Irreversible'}
                  </div>
                </div>
                <div style={{ background: 'var(--surface-1)', padding: 10, borderRadius: 6 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>dsRNA/RNAi</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Feasibility: {c.dsrna.feasibility} · {c.dsrna.specificity} · Reversible
                  </div>
                </div>
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--primary)' }}>
                Recommendation: {c.recommendation}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
