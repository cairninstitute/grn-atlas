import React, { useState, useEffect, useCallback } from 'react';
import { analysisAPI } from '../services/apiService';
import SubgraphGraph from './SubgraphGraph';
import { geneLabel } from '../utils/geneLabel';
import '../styles/GeneSetPanel.css';

const NS_LABEL = { BP: 'process', CC: 'component', MF: 'function', '': '' };

function fmtP(p) {
  if (p === 0) return '0';
  if (p < 0.001) return p.toExponential(1);
  return p.toFixed(3);
}

// Compute out-degree hubs from subgraph edges.
function topHubs(nodes, edges, k = 5) {
  const out = {};
  edges.forEach((e) => { out[e.source] = (out[e.source] || 0) + 1; });
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  return Object.entries(out)
    .sort((a, b) => b[1] - a[1])
    .slice(0, k)
    .map(([id, deg]) => ({ symbol: byId[id] ? geneLabel(byId[id]).label : id, deg }));
}

export default function GeneSetPanel({ open, onClose, initialGeneIds, species, includeInferred }) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [subgraph, setSubgraph] = useState(null);
  const [enrichment, setEnrichment] = useState(null);
  const [pathwayEnr, setPathwayEnr] = useState(null);
  const [traitEnr, setTraitEnr] = useState(null);
  const [motifEnr, setMotifEnr] = useState(null);
  const [lastIds, setLastIds] = useState([]);
  const [lastSpecies, setLastSpecies] = useState(null);
  const [speciesList, setSpeciesList] = useState([]);
  const [speciesB, setSpeciesB] = useState('');
  const [conservation, setConservation] = useState(null);
  const [consLoading, setConsLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    fetch('/api/v1/stats').then((r) => r.json())
      .then((s) => setSpeciesList(s.species_list || [])).catch(() => {});
  }, [open]);

  // Download the sequence-context export (signed edges + coords + promoter windows).
  const exportEdges = async () => {
    const res = await fetch('/api/v1/export/edges', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: lastIds, include_inferred: includeInferred, format: 'tsv',
        promoter_upstream: 2000, promoter_downstream: 500,
      }),
    });
    const text = await res.text();
    const url = URL.createObjectURL(new Blob([text], { type: 'text/tab-separated-values' }));
    const a = document.createElement('a');
    a.href = url; a.download = `grn_edges_export.tsv`; a.click();
    URL.revokeObjectURL(url);
  };

  const analyze = useCallback(async (geneIds, sp) => {
    if (!geneIds || geneIds.length < 2) {
      setError('Provide at least 2 genes.');
      return;
    }
    setLoading(true);
    setError(null);
    setConservation(null);
    try {
      const [sg, enr, penr, tenr, menr] = await Promise.all([
        analysisAPI.subgraph(geneIds, { includeInferred }),
        analysisAPI.enrich(geneIds, sp),
        analysisAPI.pathwayEnrich(geneIds, sp),
        analysisAPI.traitEnrich(geneIds, sp),
        analysisAPI.motifEnrich(geneIds, sp),
      ]);
      setSubgraph(sg);
      setEnrichment(enr);
      setPathwayEnr(penr);
      setTraitEnr(tenr);
      setMotifEnr(menr);
      setLastIds(geneIds);
      setLastSpecies(sp);
      setSpeciesB((prev) => prev && prev !== sp ? prev : '');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [includeInferred]);

  // Auto-run when opened from the network ("analyze this network").
  useEffect(() => {
    if (open && initialGeneIds && initialGeneIds.length) {
      setText(initialGeneIds.join(', '));
      analyze(initialGeneIds, species);
    }
  }, [open, initialGeneIds, species, analyze]);

  if (!open) return null;

  // Resolve pasted tokens (symbols or ids, any species) to gene ids, then analyze.
  const runFromText = async () => {
    const tokens = text.split(/[\s,]+/).map((t) => t.trim()).filter(Boolean);
    if (tokens.length < 2) { setError('Provide at least 2 genes.'); return; }
    setLoading(true);
    setError(null);
    try {
      const resolved = await Promise.all(tokens.map(async (tok) => {
        const r = await fetch(`/api/v1/genes/search?q=${encodeURIComponent(tok)}&limit=1`);
        const d = await r.json();
        return d.results?.[0] || null;
      }));
      const hits = resolved.filter(Boolean);
      if (hits.length < 2) { setError('Could not resolve those genes.'); setLoading(false); return; }
      const counts = {};
      hits.forEach((h) => { counts[h.species] = (counts[h.species] || 0) + 1; });
      const sp = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
      await analyze(hits.map((h) => h.id), sp);
    } catch (e) {
      setError(e.message);
      setLoading(false);
    }
  };

  const runConservation = async () => {
    if (!speciesB || lastIds.length < 2) return;
    setConsLoading(true);
    try {
      setConservation(await analysisAPI.conservation(lastIds, speciesB, { includeInferred }));
    } catch (e) {
      setError(e.message);
    } finally {
      setConsLoading(false);
    }
  };

  const hubs = subgraph ? topHubs(subgraph.nodes, subgraph.edges) : [];

  return (
    <div className="gs-overlay" onClick={onClose}>
      <div className="gs-modal" onClick={(e) => e.stopPropagation()}>
        <div className="gs-header">
          <h2>Gene-set analysis</h2>
          <button className="gs-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <p className="gs-hint">
          Paste gene IDs (human symbols, or locus IDs like AT1G01060 / Solyc… / Peaxi…),
          then Analyze. Species: <strong>{species || 'auto'}</strong>.
        </p>
        <textarea
          className="gs-input"
          rows={3}
          value={text}
          placeholder="TP53, MYC, CDKN1A, BAX, MDM2 …"
          onChange={(e) => setText(e.target.value)}
        />
        <button className="gs-run" onClick={runFromText} disabled={loading}>
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>

        {error && <div className="gs-error">{error}</div>}

        {subgraph && (
          <div className="gs-section">
            <h3>Induced network</h3>
            <p className="gs-metrics">
              {subgraph.nodes.length} genes · {subgraph.edges.length} interactions among them
            </p>
            <button className="gs-export" onClick={exportEdges}
              title="Signed edges + confidence + genomic coordinates + promoter windows (TSS −2000/+500)">
              ⤓ Export edges + promoter windows (TSV)
            </button>
            {hubs.length > 0 && (
              <div className="gs-hubs">
                <span className="gs-label">Top regulators:</span>{' '}
                {hubs.map((h) => (
                  <span key={h.symbol} className="gs-hub">{h.symbol} <em>({h.deg})</em></span>
                ))}
              </div>
            )}
            {subgraph.edges.length > 0 && (
              <SubgraphGraph nodes={subgraph.nodes} edges={subgraph.edges} />
            )}
          </div>
        )}

        {subgraph && subgraph.edges.length > 0 && lastSpecies && (
          <div className="gs-section">
            <h3>Cross-species conservation</h3>
            <div className="gs-cons-controls">
              <span className="gs-label">Compare {lastSpecies} edges to:</span>
              <select value={speciesB} onChange={(e) => setSpeciesB(e.target.value)}>
                <option value="">species…</option>
                {speciesList.filter((s) => s !== lastSpecies).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <button className="gs-run-sm" onClick={runConservation} disabled={!speciesB || consLoading}>
                {consLoading ? '…' : 'Check'}
              </button>
            </div>
            {conservation && (
              <>
                <p className="gs-metrics">
                  {conservation.stats.conserved}/{conservation.stats.edges} edges conserved in{' '}
                  {conservation.species_b} · {conservation.stats.both_orthologs} have orthologs on both sides
                </p>
                <table className="gs-table">
                  <thead><tr><th>Edge ({lastSpecies})</th><th>In {conservation.species_b}</th></tr></thead>
                  <tbody>
                    {conservation.edges.map((e, i) => (
                      <tr key={i}>
                        <td>{e.source_symbol} → {e.target_symbol}</td>
                        <td>{e.conserved
                          ? <span className="gs-cons-yes">✓ {e.b_edges[0].source_ortholog_symbol} → {e.b_edges[0].target_ortholog_symbol}</span>
                          : (e.source_has_ortholog && e.target_has_ortholog
                            ? <span className="gs-cons-no">diverged</span>
                            : <span className="gs-cons-na">no ortholog</span>)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}

        {motifEnr && motifEnr.background > 0 && (
          <div className="gs-section">
            <h3>Motif enrichment</h3>
            <p className="gs-metrics">
              {motifEnr.study} of the genes' promoters scanned · background {motifEnr.background} ·{' '}
              {motifEnr.results.length} enriched TF motifs (FDR)
            </p>
            {motifEnr.results.length === 0 ? (
              <p className="gs-metrics">No significantly enriched TF motifs.</p>
            ) : (
              <table className="gs-table">
                <thead><tr><th>TF (predicted binder)</th><th>genes</th><th>q-value</th></tr></thead>
                <tbody>
                  {motifEnr.results.map((r) => (
                    <tr key={r.tf_gene_id}>
                      <td>{r.tf_symbol}</td>
                      <td className="gs-num">{r.study_count}/{r.background_count}</td>
                      <td className="gs-num">{fmtP(r.q_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {pathwayEnr && pathwayEnr.background > 0 && (
          <div className="gs-section">
            <h3>Pathway enrichment <span className="gs-ns">Reactome</span></h3>
            <p className="gs-metrics">
              {pathwayEnr.study} of the genes in pathways · background {pathwayEnr.background} ·{' '}
              {pathwayEnr.results.length} enriched pathways (FDR)
            </p>
            {pathwayEnr.results.length === 0 ? (
              <p className="gs-metrics">No significantly enriched pathways.</p>
            ) : (
              <table className="gs-table">
                <thead><tr><th>Pathway</th><th>genes</th><th>q-value</th></tr></thead>
                <tbody>
                  {pathwayEnr.results.map((r) => (
                    <tr key={r.pathway_id}>
                      <td>
                        <a href={`https://plantreactome.gramene.org/PathwayBrowser/#/${r.pathway_id}`}
                           target="_blank" rel="noopener noreferrer">{r.name}</a>
                      </td>
                      <td className="gs-num">{r.study_count}/{r.background_count}</td>
                      <td className="gs-num">{fmtP(r.q_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {traitEnr && traitEnr.background > 0 && traitEnr.results.length > 0 && (
          <div className="gs-section">
            <h3>Trait associations <span className="gs-ns">GWAS Catalog</span></h3>
            <p className="gs-metrics">
              {traitEnr.study} of the genes have GWAS traits · background {traitEnr.background} ·{' '}
              {traitEnr.results.length} enriched traits (FDR). Statistical associations, not regulation.
            </p>
            <table className="gs-table">
              <thead><tr><th>Trait</th><th>genes</th><th>q-value</th></tr></thead>
              <tbody>
                {traitEnr.results.map((r, i) => (
                  <tr key={i}>
                    <td>{r.trait}</td>
                    <td className="gs-num">{r.study_count}/{r.background_count}</td>
                    <td className="gs-num">{fmtP(r.q_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {enrichment && (
          <div className="gs-section">
            <h3>GO enrichment</h3>
            <p className="gs-metrics">
              {enrichment.study} of the genes annotated · background {enrichment.background} ·{' '}
              {enrichment.results.length} enriched terms (FDR-adjusted)
            </p>
            {enrichment.results.length === 0 ? (
              <p className="gs-metrics">No significantly enriched terms.</p>
            ) : (
              <table className="gs-table">
                <thead>
                  <tr><th>GO term</th><th></th><th>genes</th><th>q-value</th></tr>
                </thead>
                <tbody>
                  {enrichment.results.map((r) => (
                    <tr key={r.go_id}>
                      <td>
                        <a href={`https://amigo.geneontology.org/amigo/term/${r.go_id}`}
                           target="_blank" rel="noopener noreferrer">{r.name}</a>
                      </td>
                      <td className="gs-ns">{NS_LABEL[r.namespace] ?? r.namespace}</td>
                      <td className="gs-num">{r.study_count}/{r.background_count}</td>
                      <td className="gs-num">{fmtP(r.q_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
