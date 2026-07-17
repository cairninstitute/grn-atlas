import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { genomeAPI } from '../services/apiService';
import '../styles/GenomeComparisonView.css';

const SPECIES_LABELS = {
  human: 'Human',
  arabidopsis: 'Arabidopsis',
  rice: 'Rice',
};

const label = (s) => SPECIES_LABELS[s] || (s ? s[0].toUpperCase() + s.slice(1) : s);

// Ribbon color by orthology relationship type.
const relColor = (rel) => {
  if (rel === '1:1') return 'var(--success)';
  if (rel && rel.startsWith('1:')) return 'var(--primary)';
  return 'var(--accent)';
};

// Drawing geometry (SVG user units; scaled responsively via viewBox).
const DRAW_H = 680;
const BAR_W = 26;
const COL_GAP_Y = 10;      // vertical gap between chromosomes in a column
const PAD_TOP = 24;
const PAD_BOTTOM = 16;
const X_LEFT = 150;
const X_RIGHT = 610;
const VIEW_W = 760;

// Build stacked chromosome layout for one genome side.
function layoutGenome(chromosomes) {
  const chroms = chromosomes.filter((c) => c.length > 0);
  const n = chroms.length;
  const avail = DRAW_H - PAD_TOP - PAD_BOTTOM - COL_GAP_Y * Math.max(0, n - 1);
  const totalBp = chroms.reduce((s, c) => s + c.length, 0) || 1;
  const scale = avail / totalBp;
  let y = PAD_TOP;
  const placed = chroms.map((c) => {
    const h = Math.max(3, c.length * scale);
    const entry = { ...c, y, h };
    y += h + COL_GAP_Y;
    return entry;
  });
  const index = {};
  placed.forEach((c) => { index[c.name] = c; });
  return { chroms: placed, index };
}

const geneY = (chrom, start) =>
  chrom.y + Math.min(1, Math.max(0, start / chrom.length)) * chrom.h;

export default function GenomeComparisonView() {
  const [speciesList, setSpeciesList] = useState([]);
  const [speciesA, setSpeciesA] = useState('human');
  const [speciesB, setSpeciesB] = useState('arabidopsis');
  const [genomeA, setGenomeA] = useState(null);
  const [genomeB, setGenomeB] = useState(null);
  const [orthologs, setOrthologs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hovered, setHovered] = useState(null); // { symbol, x, y, text }
  const [selectedSymbol, setSelectedSymbol] = useState(null);

  // Load available species once.
  useEffect(() => {
    genomeAPI.getSpecies()
      .then((data) => {
        const list = (data.species || []).map((s) => s.species);
        setSpeciesList(list);
        if (list.length && !list.includes(speciesA)) setSpeciesA(list[0]);
        if (list.length > 1 && !list.includes(speciesB)) setSpeciesB(list[1]);
      })
      .catch((e) => setError(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load genomes + orthologs when the pair changes.
  useEffect(() => {
    if (!speciesA || !speciesB || speciesA === speciesB) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSelectedSymbol(null);
    Promise.all([
      genomeAPI.getGenome(speciesA),
      genomeAPI.getGenome(speciesB),
      genomeAPI.getOrthologs(speciesA, speciesB),
    ])
      .then(([ga, gb, orth]) => {
        if (cancelled) return;
        setGenomeA(ga);
        setGenomeB(gb);
        setOrthologs(orth.pairs || []);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [speciesA, speciesB]);

  const layoutA = useMemo(
    () => (genomeA ? layoutGenome(genomeA.chromosomes) : null), [genomeA]);
  const layoutB = useMemo(
    () => (genomeB ? layoutGenome(genomeB.chromosomes) : null), [genomeB]);

  // Precompute ribbon endpoints for orthologs whose genes are placed.
  const ribbons = useMemo(() => {
    if (!layoutA || !layoutB) return [];
    return orthologs.map((p, i) => {
      const ca = layoutA.index[p.a.chromosome];
      const cb = layoutB.index[p.b.chromosome];
      if (!ca || !cb) return null;
      return {
        i,
        symbol: p.symbol,
        rel: p.rel_type,
        isTf: p.a.is_tf || p.b.is_tf,
        y1: geneY(ca, p.a.start),
        y2: geneY(cb, p.b.start),
        a: p.a,
        b: p.b,
      };
    }).filter(Boolean);
  }, [orthologs, layoutA, layoutB]);

  const showTip = useCallback((evt, text, symbol) => {
    const rect = evt.currentTarget.ownerSVGElement.getBoundingClientRect();
    // Position tooltip relative to the container using client coords.
    setHovered({ text, symbol, clientX: evt.clientX, clientY: evt.clientY, rect });
  }, []);

  const clearTip = useCallback(() => setHovered(null), []);

  const swap = () => { setSpeciesA(speciesB); setSpeciesB(speciesA); };

  const geneTicks = (layout, x, side) => {
    if (!layout) return null;
    const anchor = side === 'left' ? 'end' : 'start';
    const tickX1 = side === 'left' ? x - 6 : x + BAR_W;
    const tickX2 = side === 'left' ? x : x + BAR_W + 6;
    return layout.chroms.map((c) => (
      <g key={c.name}>
        <rect
          className="chrom-bar" x={x} y={c.y} width={BAR_W} height={c.h} rx={BAR_W / 2}
        />
        <text
          className="chrom-label" x={side === 'left' ? x - 12 : x + BAR_W + 12}
          y={c.y + c.h / 2} textAnchor={anchor} dominantBaseline="middle"
        >{c.name}</text>
        {c.genes && c.genes.map((g) => {
          const y = geneY(c, g.start);
          const active = selectedSymbol && g.symbol === selectedSymbol;
          return (
            <line
              key={g.id}
              className={`gene-tick ${g.is_tf ? 'tf' : ''} ${active ? 'active' : ''}`}
              x1={tickX1} x2={tickX2} y1={y} y2={y}
              onMouseEnter={(e) => showTip(e,
                `${g.symbol} — chr ${c.name}:${g.start.toLocaleString()}${g.is_tf ? ' (TF)' : ''}`,
                g.symbol)}
              onMouseLeave={clearTip}
              onClick={() => setSelectedSymbol(active ? null : g.symbol)}
            />
          );
        })}
      </g>
    ));
  };

  const canRender = layoutA && layoutB && genomeA.chromosomes.length && genomeB.chromosomes.length;
  const sameSpecies = speciesA === speciesB;

  return (
    <div className="genome-view">
      <div className="genome-controls">
        <div className="species-picker">
          <label>Left genome</label>
          <select value={speciesA} onChange={(e) => setSpeciesA(e.target.value)}>
            {speciesList.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
        </div>
        <button className="swap-btn" onClick={swap} title="Swap genomes">⇄</button>
        <div className="species-picker">
          <label>Right genome</label>
          <select value={speciesB} onChange={(e) => setSpeciesB(e.target.value)}>
            {speciesList.map((s) => <option key={s} value={s}>{label(s)}</option>)}
          </select>
        </div>

        <div className="genome-legend">
          <span className="lg-item"><span className="sw sw-gene" /> Gene</span>
          <span className="lg-item"><span className="sw sw-tf" /> TF</span>
          <span className="lg-item"><span className="sw sw-1to1" /> 1:1 ortholog</span>
          <span className="lg-item"><span className="sw sw-multi" /> 1:n / n:m</span>
        </div>
      </div>

      {sameSpecies && (
        <div className="genome-message">Choose two different genomes to compare.</div>
      )}
      {error && <div className="genome-message error">Failed to load genome data: {error}</div>}
      {loading && <div className="genome-message">Loading genome data…</div>}

      {!sameSpecies && !loading && !error && canRender && (
        <>
          <div className="genome-summary">
            <strong>{label(speciesA)}</strong> ({genomeA.chromosomes.length} chromosomes) vs{' '}
            <strong>{label(speciesB)}</strong> ({genomeB.chromosomes.length} chromosomes) ·{' '}
            {ribbons.length.toLocaleString()} ortholog link{ribbons.length === 1 ? '' : 's'}
            {selectedSymbol && (
              <button className="clear-sel" onClick={() => setSelectedSymbol(null)}>
                clear “{selectedSymbol}”
              </button>
            )}
          </div>

          <div className="genome-canvas">
            <svg viewBox={`0 0 ${VIEW_W} ${DRAW_H}`} preserveAspectRatio="xMidYMid meet"
                 className="genome-svg" role="img"
                 aria-label={`Chromosome comparison between ${label(speciesA)} and ${label(speciesB)}`}>
              <text className="col-title" x={X_LEFT + BAR_W / 2} y={12} textAnchor="middle">
                {label(speciesA)}
              </text>
              <text className="col-title" x={X_RIGHT + BAR_W / 2} y={12} textAnchor="middle">
                {label(speciesB)}
              </text>

              {/* Ortholog ribbons (drawn under the chromosome bars). */}
              <g className="ribbons">
                {ribbons.map((r) => {
                  const x1 = X_LEFT + BAR_W;
                  const x2 = X_RIGHT;
                  const mx = (x1 + x2) / 2;
                  const dim = selectedSymbol && r.symbol !== selectedSymbol;
                  const active = selectedSymbol && r.symbol === selectedSymbol;
                  return (
                    <path
                      key={r.i}
                      className={`ribbon ${dim ? 'dim' : ''} ${active ? 'active' : ''}`}
                      d={`M ${x1} ${r.y1} C ${mx} ${r.y1}, ${mx} ${r.y2}, ${x2} ${r.y2}`}
                      stroke={relColor(r.rel)}
                      onMouseEnter={(e) => showTip(e,
                        `${r.symbol}: ${label(speciesA)} chr ${r.a.chromosome} ↔ ${label(speciesB)} chr ${r.b.chromosome} (${r.rel || 'ortholog'})`,
                        r.symbol)}
                      onMouseLeave={clearTip}
                      onClick={() => setSelectedSymbol(active ? null : r.symbol)}
                    />
                  );
                })}
              </g>

              {geneTicks(layoutA, X_LEFT, 'left')}
              {geneTicks(layoutB, X_RIGHT, 'right')}
            </svg>

            {hovered && (
              <div
                className="genome-tooltip"
                style={{
                  left: hovered.clientX - hovered.rect.left + 12,
                  top: hovered.clientY - hovered.rect.top + 12,
                }}
              >{hovered.text}</div>
            )}
          </div>
        </>
      )}

      {!sameSpecies && !loading && !error && !canRender && genomeA && genomeB && (
        <div className="genome-message">
          No positioned genes available for this pair yet.
        </div>
      )}
    </div>
  );
}
