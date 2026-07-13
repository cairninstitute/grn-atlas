import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';
import { geneLabel } from '../utils/geneLabel';
import SubgraphGraph from './SubgraphGraph';
import '../styles/OrganismView.css';

const LABEL = {
  human: 'Human', mouse: 'Mouse', arabidopsis: 'Arabidopsis',
  tomato: 'Tomato', petunia: 'Petunia',
};
const label = (s) => LABEL[s] || (s ? s[0].toUpperCase() + s.slice(1) : s);
const fmt = (n) => (n ?? 0).toLocaleString();

export default function OrganismView({ onSelectGene }) {
  const [speciesList, setSpeciesList] = useState([]);
  const [species, setSpecies] = useState('arabidopsis');
  const [includeInferred, setIncludeInferred] = useState(true);
  const [topN, setTopN] = useState(25);
  const [minConfidence, setMinConfidence] = useState(0);
  const [overview, setOverview] = useState(null);
  const [circuit, setCircuit] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/v1/stats').then((r) => r.json()).then((s) => {
      const list = s.species_list || [];
      setSpeciesList(list);
      if (list.length && !list.includes(species)) setSpecies(list[0]);
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!species) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCircuit(null);
    fetch(`/api/v1/organism/${species}/overview?top=${topN}&min_confidence=${minConfidence}&include_inferred=${includeInferred}`)
      .then((r) => r.json())
      .then(async (ov) => {
        if (cancelled) return;
        setOverview(ov);
        const ids = (ov.top_regulators || []).map((r) => r.id);
        if (ids.length >= 2) {
          const sg = await analysisAPI.subgraph(ids, { includeInferred, minConfidence });
          if (!cancelled) setCircuit(sg);
        }
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [species, includeInferred, topN, minConfidence]);

  const tiles = overview ? [
    { label: 'Genes', value: fmt(overview.genes) },
    { label: 'Transcription factors', value: fmt(overview.transcription_factors) },
    { label: 'Measured edges', value: fmt(overview.edges?.measured) },
    { label: 'Inferred edges', value: fmt(overview.edges?.inferred), inferred: true },
    { label: 'Distinct regulators', value: fmt(overview.regulators) },
    { label: 'Genes with coordinates', value: fmt(overview.genes_with_coordinates) },
  ] : [];

  return (
    <div className="organism-view">
      <div className="org-controls">
        <div className="org-picker">
          <label>Organism</label>
          <select value={species} onChange={(e) => setSpecies(e.target.value)}>
            {speciesList.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
        </div>
        <div className="org-picker">
          <label>Top regulators: {topN}</label>
          <input type="range" min={5} max={100} step={5}
            value={topN} onChange={(e) => setTopN(Number(e.target.value))} />
        </div>
        <div className="org-picker">
          <label>Min confidence: {minConfidence.toFixed(2)}</label>
          <input type="range" min={0} max={0.95} step={0.05}
            value={minConfidence} onChange={(e) => setMinConfidence(Number(e.target.value))} />
        </div>
        <label className="org-toggle" title="Include edges projected from Arabidopsis via orthology (not measured)">
          <input type="checkbox" checked={includeInferred}
            onChange={() => setIncludeInferred((v) => !v)} />
          <span>Include inferred edges</span>
        </label>
      </div>

      {error && <div className="org-message error">Failed to load: {error}</div>}
      {loading && <div className="org-message">Loading organism overview…</div>}

      {overview && !loading && (
        <>
          <div className="org-tiles">
            {tiles.map((t) => (
              <div key={t.label} className={`org-tile ${t.inferred ? 'inferred' : ''}`}>
                <div className="org-tile-value">{t.value}</div>
                <div className="org-tile-label">{t.label}</div>
              </div>
            ))}
          </div>

          <div className="org-body">
            <div className="org-hubs">
              <h3>Top regulators (by out-degree)</h3>
              <p className="org-sub">
                Click to open the gene's full network. Showing{' '}
                {includeInferred ? 'all' : 'measured-only'} edges.
              </p>
              <ol className="org-hub-list">
                {(overview.top_regulators || []).map((r) => {
                  const gl = geneLabel(r);
                  return (
                    <li key={r.id}>
                      <button className="org-hub-btn" onClick={() => onSelectGene?.(r.symbol)}
                        title={gl.inferred ? `${gl.id} — name inferred from Arabidopsis ortholog` : gl.id}>
                        <span className="org-hub-symbol">
                          {gl.label}{gl.inferred && <span className="org-inferred-mark">≈</span>}
                          {r.is_tf && <span className="org-tf">TF</span>}
                        </span>
                        <span className="org-hub-deg">{fmt(r.out_degree)} targets</span>
                      </button>
                    </li>
                  );
                })}
                {(!overview.top_regulators || overview.top_regulators.length === 0) && (
                  <li className="org-empty">No edges for this evidence setting.</li>
                )}
              </ol>
            </div>

            <div className="org-circuit">
              <h3>Core regulatory circuit</h3>
              <p className="org-sub">
                Interactions among the top {overview.top_regulators?.length || 0} regulators —
                the network is too large to draw whole ({fmt(overview.edges?.total)} edges).
              </p>
              {circuit && circuit.edges.length > 0 ? (
                <SubgraphGraph
                  nodes={circuit.nodes}
                  edges={circuit.edges}
                  onNodeClick={(d) => onSelectGene?.(d.symbol || d.label)}
                />
              ) : (
                <div className="org-message">
                  {circuit ? 'No interactions among the top regulators at this setting.' : 'Building circuit…'}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
