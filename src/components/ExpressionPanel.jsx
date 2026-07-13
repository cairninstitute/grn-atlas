import React, { useState, useEffect } from 'react';
import { geneAPI, analysisAPI } from '../services/apiService';
import '../styles/ExpressionPanel.css';

// Per-species expression profile + predicted co-expression partners (petunia, tomato).
// Both are PREDICTED (shallow subsampled RNA-seq, kallisto vs PLAZA CDS);
// co-expression is an undirected association, not measured regulation.
export default function ExpressionPanel({ geneId }) {
  const [profile, setProfile] = useState(null);
  const [coexpr, setCoexpr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([geneAPI.getExpression(geneId), analysisAPI.coexpression(geneId, { top: 12 })])
      .then(([p, c]) => { if (!cancelled) { setProfile(p); setCoexpr(c); } })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [geneId]);

  if (loading) return <div className="expr-panel"><p className="expr-muted">Loading expression…</p></div>;
  if (!profile?.available) return null; // no petunia expression for this gene

  const max = profile.max_tpm || 1;
  return (
    <div className="expr-panel">
      <div className="detail-section">
        <h3 className="section-title">
          Expression <span className="expr-tag">predicted</span>
        </h3>
        <p className="expr-muted">
          Per-tissue TPM across a {profile.samples.length}-sample{profile.species ? ` ${profile.species}` : ''}{' '}
          RNA-seq panel (kallisto vs PLAZA CDS, subsampled). Relative, not absolute.
        </p>
        <div className="expr-bars">
          {profile.samples.map((s, i) => (
            <div key={i} className="expr-row" title={`${s.tpm} TPM · ${s.study}`}>
              <span className="expr-tissue">{s.tissue}</span>
              <div className="expr-track">
                <div className="expr-fill" style={{ width: `${(s.tpm / max) * 100}%` }} />
              </div>
              <span className="expr-val">{s.tpm.toFixed(0)}</span>
            </div>
          ))}
        </div>
      </div>

      {coexpr?.results?.length > 0 && (
        <div className="detail-section">
          <h3 className="section-title">
            Co-expressed genes <span className="expr-tag inferred">Inferred:Expression</span>
          </h3>
          <p className="expr-muted">Predicted co-expression (Pearson r), undirected — not measured regulation.</p>
          <table className="expr-coexpr">
            <thead><tr><th>Gene</th><th>r</th><th></th></tr></thead>
            <tbody>
              {coexpr.results.map((h) => (
                <tr key={h.gene_id}>
                  <td>{h.symbol}{h.is_tf && <span className="expr-tf">TF</span>}</td>
                  <td className={h.r > 0 ? 'expr-pos' : 'expr-neg'}>{h.r.toFixed(2)}</td>
                  <td className="expr-muted">{h.relationship}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
