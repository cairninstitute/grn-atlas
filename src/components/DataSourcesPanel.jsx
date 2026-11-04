import React, { useEffect, useState } from 'react';
import { proteinAPI } from '../services/apiService';
import '../styles/DataSourcesPanel.css';

const GLOSSARY = [
  ['Transcription factor (TF)', 'A protein that binds DNA to switch other genes on or off.'],
  ['Regulator / target', 'A regulator (TF) controls a target gene; edges point regulator → target.'],
  ['Activation / repression', 'Whether a regulator increases (activation) or decreases (repression) its target.'],
  ['Ortholog', 'The “same” gene in a different species, descended from a common ancestor.'],
  ['Synteny', 'Conserved gene order along chromosomes between species, shown as ribbons.'],
  ['Confidence', 'How well-supported an interaction is (evidence count / method); filterable.'],
  ['Inferred edge', 'A regulatory edge predicted for tomato/petunia by projecting the Arabidopsis network through orthology — a prediction, not a measurement.'],
];

function download(text, filename, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export default function DataSourcesPanel({ open, onClose }) {
  const [stats, setStats] = useState(null);
  const [prov, setProv] = useState(null);
  const [fresh, setFresh] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [compLayers, setCompLayers] = useState(null);

  useEffect(() => {
    if (!open) return;
    fetch('/api/v1/stats').then((r) => r.json()).then(setStats).catch(() => {});
    fetch('/api/v1/provenance').then((r) => r.json()).then(setProv).catch(() => {});
    fetch('/api/v1/provenance/freshness').then((r) => r.json()).then(setFresh).catch(() => {});
    fetch('/api/v1/species').then((r) => r.json()).then(setCoverage).catch(() => {});
    Promise.all([
      proteinAPI.esm2Stats().catch(() => null),
      proteinAPI.alphafoldStats().catch(() => null),
      proteinAPI.structuralBindingStats().catch(() => null),
      proteinAPI.signTransferStats().catch(() => null),
    ]).then(([esm2, af, sb, st]) => setCompLayers({ esm2, alphafold: af, structural: sb, signTransfer: st }));
  }, [open]);

  // key -> {status, latest_version} for the data-currency badge
  const freshBy = Object.fromEntries((fresh?.sources || []).map((s) => [s.key, s]));

  if (!open) return null;

  const exportBib = async () => {
    const bib = await fetch('/api/v1/citations.bib').then((r) => r.text());
    download(bib, 'grn_atlas_citations.bib', 'application/x-bibtex');
  };
  const exportManifest = () => {
    if (prov) download(JSON.stringify(prov, null, 2), 'grn_atlas_provenance.json', 'application/json');
  };

  return (
    <div className="ds-overlay" onClick={onClose}>
      <div className="ds-modal" onClick={(e) => e.stopPropagation()}>
        <div className="ds-header">
          <h2>Data sources &amp; citations</h2>
          <button className="ds-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        {stats && (
          <p className="ds-stats">
            {stats.species} species · {stats.genes?.toLocaleString()} genes ·{' '}
            {stats.interactions?.toLocaleString()} interactions
            {prov && <> · atlas v{prov.atlas_version}</>}
          </p>
        )}

        <p className="ds-note">
          Darwin combines measured regulation with <strong>inferred</strong> edges —
          the Arabidopsis network projected onto tomato and petunia through orthology.
          Inferred edges are shown dashed and labeled, and can be hidden with the
          “Include inferred edges” filter. They are predictions, not measurements.
        </p>

        <div className="ds-downloads">
          <button className="ds-dl-btn" onClick={exportManifest} disabled={!prov}>⤓ Provenance manifest (JSON)</button>
          <button className="ds-dl-btn" onClick={exportBib}>⤓ Citations (BibTeX)</button>
        </div>

        {coverage?.species && (
          <div className="ds-coverage">
            <h3 className="ds-subhead">Data coverage by species</h3>
            <table className="ds-cov-table">
              <thead>
                <tr>
                  <th>Species</th><th title="measured / inferred edges">network</th>
                  <th>orthologs</th><th title="predicted TF binding sites">binding</th>
                  <th title="RNA-seq samples">expression</th>
                  <th>pathways</th><th title="GWAS trait associations">traits</th>
                </tr>
              </thead>
              <tbody>
                {coverage.species.map((s) => {
                  const L = s.layers;
                  const cell = (n) => (n ? <span className="ds-cov-yes">{n.toLocaleString()}</span>
                    : <span className="ds-cov-no">—</span>);
                  return (
                    <tr key={s.species}>
                      <td className="ds-cov-sp">{s.species}</td>
                      <td>{cell(L.network.measured_edges)}<span className="ds-cov-inf">
                        {L.network.inferred_edges ? ` +${L.network.inferred_edges.toLocaleString()}i` : ''}</span></td>
                      <td>{cell(L.orthologs)}</td>
                      <td>{cell(L.binding_sites)}</td>
                      <td>{cell(L.expression_samples)}</td>
                      <td>{cell(L.pathway_annotations)}</td>
                      <td>{cell(L.trait_associations)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="ds-note" style={{ marginTop: 4 }}>
              Empty cells are onboarding opportunities. “+Ni” = inferred edges (predicted, not measured).
            </p>
          </div>
        )}

        {compLayers && (
          <div className="ds-coverage" style={{ marginTop: 16 }}>
            <h3 className="ds-subhead">Computational layers</h3>
            <p className="ds-note" style={{ marginBottom: 8 }}>
              Machine-learning predictions and protein features — labeled as <strong>predicted</strong>, not measured.
            </p>
            <table className="ds-cov-table">
              <thead>
                <tr><th>Layer</th><th>Coverage</th><th>Detail</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td className="ds-cov-sp">ESM2 embeddings</td>
                  <td>{compLayers.esm2?.total
                    ? <span className="ds-cov-yes">{compLayers.esm2.total.toLocaleString()} proteins</span>
                    : <span className="ds-cov-no">not computed</span>}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-2)' }}>
                    {compLayers.esm2?.stats && Object.entries(compLayers.esm2.stats).map(([sp, v]) =>
                      `${sp}: ${v.count}`).join(', ')}
                  </td>
                </tr>
                <tr>
                  <td className="ds-cov-sp">AlphaFold features</td>
                  <td>{compLayers.alphafold?.total
                    ? <span className="ds-cov-yes">{compLayers.alphafold.total.toLocaleString()} structures</span>
                    : <span className="ds-cov-no">not fetched</span>}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-2)' }}>
                    {compLayers.alphafold?.stats && Object.entries(compLayers.alphafold.stats).map(([sp, v]) =>
                      `${sp}: ${v.count} (avg pLDDT ${v.avg_plddt ?? '?'})`).join(', ')}
                  </td>
                </tr>
                <tr>
                  <td className="ds-cov-sp">Structural binding</td>
                  <td>{compLayers.structural?.stats && Object.keys(compLayers.structural.stats).length > 0
                    ? <span className="ds-cov-yes">
                        {Object.values(compLayers.structural.stats).reduce((sum, sp) =>
                          sum + Object.values(sp).reduce((s, c) => s + c.count, 0), 0).toLocaleString()} predictions
                      </span>
                    : <span className="ds-cov-no">not run</span>}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-2)' }}>
                    Boltz-2 TF-DNA complex (uncalibrated — no validated signal)
                  </td>
                </tr>
                <tr>
                  <td className="ds-cov-sp">Signed edges</td>
                  <td>{compLayers.signTransfer?.ortholog_transferred
                    ? <span className="ds-cov-yes">
                        {compLayers.signTransfer.ortholog_transferred.toLocaleString()} via ortholog transfer
                      </span>
                    : <span className="ds-cov-no">none transferred</span>}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-2)' }}>
                    {compLayers.signTransfer?.distribution?.map(d =>
                      `${d.evidence}: ${d.count}`).join(', ')}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        <ul className="ds-list">
          {(prov?.sources || []).map((s) => (
            <li key={s.key} className="ds-item">
              <a className="ds-name" href={s.url} target="_blank" rel="noopener noreferrer">
                {s.name}{s.version ? ` (${s.version})` : ''}
              </a>
              {freshBy[s.key]?.status === 'stale' && (
                <span className="ds-badge stale"
                      title={`A newer release is available: ${freshBy[s.key].latest_version}`}>
                  update available → {freshBy[s.key].latest_version}
                </span>
              )}
              {freshBy[s.key]?.status === 'current' && (
                <span className="ds-badge current" title="Loaded data matches the latest release">current</span>
              )}
              <div className="ds-provides">{s.provides}</div>
              <div className="ds-cite">
                {s.authors} ({s.year}) {s.journal}{s.volume ? ` ${s.volume}` : ''}{s.pages ? `:${s.pages}` : ''}.
                {s.doi ? ` doi:${s.doi}` : ''}
              </div>
            </li>
          ))}
        </ul>

        {prov?.methods && (
          <>
            <h3 className="ds-subhead">Methods</h3>
            <dl className="ds-glossary">
              {Object.entries(prov.methods).map(([k, v]) => (
                <div key={k} className="ds-term">
                  <dt>{k.replace(/_/g, ' ')}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </>
        )}

        <h3 className="ds-subhead">Glossary</h3>
        <dl className="ds-glossary">
          {GLOSSARY.map(([term, def]) => (
            <div key={term} className="ds-term">
              <dt>{term}</dt>
              <dd>{def}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
