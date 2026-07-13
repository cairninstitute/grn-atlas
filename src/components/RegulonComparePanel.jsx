import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function RegulonComparePanel({ onShareGenes }) {
  const [tfA, setTfA] = useState('');
  const [tfB, setTfB] = useState('');
  const [depth, setDepth] = useState(2);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const run = async () => {
    if (!tfA.trim() || !tfB.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.regulonCompare(tfA.trim(), tfB.trim(), { depth });
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const venn = (a, b, overlap) => {
    const maxR = 80;
    const rA = Math.max(20, maxR * Math.sqrt(a / Math.max(a, b, 1)));
    const rB = Math.max(20, maxR * Math.sqrt(b / Math.max(a, b, 1)));
    const overlapRatio = overlap / Math.max(Math.min(a, b), 1);
    const sep = Math.max(0, (rA + rB) * (1 - overlapRatio)) * (1 - overlapRatio * 0.3);
    const cx1 = 120, cx2 = 120 + sep;
    const w = cx2 + rB + 30;
    return (
      <svg className="venn-svg" width={w} height={200} viewBox={`0 0 ${w} 200`}>
        <circle cx={cx1} cy={100} r={rA} fill="rgba(59,139,212,0.25)" stroke="var(--primary)" strokeWidth="2" />
        <circle cx={cx2} cy={100} r={rB} fill="rgba(127,119,221,0.25)" stroke="var(--accent)" strokeWidth="2" />
        <text x={cx1 - rA * 0.4} y={100} textAnchor="middle" fontSize="13" fontWeight="bold" fill="var(--primary-dark)">{a}</text>
        <text x={cx2 + rB * 0.4} y={100} textAnchor="middle" fontSize="13" fontWeight="bold" fill="var(--accent-dark)">{b}</text>
        {overlap > 0 && <text x={(cx1 + cx2) / 2} y={100} textAnchor="middle" fontSize="13" fontWeight="bold" fill="var(--text-primary)">{overlap}</text>}
        <text x={cx1} y={190} textAnchor="middle" fontSize="11" fill="var(--text-secondary)">{result?.tf_a?.symbol}</text>
        <text x={cx2} y={190} textAnchor="middle" fontSize="11" fill="var(--text-secondary)">{result?.tf_b?.symbol}</text>
      </svg>
    );
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>TF A</label>
          <input type="text" value={tfA} onChange={e => setTfA(e.target.value)} placeholder="e.g. TP53" />
        </div>
        <div className="field">
          <label>TF B</label>
          <input type="text" value={tfB} onChange={e => setTfB(e.target.value)} placeholder="e.g. MYC" />
        </div>
        <div className="field">
          <label>Depth</label>
          <input type="number" value={depth} onChange={e => setDepth(+e.target.value)} min={1} max={4} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading || !tfA.trim() || !tfB.trim()}>
          {loading ? 'Running...' : 'Compare'}
        </button>
      </div>

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          {venn(result.tf_a.regulon_size, result.tf_b.regulon_size, result.overlap_size)}
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{result.jaccard.toFixed(4)}</div>
              <div className="stat-label">Jaccard</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.p_value.toExponential(2)}</div>
              <div className="stat-label">P-value</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.overlap_size}</div>
              <div className="stat-label">Overlap</div>
            </div>
            <div className="analysis-stat">
              <div className="stat-value">{result.union_size}</div>
              <div className="stat-label">Union</div>
            </div>
          </div>
          {onShareGenes && result.overlap_genes.length > 0 && (
            <div className="analysis-actions">
              <button className="btn-action" onClick={() =>
                onShareGenes('upstream', result.overlap_genes,
                  `${result.tf_a.symbol} / ${result.tf_b.symbol} overlap`)}>
                Find upstream regulators of overlap
              </button>
            </div>
          )}
          {result.overlap_genes.length > 0 && (
            <div className="analysis-table-wrap">
              <table className="analysis-table">
                <thead><tr><th>Overlap Genes ({result.overlap_size})</th></tr></thead>
                <tbody>
                  {result.overlap_genes.slice(0, 200).map(g => (
                    <tr key={g}><td className="mono">{g}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
