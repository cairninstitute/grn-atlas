import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function InterventionRankerPanel({ currentGene, currentSpecies }) {
  const [geneIds, setGeneIds] = useState(currentGene?.id || '');
  const [intent, setIntent] = useState('knockdown');
  const [budget, setBudget] = useState('moderate');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async () => {
    if (!geneIds.trim()) return;
    setLoading(true); setError(null);
    try {
      const ids = geneIds.split(/[,\s]+/).filter(Boolean);
      const data = await analysisAPI.interventionRank(ids, currentSpecies, intent, budget);
      setResult(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Gene IDs</label>
          <input type="text" value={geneIds} onChange={e => setGeneIds(e.target.value)} placeholder="AT1G56650, AT5G42910" style={{ minWidth: 250 }} />
        </div>
        <div className="field">
          <label>Intent</label>
          <select value={intent} onChange={e => setIntent(e.target.value)}>
            <option value="knockdown">Knockdown</option>
            <option value="knockout">Knockout</option>
          </select>
        </div>
        <div className="field">
          <label>Budget</label>
          <select value={budget} onChange={e => setBudget(e.target.value)}>
            <option value="low">Low</option>
            <option value="moderate">Moderate</option>
            <option value="high">High</option>
          </select>
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !geneIds.trim()}>
          {loading ? 'Ranking...' : 'Rank strategies'}
        </button>
      </div>
      {error && <div className="analysis-error">{error}</div>}
      {result?.candidates?.map((c, i) => (
        <div key={i} style={{ marginBottom: 14, border: '1px solid var(--border)', borderRadius: 8, padding: 14 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {c.symbol || c.gene_id}
            {c.is_tf && <span style={{ fontSize: '0.75rem', color: 'var(--primary)', marginLeft: 6 }}>TF ({c.regulon_size} targets)</span>}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            {c.strategies.map((s, j) => (
              <div key={j} style={{
                background: s.mode === c.recommended ? 'var(--primary)' : 'var(--surface-1)',
                color: s.mode === c.recommended ? 'white' : 'var(--text-primary)',
                padding: '6px 12px', borderRadius: 6, fontSize: '0.8rem',
              }}>
                <div style={{ fontWeight: 600 }}>{s.mode}</div>
                <div>Feasibility: {s.feasibility} · Specificity: {s.specificity}</div>
                <div>{s.complexity} cost · {s.reversible ? 'reversible' : 'permanent'}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--primary)', fontWeight: 600 }}>
            Recommended: {c.recommended}
          </div>
        </div>
      ))}
    </div>
  );
}
