import React, { useState, useEffect } from 'react';

export default function ValidationDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showFullReport, setShowFullReport] = useState(false);

  useEffect(() => {
    fetch('/api/v1/benchmark/status')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) return <div style={{ padding: 16, color: 'var(--text-2)' }}>Loading validation data…</div>;
  if (error) return <div style={{ padding: 16, color: '#e05050' }}>Error: {error}</div>;
  if (!data) return null;

  const { atlas_summary, benchmarks, species_validation } = data;
  const artifactHealth = data.artifact_health || {};
  const summary = artifactHealth.summary || {};
  const healthIsDegraded = artifactHealth.status && artifactHealth.status !== 'ok';

  return (
    <div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginBottom: 12 }}>
        Living validation dashboard — benchmark results, per-species network quality, and atlas coverage.
      </p>

      <div className="analysis-stats">
        <div className="analysis-stat">
          <div className="stat-value">{atlas_summary.genes?.toLocaleString()}</div>
          <div className="stat-label">Genes</div>
        </div>
        <div className="analysis-stat">
          <div className="stat-value">{atlas_summary.interactions?.toLocaleString()}</div>
          <div className="stat-label">Interactions</div>
        </div>
        <div className="analysis-stat">
          <div className="stat-value">{atlas_summary.species?.length}</div>
          <div className="stat-label">Species</div>
        </div>
        <div className="analysis-stat">
          <div className="stat-value">{atlas_summary.tissue_weight_rows?.toLocaleString()}</div>
          <div className="stat-label">Tissue weights</div>
        </div>
      </div>

      <div style={{
        marginTop: 16,
        padding: 12,
        borderRadius: 8,
        border: `1px solid ${healthIsDegraded ? 'rgba(224,80,80,0.45)' : 'rgba(88,160,108,0.35)'}`,
        background: healthIsDegraded ? 'rgba(224,80,80,0.08)' : 'rgba(88,160,108,0.08)',
      }}>
        <h4 style={{ fontSize: '0.9rem', marginBottom: 8 }}>Benchmark artifact health</h4>
        <div className="analysis-table-wrap">
          <table className="analysis-table">
            <tbody>
              <tr>
                <th>Status</th>
                <td style={{ fontWeight: 600, color: healthIsDegraded ? '#d66' : '#6c6' }}>
                  {healthIsDegraded ? 'Degraded' : 'Healthy'}
                </td>
              </tr>
              <tr>
                <th>Validation suite</th>
                <td className="mono">{summary.suite_status || 'unknown'}</td>
              </tr>
              <tr>
                <th>Corpus version</th>
                <td className="mono">{summary.benchmark_corpus_version || 'unknown'}</td>
              </tr>
              <tr>
                <th>Commit</th>
                <td className="mono">{summary.git_sha || 'unknown'}</td>
              </tr>
              <tr>
                <th>Run timestamp</th>
                <td className="mono">{summary.run_at_utc || 'unknown'}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {Array.isArray(artifactHealth.warnings) && artifactHealth.warnings.length > 0 && (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>Warnings</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {artifactHealth.warnings.map((warning, idx) => (
                <li key={`${warning}-${idx}`} style={{ fontSize: '0.8rem', color: 'var(--text-1)' }}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {benchmarks.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ fontSize: '0.9rem', marginBottom: 8 }}>Benchmark Results (AUROC / AUPRC)</h4>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr><th>Species</th><th>Ground truth</th><th>Predictions</th><th>AUROC</th><th>AUPRC</th><th>Prec@100</th></tr>
              </thead>
              <tbody>
                {benchmarks.map((b, i) => (
                  <tr key={i}>
                    <td>{b.species}</td>
                    <td style={{ fontSize: '0.8rem' }}>{b.ground_truth}</td>
                    <td className="mono">{b.n_predictions?.toLocaleString()}</td>
                    <td className="mono" style={{ fontWeight: 600, color: b.auroc >= 0.8 ? '#2a2' : b.auroc >= 0.6 ? '#aa2' : '#a22' }}>
                      {b.auroc?.toFixed(4)}
                    </td>
                    <td className="mono">{b.auprc?.toFixed(4)}</td>
                    <td className="mono">{b.early_precision_100?.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {Object.keys(species_validation).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <h4 style={{ fontSize: '0.9rem', marginBottom: 8 }}>Per-Species Network Quality</h4>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr><th>Species</th><th>Edges</th><th>GO genes</th><th>Coherence (σ)</th><th>Multi-ev. z</th><th>Motif enrichment</th></tr>
              </thead>
              <tbody>
                {Object.entries(species_validation).map(([sp, v]) => {
                  const coh = v.regulon_coherence;
                  const multi = v.multi_evidence;
                  const motif = v.motif_enrichment;
                  return (
                    <tr key={sp}>
                      <td>{sp}</td>
                      <td className="mono">{v.go_coverage?.total_edges?.toLocaleString() || '—'}</td>
                      <td className="mono">{v.go_coverage?.genes_with_go?.toLocaleString() || '—'}</td>
                      <td className="mono">{coh?.sigma != null ? coh.sigma.toFixed(2) : '—'}</td>
                      <td className="mono">{multi?.z_score != null ? multi.z_score.toFixed(2) : '—'}</td>
                      <td className="mono">{motif?.mean_enrichment != null ? `${motif.mean_enrichment.toFixed(1)}×` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <details style={{ marginTop: 16 }}>
        <summary style={{ cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-2)' }}>
          Full validation report (markdown)
        </summary>
        <pre style={{ fontSize: '0.75rem', maxHeight: 400, overflow: 'auto', whiteSpace: 'pre-wrap',
          background: 'var(--surface-1)', padding: 12, borderRadius: 4, marginTop: 8 }}>
          {data.validation_report_md || 'No report available.'}
        </pre>
      </details>
    </div>
  );
}
