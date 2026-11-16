import React, { useEffect, useMemo, useState } from 'react';
import '../../styles/ControlAtlasDemo.css';

const SPECIES = ['arabidopsis', 'human', 'mouse', 'tomato', 'petunia', 'rice', 'pepper', 'potato'];
const LABELS = {
  arabidopsis: 'Arabidopsis', human: 'Human', mouse: 'Mouse', tomato: 'Tomato',
  petunia: 'Petunia', rice: 'Rice', pepper: 'Pepper', potato: 'Potato',
};
const CONTROLLER_PROGRAMS = {
  WRKY6: 'stress and senescence',
  ABI5: 'ABA and stress response',
  TTG2: 'epidermal and seed-coat patterning',
  CPC: 'epidermal cell fate',
  ABI3: 'seed maturation',
  AG: 'floral identity and determinacy',
  AP2: 'floral organ identity',
};
const number = (value) => value == null ? '—' : value.toLocaleString();

function FloralCoreNeighborhood({ system }) {
  const shownGenes = ['LFY', 'AP1', 'AG', 'AP2', 'SEP3', 'ANT', 'AP3', 'PI', 'SUP', 'CRC', 'NAP', 'INO', 'WUS'];
  const geneIds = new Map((system?.genes || []).map((gene) => [gene.id, gene.symbol]));
  const shownEdges = (system?.edges || []).filter((edge) => (
    shownGenes.includes(geneIds.get(edge.source)) && shownGenes.includes(geneIds.get(edge.target))
  ));
  const focusCircuits = (system?.circuits || []).filter((circuit) => (
    (circuit.genes || []).some((gene) => ['AP3', 'PI', 'SUP'].includes(gene.symbol))
  ));

  return (
    <div className="control-neighborhood">
      <div className="control-neighborhood-flow">
        <section className="control-neighborhood-module inputs">
          <span>Upstream floral patterning</span>
          <h4>Establish the program</h4>
          <div className="control-neighborhood-genes">
            {['LFY', 'AP1', 'AG', 'AP2', 'SEP3', 'ANT'].map((gene) => <b key={gene}>{gene}</b>)}
          </div>
          <ul>
            <li><b>LFY</b> activates AP3, PI, and SUP, coupling floral initiation to both identity and its boundary.</li>
            <li><b>AP1/AP2</b> activate AP3 and PI; <b>AG</b> activates AP3 and SUP.</li>
            <li><b>SEP3/ANT</b> add activation into AP3, reinforcing entry into the B-class program.</li>
          </ul>
          <p>These convergent inputs establish AP3/PI and its SUP brake together. The closed loops can then maintain the identity state while restricting where it operates.</p>
        </section>
        <div className="control-neighborhood-link bidirectional"><span>inputs activate<br />AP3 / PI ─| AP1</span></div>
        <section className="control-neighborhood-module controller">
          <span>Mixed-feedback controller</span>
          <h4>Maintain and contain identity</h4>
          <div className="control-neighborhood-controller">
            <b>AP3</b><i>↔</i><b>PI</b>
            <em>activate</em>
            <b className="sup">SUP</b>
            <small>SUP ─| AP3 / PI</small>
          </div>
          <p>Positive feedback stabilizes B-class identity; negative feedback limits its spatial domain.</p>
        </section>
        <div className="control-neighborhood-link split"><span>routes signed outputs</span></div>
        <section className="control-neighborhood-module outputs">
          <span>Connected developmental programs</span>
          <h4>Coordinate the flower</h4>
          <div className="control-output-row activation"><b>CRC</b><b>NAP</b><small>activated by AP3 / PI</small></div>
          <div className="control-output-row repression"><b>INO</b><b>WUS</b><small>repressed by SUP</small></div>
          <ul>
            <li><b>CRC</b> links the controller to carpel and nectary development.</li>
            <li><b>NAP</b> links it to floral-organ maturation and senescence.</li>
            <li><b>INO</b> participates in ovule outer-integument identity.</li>
            <li><b>WUS</b> maintains floral stem-cell activity.</li>
          </ul>
          <p>The outputs therefore coordinate the stamen/carpel boundary with organ differentiation and termination of the floral meristem.</p>
        </section>
      </div>
      <div className="control-neighborhood-facts">
        <div><strong>{number(system?.gene_count)}</strong><span>genes in the annotated floral system</span></div>
        <div><strong>{number(system?.edge_count)}</strong><span>signed edges in that system</span></div>
        <div><strong>{number(shownEdges.length)}</strong><span>signed links among the genes shown</span></div>
        <div><strong>{number(focusCircuits.length)}</strong><span>closed circuits touching AP3, PI, or SUP</span></div>
      </div>
      <p className="control-neighborhood-explanation">
        <strong>What this adds:</strong> AP3–PI–SUP is not an isolated three-gene motif. The local neighborhood shows
        how upstream floral-patterning genes engage it and how its signed outputs connect boundary control to other
        developmental programs. Module arrows summarize the returned gene-level edges; this is a selected, readable
        slice of the 157-gene core, not the entire core.
      </p>
    </div>
  );
}

function FloralBoundaryMechanism({ circuits }) {
  const edges = circuits.flatMap((circuit) => circuit.edges || []);
  const confidence = edges.length ? Math.min(...edges.map((edge) => edge.confidence ?? 0)) : 0.95;

  return (
    <div className="control-floral-mechanism">
      <div className="control-flower-map">
        <p className="control-demo-kicker">Spatial outcome</p>
        <svg viewBox="0 0 360 360" role="img" aria-label="Arabidopsis flower whorls with the SUPERMAN boundary between stamens and carpels">
          <circle cx="180" cy="180" r="145" className="whorl whorl-one" />
          <circle cx="180" cy="180" r="112" className="whorl whorl-two" />
          <circle cx="180" cy="180" r="78" className="whorl whorl-three" />
          <circle cx="180" cy="180" r="40" className="whorl whorl-four" />
          <circle cx="180" cy="180" r="59" className="whorl-boundary" />
          <text x="180" y="28" textAnchor="middle">WHORL 1 · SEPALS</text>
          <text x="180" y="71" textAnchor="middle">WHORL 2 · PETALS</text>
          <text x="180" y="116" textAnchor="middle" className="whorl-three-label">WHORL 3 · STAMENS</text>
          <text x="180" y="175" textAnchor="middle" className="boundary-label">SUP BOUNDARY</text>
          <text x="180" y="190" textAnchor="middle" className="whorl-four-label">WHORL 4</text>
          <text x="180" y="204" textAnchor="middle" className="whorl-four-label">CARPELS</text>
        </svg>
        <p>SUP marks the boundary that prevents the stamen program from expanding into the central carpel-forming domain.</p>
      </div>
      <div className="control-floral-circuit">
        <p className="control-demo-kicker">Signed control circuit</p>
        <svg viewBox="0 0 620 360" role="img" aria-label="AP3 and PI mutually activate, activate SUP, and are repressed by SUP">
          <defs>
            <marker id="floral-activation" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" /></marker>
            <marker id="floral-repression" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M8,0 L8,10" /></marker>
          </defs>
          <path d="M205 94 C255 55 365 55 415 94" className="floral-edge activation" markerEnd="url(#floral-activation)" />
          <path d="M415 126 C365 165 255 165 205 126" className="floral-edge activation" markerEnd="url(#floral-activation)" />
          <path d="M185 150 C205 220 250 246 282 260" className="floral-edge activation" markerEnd="url(#floral-activation)" />
          <path d="M435 150 C415 220 370 246 338 260" className="floral-edge activation" markerEnd="url(#floral-activation)" />
          <path d="M280 274 C220 257 167 215 160 153" className="floral-edge repression" markerEnd="url(#floral-repression)" />
          <path d="M340 274 C400 257 453 215 460 153" className="floral-edge repression" markerEnd="url(#floral-repression)" />
          <g className="floral-node identity" transform="translate(160 115)"><circle r="48" /><text y="8">AP3</text></g>
          <g className="floral-node identity" transform="translate(460 115)"><circle r="48" /><text y="8">PI</text></g>
          <g className="floral-node boundary" transform="translate(310 285)"><circle r="48" /><text y="8">SUP</text></g>
          <text x="310" y="45" textAnchor="middle" className="floral-edge-label">REINFORCE B-CLASS IDENTITY</text>
          <text x="310" y="205" textAnchor="middle" className="floral-edge-label">ACTIVATE BOUNDARY BRAKE</text>
          <text x="310" y="348" textAnchor="middle" className="floral-circuit-caption">SUP RESTRICTS AP3 / PI EXPANSION</text>
        </svg>
        <div className="control-mechanism-score">
          <span>Atlas circuits</span>
          <strong>4 representative loops · high confidence · {Math.round(confidence * 100)}% edge floor</strong>
        </div>
      </div>
    </div>
  );
}

export default function ControlAtlasDemo({ onBack, onOpenControl }) {
  const [stats, setStats] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [feedback, setFeedback] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch('/api/v1/stats', { signal: controller.signal }).then((response) => response.json()),
      fetch('/api/v1/evidence/external/summary', { signal: controller.signal }).then((response) => response.json()),
      ...SPECIES.map((species) => fetch(`/api/v1/network/feedback-control/${species}/latest`, {
        signal: controller.signal,
      }).then((response) => response.ok ? response.json() : null)),
    ]).then(([statsResult, evidenceResult, ...feedbackResults]) => {
      setStats(statsResult);
      setEvidence(evidenceResult);
      setFeedback(Object.fromEntries(SPECIES.map((species, index) => [species, feedbackResults[index]])));
    }).catch((requestError) => {
      if (requestError.name !== 'AbortError') setError(requestError.message);
    });
    return () => controller.abort();
  }, []);

  const evidenceLayers = useMemo(() => {
    const rows = evidence?.evidence || [];
    const count = (layer) => rows.filter((row) => row.evidence_layer === layer)
      .reduce((sum, row) => sum + row.count, 0);
    return {
      directSigned: count('direct_signed'),
      directUnsigned: count('direct_unsigned'),
      perturbation: count('perturbation_signed'),
      transferred: count('orthology_transferred'),
      sources: new Set(rows.map((row) => row.source)).size,
    };
  }, [evidence]);

  const totals = useMemo(() => Object.values(feedback).reduce((acc, result) => {
    const summary = result?.summary || {};
    acc.cores += summary.feedback_cores || 0;
    acc.genes += summary.feedback_genes || 0;
    acc.edges += summary.feedback_edges || 0;
    return acc;
  }, { cores: 0, genes: 0, edges: 0 }), [feedback]);

  const arabidopsis = feedback.arabidopsis;
  const arabidopsisSummary = arabidopsis?.summary || {};
  const centralCore = arabidopsis?.cores?.[0];
  const controllers = centralCore?.controller_analysis?.controllers?.slice(0, 7) || [];
  const floralSystem = arabidopsis?.systems?.find((system) => system.name === 'floral organ morphogenesis');
  const floralCircuits = (floralSystem?.circuits || []).filter((circuit) => {
    const symbols = new Set((circuit.genes || []).map((gene) => gene.symbol));
    return [...symbols].every((symbol) => ['AP3', 'PI', 'SUP'].includes(symbol));
  });

  return (
    <main className="control-demo">
      <section className="control-demo-hero">
        <button type="button" className="control-demo-back" onClick={onBack}>← Darwin home</button>
        <p className="control-demo-kicker">New guided demonstration · Species-wide control discovery</p>
        <h1>From millions of interactions to biological control architecture</h1>
        <p className="control-demo-lede">
          Darwin now separates evidence layers, scans complete species networks for signed feedback,
          connects feedback cores into larger systems, and identifies structural intervention points.
        </p>
        <div className="control-demo-hero-stats">
          <div><strong>{number(stats?.interactions)}</strong><span>regulatory relationships</span></div>
          <div><strong>{number(stats?.genes)}</strong><span>genes</span></div>
          <div><strong>{number(stats?.species)}</strong><span>species</span></div>
          <div><strong>{number(totals.cores)}</strong><span>observed feedback cores</span></div>
        </div>
        <button type="button" className="control-demo-primary" onClick={() => onOpenControl('arabidopsis')}>Explore the live control-system atlas</button>
      </section>

      {error && <div className="control-demo-error">Live data unavailable: {error}</div>}

      <section className="control-demo-body">
        <article className="control-demo-section">
          <header><span>01</span><div><p>Separate the evidence</p><h2>Not every edge makes the same claim</h2></div></header>
          <div className="control-evidence-grid">
            <div className="observed"><span>Observed signed</span><strong>{number(evidenceLayers.directSigned)}</strong><p>Curated activation and repression records can enter the default signed graph.</p></div>
            <div className="context"><span>Direct binding</span><strong>{number(evidenceLayers.directUnsigned)}</strong><p>Binding supports a relationship but does not independently determine its sign.</p></div>
            <div className="perturbation"><span>Perturbation signed</span><strong>{number(evidenceLayers.perturbation)}</strong><p>Direction inferred from reviewed perturbation evidence, with calibration gates.</p></div>
            <div className="exploratory"><span>Orthology transferred</span><strong>{number(evidenceLayers.transferred)}</strong><p>Explicitly exploratory recipient-species hypotheses, never silently promoted.</p></div>
          </div>
          <div className="control-model-layers">
            <div><strong>{number(stats?.analysis_layers?.directed_inferred_edges)}</strong><span>directed inference edges</span></div>
            <div><strong>{number(stats?.analysis_layers?.celltype_regulatory_edges)}</strong><span>cell-type regulatory edges</span></div>
            <div><strong>{number(stats?.analysis_layers?.perturbation_observations)}</strong><span>perturbation observations</span></div>
            <div><strong>{number(stats?.analysis_layers?.chromatin_peaks)}</strong><span>chromatin peaks</span></div>
            <div><strong>{number(stats?.analysis_layers?.structural_binding_predictions)}</strong><span>structural predictions</span></div>
          </div>
          <p className="control-demo-boundary">The default feedback graph uses signed observed evidence. Inferred, transferred, and multilayer relationships remain selectable and visibly labeled.</p>
        </article>

        <article className="control-demo-section">
          <header><span>02</span><div><p>Scan every species</p><h2>Recover feedback-capable regions at atlas scale</h2></div></header>
          <div className="control-species-grid">
            {SPECIES.map((species) => {
              const summary = feedback[species]?.summary || {};
              return (
                <button key={species} type="button" onClick={() => onOpenControl(species)} className={summary.feedback_cores ? '' : 'empty'}>
                  <span>{LABELS[species]}</span>
                  <strong>{number(summary.feedback_cores)}</strong>
                  <small>feedback cores</small>
                  <p>{number(summary.feedback_genes)} genes · {number(summary.feedback_edges)} edges</p>
                </button>
              );
            })}
          </div>
          <p className="control-demo-boundary">A feedback core is a structurally strongly connected signed region. It is not evidence that the region oscillates, switches, or controls a phenotype in vivo.</p>
        </article>

        <article className="control-demo-section control-architecture-section">
          <header><span>03</span><div><p>Explain a discovered controller</p><h2>AP3–PI–SUP maintains the stamen–carpel boundary</h2></div></header>
          <p className="control-mechanism-intro">
            Darwin recovered a mixed-feedback controller with a directly visible developmental outcome. AP3 and PI
            reinforce the B-class floral identity program that specifies petals and stamens. They also support SUP
            expression at the inner stamen boundary, where SUP represses AP3 and PI from spreading into the
            carpel-forming center of the flower.
          </p>
          <FloralBoundaryMechanism circuits={floralCircuits} />
          <div className="control-mechanism-interpretation">
            <div>
              <span>Reinforcing arm</span>
              <strong>AP3 and PI stabilize stamen identity</strong>
              <p>Mutual activation and AP3 autoregulation help maintain the B-class floral program after it is established.</p>
            </div>
            <div>
              <span>Restraining arm</span>
              <strong>SUP keeps that program out of whorl 4</strong>
              <p>AP3/PI support SUP, while SUP represses AP3/PI at the boundary: two negative-feedback loops contain the domain.</p>
            </div>
            <div>
              <span>Visible perturbation</span>
              <strong>Loss of SUP produces extra stamens</strong>
              <p>AP3/PI expression expands inward, replacing central carpel tissue and weakening floral determinacy.</p>
            </div>
          </div>
          <p className="control-demo-boundary">
            This is a known biological benchmark, not a novel Darwin claim. Genetic studies show that SUP maintains
            the whorl 3/4 boundary and that loss of SUP permits ectopic AP3/PI expression and extra stamens. See{' '}
            <a href="https://pubmed.ncbi.nlm.nih.gov/7477325/" target="_blank" rel="noreferrer">Sakai et al., Nature (1995)</a>
            {' '}and <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC5502645/" target="_blank" rel="noreferrer">Prunet et al., PNAS (2017)</a>.
          </p>
          <div className="control-neighborhood-section">
            <p className="control-map-title">How the boundary controller interacts with its central-core neighborhood</p>
            <p className="control-map-subtitle">A readable local view of measured signed relationships around AP3, PI, and SUP.</p>
            <FloralCoreNeighborhood system={floralSystem} />
          </div>
        </article>

        <article className="control-demo-section">
          <header><span>04</span><div><p>Find intervention points</p><h2>Ask what must be interrupted to eliminate feedback</h2></div></header>
          <p className="control-controller-intro">
            A feedback-vertex set is the smallest set of genes that touches every directed cycle in a graph.
            Removing those nodes turns a cyclic regulatory system into an acyclic one. This answers a structural
            question; it does not automatically identify the safest or most useful biological perturbation.
          </p>
          <div className="control-local-controller">
            <div className="control-local-answer">
              <p className="control-demo-kicker">Exact result for the displayed AP3–PI–SUP graph</p>
              <div><span>AP3</span><strong>+</strong><span>PI</span></div>
              <h3>Both identity regulators are required to break every local cycle</h3>
              <p>AP3 and PI each have a self-reinforcing edge. Selecting both also intersects their mutual-activation loop and both SUP feedback loops.</p>
            </div>
            <div className="control-local-comparison">
              <div>
                <span>Structurally breaks feedback</span>
                <strong>Interrupt AP3 + PI</strong>
                <p>The selected three-gene graph becomes acyclic, but the B-class petal/stamen identity program is also disrupted.</p>
              </div>
              <div>
                <span>Changes behavior without breaking all feedback</span>
                <strong>Interrupt SUP alone</strong>
                <p>The boundary brake is lost, while AP3–PI reinforcement remains. The expected direction is expansion of stamen identity, not elimination of the identity loop.</p>
              </div>
            </div>
          </div>
          <div className="control-core-controller-section">
            <div>
              <p className="control-demo-kicker">Scaling to the 157-gene central core</p>
              <h3>The large-core result is a bounded prioritization, not a complete solution</h3>
              <p>The exact search is too large, so Darwin greedily ranks genes that intersect returned representative cycles. The current run is truncated and does not claim that these seven genes break every cycle.</p>
            </div>
            <aside><strong>{number(arabidopsisSummary.controller_candidates)}</strong><span>controller candidates across all returned Arabidopsis cores</span></aside>
          </div>
          <div className="control-controller-list">
            {controllers.map((gene) => (
              <div key={gene.id}>
                <strong>{gene.symbol}</strong>
                <span>{CONTROLLER_PROGRAMS[gene.symbol] || gene.name}</span>
                <small>intersects {gene.representative_circuit_count} returned representative circuit</small>
              </div>
            ))}
          </div>
          <p className="control-demo-boundary">A feedback-vertex set is a topology result. It does not determine perturbation direction or guarantee control of a biological attractor.</p>
          <button type="button" className="control-demo-primary" onClick={() => onOpenControl('arabidopsis')}>Inspect cores, cycles, bridges, and controllers →</button>
        </article>
      </section>

      <section className="control-demo-finish">
        <p className="control-demo-kicker">What the new atlas enables</p>
        <h2>Move from an edge collection to evidence-aware control hypotheses</h2>
        <p>Start with observed structure, then ask exactly what candidate, transferred, cell-type, or multilayer evidence would change.</p>
        <button type="button" className="control-demo-primary" onClick={() => onOpenControl('arabidopsis')}>Open feedback and control systems</button>
      </section>
    </main>
  );
}
