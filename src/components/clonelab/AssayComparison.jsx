import React from 'react';

export default function AssayComparison({ optimization }) {
  if (!optimization) return null;
  const best = optimization.best_digest;
  return (
    <section className="clonelab-panel">
      <div className="clonelab-panel-heading">
        <div><span className="clonelab-step">03</span><h2>Diagnostic digest ranking</h2></div>
        <span className={`clonelab-status ${best.fully_discriminatory ? 'success' : 'warning'}`}>
          {best.fully_discriminatory ? 'All states resolved' : 'Ambiguity remains'}
        </span>
      </div>
      <div className="clonelab-best-assay">
        <div><small>BEST CANDIDATE</small><strong>{best.enzymes.join(' + ')}</strong></div>
        <div><small>PAIRWISE SEPARATION</small><strong>{best.pairwise_distinguishable}/{best.pairwise_total}</strong></div>
        <div><small>INFORMATION</small><strong>{best.information_bits} bits</strong></div>
      </div>
      <table className="clonelab-table">
        <thead><tr><th>Rank</th><th>Digest</th><th>Score</th><th>Unique states</th><th>Verdict</th></tr></thead>
        <tbody>{optimization.rankings.slice(0, 8).map((row, index) => <tr key={row.enzymes.join('-')}>
          <td>{index + 1}</td><td>{row.enzymes.join(' + ')}</td><td>{Math.round(row.score * 100)}%</td>
          <td>{row.unique_hypotheses.length}/{optimization.hypotheses.length}</td>
          <td>{row.fully_discriminatory ? 'Discriminatory' : 'Partial'}</td>
        </tr>)}</tbody>
      </table>
      <p className="clonelab-boundary">{optimization.claim_boundary.sequence_identity}</p>
    </section>
  );
}
