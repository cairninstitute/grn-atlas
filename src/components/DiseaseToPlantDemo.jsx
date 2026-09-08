import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import '../styles/DiseaseToPlantDemo.css';

const API = '/api/v1';

const STEPS = [
  { id: 'pick',     label: '1. Choose a gene' },
  { id: 'network',  label: '2. See the circuit' },
  { id: 'cross',    label: '3. Find it in crops' },
  { id: 'target',   label: '4. Pick a target' },
  { id: 'dsrna',    label: '5. Design dsRNA' },
];

const SUGGESTED_GENES = [
  {
    symbol: 'WRKY33', id: 'AT2G38470',
    trait: 'Pathogen defense',
    desc: 'When a plant is attacked by a fungus, WRKY33 switches on the genes that produce camalexin — a natural antibiotic. Silencing the crop version could test whether that defense pathway works the same way in tomato or rice.',
  },
  {
    symbol: 'DREB2A', id: 'AT5G05410',
    trait: 'Drought tolerance',
    desc: 'DREB2A is a master switch for drought response. It turns on dozens of genes that help cells survive water stress. If you could boost or silence its crop ortholog, you might alter how a plant handles drought.',
  },
  {
    symbol: 'GL3', id: 'AT5G41315',
    trait: 'Flower color & trichomes',
    desc: 'GL3 is the bHLH partner in the MBW complex that controls anthocyanin (pigment) production and trichome (hair) formation. The same complex controls flower color in petunia.',
  },
];

function StepBar({ current }) {
  const idx = STEPS.findIndex((s) => s.id === current);
  return (
    <div className="demo-step-bar">
      {STEPS.map((s, i) => (
        <div key={s.id} className={`demo-step ${i < idx ? 'done' : ''} ${i === idx ? 'active' : ''}`}>
          <span className="demo-step-num">{i < idx ? '✓' : i + 1}</span>
          <span className="demo-step-label">{s.label}</span>
        </div>
      ))}
    </div>
  );
}

function EdgeChip({ edge, onClick }) {
  return (
    <button
      className={`demo-edge-chip ${edge.inferred ? 'inferred' : 'curated'}`}
      onClick={() => onClick?.(edge)}
      title={`${edge.partner_symbol} — ${(edge.sources || []).join(', ')}${edge.inferred ? ' (predicted from ortholog, not directly measured)' : ' (experimentally measured)'}`}
    >
      <span className="demo-edge-arrow">{edge.direction === 'regulator' ? '←' : '→'}</span>
      {edge.partner_symbol}
      {edge.inferred && <span className="demo-edge-badge">predicted</span>}
    </button>
  );
}

function MiniGraph({ gene, neighborhoodData }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    if (!containerRef.current || !neighborhoodData) return;

    const elements = [];
    const selectedLabel = gene.label || gene.symbol;

    elements.push({
      data: {
        id: gene.id,
        label: selectedLabel,
        fullName: gene.name || '',
        nodeType: 'selected',
        is_tf: gene.is_tf,
      },
    });

    const regs = neighborhoodData.regulators || [];
    const tgts = neighborhoodData.targets || [];

    regs.forEach((r) => {
      elements.push({
        data: {
          id: r.id,
          label: r.symbol,
          fullName: r.name || '',
          nodeType: 'regulator',
          is_tf: r.is_tf,
        },
      });
      elements.push({
        data: {
          id: `${r.id}->${gene.id}`,
          source: r.id,
          target: gene.id,
          regulation_type: r.regulation_type || 'regulation',
          confidence: r.confidence || 0.5,
        },
      });
    });

    tgts.forEach((t) => {
      elements.push({
        data: {
          id: t.id,
          label: t.symbol,
          fullName: t.name || '',
          nodeType: 'target',
          is_tf: t.is_tf,
        },
      });
      elements.push({
        data: {
          id: `${gene.id}->${t.id}`,
          source: gene.id,
          target: t.id,
          regulation_type: t.regulation_type || 'regulation',
          confidence: t.confidence || 0.5,
        },
      });
    });

    const graphWidth = containerRef.current.clientWidth || 760;
    const positions = {};
    const centerX = graphWidth / 2;
    const topY = 60;
    const midY = 180;
    const botY = 300;

    positions[gene.id] = { x: centerX, y: midY };

    regs.forEach((r, i) => {
      const spread = Math.min(80, (graphWidth - 80) / Math.max(regs.length, 1));
      const startX = centerX - ((regs.length - 1) * spread) / 2;
      positions[r.id] = { x: startX + i * spread, y: topY };
    });

    tgts.forEach((t, i) => {
      const spread = Math.min(80, (graphWidth - 80) / Math.max(tgts.length, 1));
      const startX = centerX - ((tgts.length - 1) * spread) / 2;
      positions[t.id] = { x: startX + i * spread, y: botY };
    });

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            content: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'font-size': '10px',
            'font-weight': '500',
            color: '#ccc',
            'text-max-width': '80px',
            'text-wrap': 'wrap',
            width: '38px',
            height: '38px',
            'border-width': '2px',
          },
        },
        {
          selector: 'node[nodeType="selected"]',
          style: {
            'background-color': '#3B8BD4',
            'border-color': '#185FA5',
            color: 'white',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-margin-y': 0,
            width: '56px',
            height: '56px',
            'font-size': '13px',
            'font-weight': '700',
            'z-index': 10,
          },
        },
        {
          selector: 'node[nodeType="regulator"]',
          style: {
            'background-color': '#7F77DD',
            'border-color': '#534AB7',
            color: '#ccc',
            shape: 'diamond',
          },
        },
        {
          selector: 'node[nodeType="target"]',
          style: {
            'background-color': '#888780',
            'border-color': '#5F5E5A',
            color: '#ccc',
            shape: 'ellipse',
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            width: 2,
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.2,
            opacity: 0.7,
            'line-color': '#7E57C2',
            'target-arrow-color': '#7E57C2',
          },
        },
        {
          selector: 'edge[regulation_type="activation"]',
          style: { 'line-color': '#4CAF50', 'target-arrow-color': '#4CAF50' },
        },
        {
          selector: 'edge[regulation_type="repression"]',
          style: {
            'line-color': '#F44336',
            'target-arrow-color': '#F44336',
            'target-arrow-shape': 'tee',
          },
        },
        {
          selector: 'edge[confidence >= 0.75]',
          style: { 'line-style': 'solid' },
        },
        {
          selector: 'edge[confidence >= 0.6][confidence < 0.75]',
          style: { 'line-style': 'dashed' },
        },
        {
          selector: 'edge[confidence < 0.6]',
          style: { 'line-style': 'dotted' },
        },
      ],
      layout: {
        name: 'preset',
        positions: (node) => positions[node.id()] || { x: centerX, y: midY },
      },
      wheelSensitivity: 0.15,
      autoungrabify: false,
      boxSelectionEnabled: false,
    });

    cyRef.current = cy;

    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      const fullName = node.data('fullName');
      if (!fullName) return;
      const pos = evt.renderedPosition;
      setTooltip({
        x: pos.x,
        y: pos.y,
        label: node.data('label'),
        name: fullName,
        type: node.data('nodeType'),
      });
    });

    cy.on('mouseout', 'node', () => setTooltip(null));
    cy.on('pan zoom', () => setTooltip(null));

    cy.fit(cy.elements(), 30);

    return () => { cy.destroy(); };
  }, [gene, neighborhoodData]);

  return (
    <div className="demo-mini-graph-wrap">
      <div className="demo-mini-graph" ref={containerRef} />
      {tooltip && (
        <div
          className="demo-node-tooltip"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          <strong>{tooltip.label}</strong>
          <span>{tooltip.name}</span>
        </div>
      )}
      <div className="demo-graph-legend">
        <span><span className="demo-legend-dot regulator" /> Upstream regulator (top)</span>
        <span><span className="demo-legend-dot selected" /> Focus gene (center)</span>
        <span><span className="demo-legend-dot target" /> Downstream target (bottom)</span>
      </div>
    </div>
  );
}

function EvidenceBar({ measured, inferred, max }) {
  const total = measured + inferred;
  if (!max || !total) return null;
  const mPct = (measured / max) * 100;
  const iPct = (inferred / max) * 100;
  return (
    <div className="demo-evidence-bar" title={`${measured} measured + ${inferred} inferred = ${total} total`}>
      <div className="demo-evidence-measured" style={{ width: `${mPct}%` }} />
      <div className="demo-evidence-inferred" style={{ width: `${iPct}%` }} />
    </div>
  );
}

export default function DiseaseToPlantDemo({ onOpenDsRna, onGeneSelect }) {
  const [step, setStep] = useState('pick');
  const [gene, setGene] = useState(null);
  const [homeNetwork, setHomeNetwork] = useState(null);
  const [neighborhoodData, setNeighborhoodData] = useState(null);
  const [crossData, setCrossData] = useState(null);
  const [orthoEvidence, setOrthoEvidence] = useState(null);
  const [selectedPlantGene, setSelectedPlantGene] = useState(null);
  const [dsrnaResult, setDsrnaResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const pickGene = useCallback(async (g) => {
    setGene(g);
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/genes/${g.id}`);
      if (!res.ok) throw new Error('Gene not found');
      const data = await res.json();
      setGene({ ...data, trait: g.trait });
      setStep('network');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (step !== 'network' || !gene) return;
    let cancelled = false;
    setLoading(true);

    const crossviewPromise = fetch(
      `${API}/crossview/${gene.id}?max_edges=15&min_confidence=0.3`
    ).then((r) => r.json());

    const neighborhoodPromise = fetch(
      `${API}/pathways/neighborhood/${gene.id}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_depth: 1,
          direction: 'both',
          min_confidence: 0.3,
          max_regulators: 8,
          max_targets: 8,
        }),
      }
    ).then((r) => r.json());

    Promise.all([crossviewPromise, neighborhoodPromise])
      .then(([crossview, neighborhood]) => {
        if (cancelled) return;
        setHomeNetwork(crossview.species?.arabidopsis || null);
        setCrossData(crossview);
        setNeighborhoodData(neighborhood);
        setLoading(false);
      })
      .catch((err) => {
        if (!cancelled) { setError(err.message); setLoading(false); }
      });

    return () => { cancelled = true; };
  }, [step, gene]);

  useEffect(() => {
    if (step !== 'cross' || !gene) return;
    let cancelled = false;
    fetch(`${API}/orthologs/${gene.id}/evidence`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setOrthoEvidence(d.orthologs || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [step, gene]);

  const pickPlantTarget = useCallback((ortho) => {
    setSelectedPlantGene({ id: ortho.gene_id, symbol: ortho.symbol, species: ortho.species, evidence: ortho });
    setStep('target');
  }, []);

  const designDsRna = useCallback(async () => {
    if (!selectedPlantGene) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/dsrna`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_gene_id: selectedPlantGene.id,
          species: selectedPlantGene.species,
          k: 21,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `dsRNA design failed (${res.status})`);
      }
      const data = await res.json();
      setDsrnaResult(data);
      setStep('dsrna');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedPlantGene]);

  const reset = useCallback(() => {
    setStep('pick');
    setGene(null);
    setHomeNetwork(null);
    setNeighborhoodData(null);
    setCrossData(null);
    setOrthoEvidence(null);
    setSelectedPlantGene(null);
    setDsrnaResult(null);
    setError(null);
  }, []);

  const cropSpecies = useMemo(() => {
    if (!crossData?.species) return [];
    return Object.entries(crossData.species)
      .filter(([sp, d]) => sp !== 'arabidopsis' && d.edges?.length > 0)
      .sort((a, b) => b[1].edges.length - a[1].edges.length);
  }, [crossData]);

  const regulators = homeNetwork?.edges?.filter((e) => e.direction === 'regulator') || [];
  const targets = homeNetwork?.edges?.filter((e) => e.direction === 'target') || [];
  const sym = gene?.label || gene?.symbol || '';

  return (
    <div className="demo-container">
      <StepBar current={step} />

      {error && <div className="demo-error">{error}</div>}
      {loading && <div className="demo-loading">Loading…</div>}

      {/* ── STEP 1: Pick a gene ── */}
      {step === 'pick' && (
        <div className="demo-panel">
          <h2>What gene controls the trait you care about?</h2>
          <p className="demo-desc">
            Arabidopsis is the best-studied plant genome — thousands of its regulatory
            relationships have been experimentally validated. Because those genes have
            orthologs (evolutionary cousins) in crop species, knowledge from Arabidopsis
            can be transferred to tomato, rice, petunia, and more.
          </p>
          <p className="demo-desc">
            Pick a gene below. In five steps, Darwin will show you its regulatory circuit,
            find the equivalent genes in crops, and design an RNA molecule that could
            silence the crop version in a lab experiment.
          </p>
          <div className="demo-suggestions">
            {SUGGESTED_GENES.map((g) => (
              <button key={g.id} className="demo-gene-card" onClick={() => pickGene(g)}>
                <strong>{g.symbol}</strong>
                <span className="demo-gene-trait">{g.trait}</span>
                <span className="demo-gene-desc">{g.desc}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── STEP 2: Arabidopsis regulatory circuit ── */}
      {step === 'network' && !loading && homeNetwork && (
        <div className="demo-panel">
          <h2>
            The regulatory circuit around <span className="demo-gene-label">{sym}</span>
          </h2>
          <p className="demo-desc">
            Darwin found <strong>{homeNetwork.edges?.length || 0}</strong> genes connected
            to {sym} in Arabidopsis. Diamond nodes at the top are upstream transcription
            factors that switch {sym} on or off. Round nodes at the bottom are downstream
            genes that {sym} controls. Hover over any node to see what it does.
          </p>

          {neighborhoodData && (
            <MiniGraph gene={gene} neighborhoodData={neighborhoodData} />
          )}

          <p className="demo-desc demo-desc-aside">
            This circuit is well-characterized because Arabidopsis has extensive
            ChIP-seq, DAP-seq, and genetic data. The question is: does the same
            circuit exist in a crop you actually grow?
          </p>
          <div className="demo-actions">
            <button className="demo-btn" onClick={() => setStep('pick')}>&larr; Back</button>
            <button className="demo-btn primary" onClick={() => setStep('cross')}>
              Find this circuit in crops &rarr;
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Crop orthologs ── */}
      {step === 'cross' && !loading && (
        <div className="demo-panel">
          <h2>Which crop ortholog should you target?</h2>
          <p className="demo-desc">
            Darwin found the evolutionary cousins (orthologs) of {sym} in each crop
            species and compared their evidence quality. Not all orthologs are equal —
            some have hundreds of experimentally validated regulatory edges, while
            others rely entirely on predictions.
          </p>
          <p className="demo-desc">
            <strong>Pick the ortholog with the strongest evidence</strong> — more
            <span className="demo-legend-curated"> measured edges</span> and more
            conserved targets mean higher confidence that the regulatory circuit
            actually works the same way in that species.
          </p>
          {(() => {
            const orthos = orthoEvidence || [];
            if (orthos.length === 0 && cropSpecies.length === 0) {
              return <p className="demo-empty">No crop orthologs found. This gene may be Arabidopsis-specific.</p>;
            }
            const maxEdges = Math.max(1, ...orthos.map((o) => o.total_edges));
            const bySpecies = {};
            for (const o of orthos) {
              (bySpecies[o.species] ||= []).push(o);
            }
            const speciesOrder = Object.keys(bySpecies).sort(
              (a, b) => Math.max(...bySpecies[b].map((o) => o.measured_edges)) -
                        Math.max(...bySpecies[a].map((o) => o.measured_edges))
            );
            return speciesOrder.map((sp) => (
              <div key={sp} className="demo-species-block">
                <h3>{sp.charAt(0).toUpperCase() + sp.slice(1)}</h3>
                <div className="demo-ortho-cards">
                  {bySpecies[sp].map((o) => {
                    const best = bySpecies[sp].reduce((a, b) => a.measured_edges > b.measured_edges ? a : b);
                    const isBest = o.gene_id === best.gene_id && o.measured_edges > 0;
                    return (
                      <button
                        key={o.gene_id}
                        className={`demo-ortho-card ${isBest ? 'best' : ''}`}
                        onClick={() => pickPlantTarget(o)}
                        title={`Click to select ${o.symbol} as target`}
                      >
                        {isBest && <span className="demo-ortho-best-badge">Strongest evidence</span>}
                        <div className="demo-ortho-header">
                          <strong className="demo-ortho-symbol">{o.symbol}</strong>
                          {o.tf_family && <span className="demo-ortho-family">{o.tf_family}</span>}
                          <span className="demo-ortho-rel">{o.rel_type}</span>
                        </div>
                        <div className="demo-ortho-stats">
                          <div className="demo-ortho-stat">
                            <span className="demo-ortho-stat-val measured">{o.measured_edges.toLocaleString()}</span>
                            <span className="demo-ortho-stat-label">measured</span>
                          </div>
                          <div className="demo-ortho-stat">
                            <span className="demo-ortho-stat-val inferred">{o.inferred_edges.toLocaleString()}</span>
                            <span className="demo-ortho-stat-label">predicted</span>
                          </div>
                          <div className="demo-ortho-stat">
                            <span className="demo-ortho-stat-val conserved">{o.conserved_targets.toLocaleString()}</span>
                            <span className="demo-ortho-stat-label">conserved targets</span>
                          </div>
                        </div>
                        <EvidenceBar measured={o.measured_edges} inferred={o.inferred_edges} max={maxEdges} />
                        {o.sources.length > 0 && (
                          <div className="demo-ortho-sources">
                            {o.sources.filter((s) => !s.startsWith('Inferred')).map((s) => (
                              <span key={s} className="demo-ortho-source">{s}</span>
                            ))}
                            {o.sources.some((s) => s.startsWith('Inferred')) && (
                              <span className="demo-ortho-source inferred">+ ortholog inference</span>
                            )}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ));
          })()}

          {/* Fallback: show species from crossview that have no orthologs in evidence */}
          {orthoEvidence && cropSpecies
            .filter(([sp]) => !(orthoEvidence || []).some((o) => o.species === sp))
            .map(([sp, spData]) => (
              <div key={sp} className="demo-species-block">
                <h3>
                  {sp.charAt(0).toUpperCase() + sp.slice(1)}
                  <span className="demo-species-counts">
                    <span className="demo-count-inferred">{spData.edges.length} connections (no direct ortholog)</span>
                  </span>
                </h3>
              </div>
            ))
          }

          <div className="demo-actions">
            <button className="demo-btn" onClick={() => setStep('network')}>&larr; Back</button>
          </div>
        </div>
      )}

      {/* ── STEP 4: Confirm target ── */}
      {step === 'target' && selectedPlantGene && (
        <div className="demo-panel">
          <h2>Ready to design a silencing molecule</h2>
          <p className="demo-desc">
            You picked <strong>{selectedPlantGene.symbol}</strong> in{' '}
            {selectedPlantGene.species} — the crop equivalent of Arabidopsis{' '}
            {sym}. In the next step, Darwin will scan the {selectedPlantGene.species}{' '}
            transcriptome and design a short double-stranded RNA (dsRNA) molecule
            that is complementary to this gene's mRNA. When applied to the plant
            (e.g. by spraying), the dsRNA triggers RNA interference (RNAi), which
            degrades the target mRNA and effectively silences the gene.
          </p>
          <div className="demo-target-card">
            <div><strong>Crop gene:</strong> {selectedPlantGene.symbol}</div>
            <div><strong>Species:</strong> {selectedPlantGene.species}</div>
            <div><strong>Gene ID:</strong> <code>{selectedPlantGene.id}</code></div>
            <div><strong>Arabidopsis counterpart:</strong> {sym}</div>
            {selectedPlantGene.evidence && (
              <>
                <div className="demo-target-evidence">
                  <div><strong>Evidence quality:</strong></div>
                  <div className="demo-target-ev-row">
                    <span className="demo-count-curated">{selectedPlantGene.evidence.measured_edges.toLocaleString()} measured edges</span>
                    {' · '}
                    <span className="demo-count-inferred">{selectedPlantGene.evidence.inferred_edges.toLocaleString()} predicted edges</span>
                    {' · '}
                    <span>{selectedPlantGene.evidence.conserved_targets.toLocaleString()} conserved targets</span>
                  </div>
                </div>
              </>
            )}
          </div>
          <div className="demo-actions">
            <button className="demo-btn" onClick={() => setStep('cross')}>&larr; Pick a different gene</button>
            <button className="demo-btn primary" onClick={designDsRna} disabled={loading}>
              Design dsRNA &rarr;
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 5: dsRNA result ── */}
      {step === 'dsrna' && dsrnaResult && (
        <div className="demo-panel">
          <h2>dsRNA designed for {selectedPlantGene.symbol}</h2>
          <p className="demo-desc">
            Darwin scanned every transcript in the {selectedPlantGene.species} genome
            and found the most specific window — a {dsrnaResult.design?.sequence?.length || '?'}nt
            stretch of {selectedPlantGene.symbol}'s mRNA that has the fewest matches
            to other genes. This is the sequence you would synthesize and apply to
            the plant to silence {selectedPlantGene.symbol} via RNAi.
          </p>

          {dsrnaResult.design?.sequence && (
            <div className="demo-sequence">
              <h4>dsRNA sequence ({dsrnaResult.design.sequence.length}nt) — ready to synthesize</h4>
              <pre>{dsrnaResult.design.sequence}</pre>
            </div>
          )}

          {dsrnaResult.on_target?.length > 0 && (
            <div className="demo-on-target">
              <h4>On-target: this dsRNA will silence</h4>
              {dsrnaResult.on_target.map((t) => (
                <div key={t.gene_id} className="demo-target-hit">
                  <strong>{t.symbol || t.gene_id}</strong>
                  <span>{t.shared_kmers} matching 21-mers</span>
                </div>
              ))}
            </div>
          )}

          {dsrnaResult.off_target?.length > 0 && (
            <div className="demo-off-target">
              <h4>
                Off-target risk: {dsrnaResult.off_target.length} other gene{dsrnaResult.off_target.length > 1 ? 's' : ''} share
                partial sequence matches
              </h4>
              <p className="demo-off-explain">
                These genes have some sequence overlap and might be partially silenced
                as a side effect. Fewer off-targets = more specific dsRNA.
              </p>
              <div className="demo-off-target-list">
                {dsrnaResult.off_target.slice(0, 10).map((t) => (
                  <div key={t.gene_id} className="demo-target-hit off">
                    <span>{t.symbol || t.gene_id}</span>
                    <span>{t.shared_kmers} matching 21-mers</span>
                  </div>
                ))}
                {dsrnaResult.off_target.length > 10 && (
                  <div className="demo-more">+{dsrnaResult.off_target.length - 10} more</div>
                )}
              </div>
            </div>
          )}

          <p className="demo-disclaimer">
            This is a computational prediction, not a validated lab result. Real RNAi
            efficacy depends on how the dsRNA is diced into siRNAs, whether it reaches
            the target tissue, mRNA secondary structure, and amplification by the
            plant's own RNA-dependent RNA polymerase. Use this as a starting point for
            experimental design, not as a guarantee of knockdown.
          </p>
          <div className="demo-actions">
            <button className="demo-btn" onClick={() => setStep('target')}>&larr; Back</button>
            <button className="demo-btn primary" onClick={reset}>Try another gene</button>
            {onOpenDsRna && (
              <button
                className="demo-btn"
                onClick={() => onOpenDsRna({ target: selectedPlantGene })}
              >
                Open full dsRNA designer
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
