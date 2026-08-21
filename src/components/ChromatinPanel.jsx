import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';

export default function ChromatinPanel({ currentGene, currentSpecies }) {
  const [support, setSupport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [importMode, setImportMode] = useState(false);
  const [peakInput, setPeakInput] = useState('');
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (currentGene?.id) loadSupport(currentGene.id);
  }, [currentGene?.id]);

  const loadSupport = async (geneId) => {
    setLoading(true);
    try {
      const data = await analysisAPI.chromatinGeneSupport(geneId);
      setSupport(data);
    } catch {}
    finally { setLoading(false); }
  };

  const parsePeaks = () => {
    const lines = peakInput.trim().split('\n').filter(l => l.trim() && !l.startsWith('#'));
    const peaks = [];
    const links = [];
    for (const line of lines) {
      const parts = line.trim().split(/[\t]+/);
      if (parts.length >= 3) {
        const chrom = parts[0];
        const start = parseInt(parts[1]);
        const end = parseInt(parts[2]);
        const peakId = `${chrom}:${start}-${end}`;
        const score = parts.length > 4 ? parseFloat(parts[4]) || 0 : 0;
        const peakType = parts.length > 5 ? parts[5] : null;
        peaks.push({ peak_id: peakId, chrom, start, end, score, peak_type: peakType });
        if (parts.length > 3 && parts[3]) {
          links.push({ peak_id: peakId, gene_id: parts[3], score: score || 0.5, link_type: 'proximity' });
        }
      }
    }
    return { peaks, links };
  };

  const runImport = async () => {
    const { peaks, links } = parsePeaks();
    if (!peaks.length) { setError('No valid peaks parsed'); return; }
    setLoading(true); setError(null);
    try {
      const sp = currentSpecies || 'arabidopsis';
      const data = await analysisAPI.importPeaks({ species: sp, peaks, links: links.length ? links : null });
      if (data.detail) throw new Error(data.detail);
      setImportResult(data);
      if (currentGene?.id) loadSupport(currentGene.id);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const hasPeaks = support?.linked_peaks?.length > 0;
  const hasCis = support?.cis_support?.length > 0;
  const hasMotifs = support?.motif_hits?.length > 0;

  return (
    <div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginBottom: 12 }}>
        View chromatin accessibility peaks, enhancer-gene links, and cis-regulatory support for the current gene.
        Import peaks from ATAC-seq, DAP-seq, or ChIP-seq experiments.
      </p>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button className={`btn-small ${!importMode ? 'active' : ''}`} onClick={() => setImportMode(false)}>
          View Support
        </button>
        <button className={`btn-small ${importMode ? 'active' : ''}`} onClick={() => setImportMode(true)}>
          Import Peaks
        </button>
      </div>

      {importMode ? (
        <div className="analysis-form">
          <div className="field">
            <label>Peaks (BED-like: chrom start end [gene_id] [score] [type])</label>
            <textarea value={peakInput} onChange={e => setPeakInput(e.target.value)} rows={6}
              placeholder={"Chr1\t1000\t2000\tAT1G01010\t50.5\tpromoter\nChr1\t5000\t6000\tAT1G01020\t30.2\tenhancer"} />
          </div>
          <button className="btn-run" onClick={runImport} disabled={loading} style={{ marginTop: 8 }}>
            {loading ? 'Importing…' : 'Import Peaks'}
          </button>
          {importResult && (
            <div className="analysis-stats" style={{ marginTop: 8 }}>
              <div className="analysis-stat"><div className="stat-value">{importResult.n_peaks}</div><div className="stat-label">Peaks</div></div>
              <div className="analysis-stat"><div className="stat-value">{importResult.n_links}</div><div className="stat-label">Gene links</div></div>
            </div>
          )}
        </div>
      ) : (
        <>
          {loading && <div style={{ color: 'var(--text-3)' }}>Loading…</div>}
          {!loading && !currentGene && (
            <div style={{ color: 'var(--text-3)', textAlign: 'center', padding: 16 }}>
              Select a gene to view chromatin support
            </div>
          )}
          {!loading && currentGene && !hasPeaks && !hasCis && (
            <div style={{ color: 'var(--text-3)', textAlign: 'center', padding: 16 }}>
              No chromatin/enhancer data for {currentGene.symbol || currentGene.id}. Import peaks to add support.
            </div>
          )}

          {hasPeaks && (
            <div style={{ marginBottom: 12 }}>
              <strong>Linked peaks ({support.linked_peaks.length})</strong>
              <div className="analysis-table-wrap" style={{ marginTop: 4 }}>
                <table className="analysis-table">
                  <thead><tr><th>Peak</th><th>Type</th><th>Score</th><th>Link</th><th>Distance</th></tr></thead>
                  <tbody>
                    {support.linked_peaks.slice(0, 20).map(p => (
                      <tr key={p.peak_id}>
                        <td className="mono" style={{ fontSize: '0.8rem' }}>{p.chrom}:{p.start}-{p.end}</td>
                        <td>{p.peak_type || '—'}</td>
                        <td className="mono">{p.score?.toFixed(1)}</td>
                        <td className="mono">{p.link_score?.toFixed(3)}</td>
                        <td>{p.distance_bp != null ? `${(p.distance_bp / 1000).toFixed(1)}kb` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {hasCis && (
            <div style={{ marginBottom: 12 }}>
              <strong>Cis-regulatory support ({support.cis_support.length} edges)</strong>
              <div style={{ fontSize: '0.82rem', marginTop: 4 }}>
                {support.cis_support.slice(0, 10).map((c, i) => (
                  <div key={i} style={{ padding: '2px 0' }}>
                    {c.source_id} → {c.target_id}: {c.support_type} (score {c.score?.toFixed(3)})
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasMotifs && (
            <div>
              <strong>Motif hits in peaks ({support.motif_hits.length})</strong>
              <div style={{ fontSize: '0.82rem', marginTop: 4 }}>
                {support.motif_hits.slice(0, 10).map((m, i) => (
                  <div key={i} style={{ padding: '2px 0' }}>
                    {m.motif_id} {m.tf_gene_id ? `(${m.tf_gene_id})` : ''} — score {m.score?.toFixed(2)}
                    {m.pvalue != null && ` p=${m.pvalue.toExponential(2)}`}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {error && <div className="analysis-error">{error}</div>}
    </div>
  );
}
