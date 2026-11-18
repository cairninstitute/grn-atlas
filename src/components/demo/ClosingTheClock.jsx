import React from 'react';
import '../../styles/ClosingTheClock.css';

const CLOCK_GENES = [
  { id: 'AT2G46830', symbol: 'CCA1', role: 'Morning loop activator', x: 50, y: 20 },
  { id: 'AT1G01060', symbol: 'LHY', role: 'Morning loop activator', x: 20, y: 45 },
  { id: 'AT5G61380', symbol: 'TOC1', role: 'Evening loop component', x: 80, y: 45 },
  { id: 'AT5G02810', symbol: 'PRR7', role: 'Daytime repressor', x: 65, y: 75 },
  { id: 'AT3G46640', symbol: 'PCL1', role: 'Morning-phased activator', x: 35, y: 75 },
  { id: 'AT2G25930', symbol: 'ELF3', role: 'Evening complex', x: 50, y: 95 },
];

const CONFIRMED_EDGES = [
  { from: 'CCA1', to: 'TOC1', sign: 'repression' },
  { from: 'CCA1', to: 'LHY', sign: 'repression' },
  { from: 'CCA1', to: 'PRR7', sign: 'activation' },
  { from: 'CCA1', to: 'PCL1', sign: 'repression' },
  { from: 'LHY', to: 'TOC1', sign: 'repression' },
  { from: 'LHY', to: 'PRR7', sign: 'activation' },
  { from: 'LHY', to: 'PCL1', sign: 'repression' },
  { from: 'PCL1', to: 'CCA1', sign: 'activation' },
  { from: 'PCL1', to: 'LHY', sign: 'activation' },
  { from: 'PCL1', to: 'TOC1', sign: 'repression' },
  { from: 'PCL1', to: 'PCL1', sign: 'repression' },
];

const CANDIDATE_EDGES = [
  { from: 'TOC1', to: 'CCA1', sign: 'repression', evidence: 'ChIP-seq binding known; repression inferred from expression anti-phase', experiment: 'TOC1 OE at ZT12 → CCA1 qRT-PCR' },
  { from: 'TOC1', to: 'LHY', sign: 'repression', evidence: 'ChIP-seq binding known; repression inferred from expression anti-phase', experiment: 'TOC1 OE at ZT12 → LHY qRT-PCR' },
  { from: 'PRR7', to: 'CCA1', sign: 'repression', evidence: 'PRR family represses morning genes (Nakamichi 2010)', experiment: 'PRR7 KO → CCA1 expression under LD' },
  { from: 'PRR7', to: 'LHY', sign: 'repression', evidence: 'PRR family represses morning genes (Nakamichi 2010)', experiment: 'PRR7 KO → LHY expression under LD' },
  { from: 'ELF3', to: 'LHY', sign: 'unknown', evidence: 'ELF3 → CCA1 edge exists (unsigned); LHY arm unconfirmed', experiment: 'ELF3 KO → LHY time-course under constant light' },
];

const UNSUPPORTED_EDGE = { from: 'ELF3', to: 'CCA1', sign: null, evidence: 'Edge exists in atlas (conf 0.51) but no sign assigned', experiment: 'Sign the ELF3 → CCA1 edge via ELF3 OE → CCA1 qRT-PCR' };

function ArrowSVG() {
  const genes = Object.fromEntries(CLOCK_GENES.map(g => [g.symbol, g]));
  const lines = [];

  CONFIRMED_EDGES.forEach((e, i) => {
    if (e.from === e.to) return;
    const f = genes[e.from], t = genes[e.to];
    if (!f || !t) return;
    lines.push(
      <line key={`c${i}`} x1={f.x} y1={f.y} x2={t.x} y2={t.y}
        className={`clock-edge confirmed ${e.sign}`}
        markerEnd={e.sign === 'activation' ? 'url(#arrow-act)' : 'url(#arrow-rep)'}
      />
    );
  });

  CANDIDATE_EDGES.forEach((e, i) => {
    const f = genes[e.from], t = genes[e.to];
    if (!f || !t) return;
    lines.push(
      <line key={`k${i}`} x1={f.x} y1={f.y} x2={t.x} y2={t.y}
        className="clock-edge candidate"
        strokeDasharray="4 3"
        markerEnd="url(#arrow-cand)"
      />
    );
  });

  return (
    <svg viewBox="0 0 100 110" className="clock-svg">
      <defs>
        <marker id="arrow-act" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <path d="M0,0 L8,3 L0,6" fill="#4a8876" />
        </marker>
        <marker id="arrow-rep" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <path d="M0,0 L8,3 L0,6" fill="#c0583e" />
        </marker>
        <marker id="arrow-cand" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <path d="M0,0 L8,3 L0,6" fill="#d08955" />
        </marker>
      </defs>
      {lines}
      {CLOCK_GENES.map(g => (
        <g key={g.id}>
          <circle cx={g.x} cy={g.y} r="4" className="clock-node" />
          <text x={g.x} y={g.y - 5.5} textAnchor="middle" className="clock-label">{g.symbol}</text>
        </g>
      ))}
    </svg>
  );
}

export default function ClosingTheClock() {
  return (
    <div className="closing-clock">
      <header className="clock-header">
        <h2>Closing the clock</h2>
        <p>
          The Arabidopsis circadian clock is one of the best-studied feedback systems in plant
          biology, yet the atlas shows that several return arms — the edges that complete the
          oscillator loop — still lack direct transcriptional evidence.
        </p>
      </header>

      <div className="clock-layout">
        <section className="clock-diagram-section">
          <h3>Circadian scaffold</h3>
          <div className="clock-diagram">
            <ArrowSVG />
          </div>
          <div className="clock-legend">
            <span className="clock-legend-item"><span className="clock-dot confirmed activation" /> Confirmed activation</span>
            <span className="clock-legend-item"><span className="clock-dot confirmed repression" /> Confirmed repression</span>
            <span className="clock-legend-item"><span className="clock-dot candidate" /> Candidate return arm</span>
          </div>
        </section>

        <section className="clock-genes-section">
          <h3>Clock components</h3>
          <div className="clock-gene-list">
            {CLOCK_GENES.map(g => (
              <div key={g.id} className="clock-gene-row">
                <strong>{g.symbol}</strong>
                <span>{g.role}</span>
                <code>{g.id}</code>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="clock-candidates">
        <h3>Candidate return arms</h3>
        <p className="clock-note">
          These edges would complete the negative feedback loop required for oscillation.
          Each is supported by indirect evidence but lacks direct transcriptional proof
          in the atlas. The experiment column suggests the minimum validation step.
        </p>
        <table className="clock-table">
          <thead>
            <tr>
              <th>Edge</th>
              <th>Predicted sign</th>
              <th>Supporting evidence</th>
              <th>Validation experiment</th>
            </tr>
          </thead>
          <tbody>
            {CANDIDATE_EDGES.map((e, i) => (
              <tr key={i}>
                <td><strong>{e.from} → {e.to}</strong></td>
                <td className={`clock-sign ${e.sign}`}>{e.sign}</td>
                <td>{e.evidence}</td>
                <td className="clock-experiment">{e.experiment}</td>
              </tr>
            ))}
            <tr className="clock-unsigned">
              <td><strong>{UNSUPPORTED_EDGE.from} → {UNSUPPORTED_EDGE.to}</strong></td>
              <td className="clock-sign unsigned">unsigned</td>
              <td>{UNSUPPORTED_EDGE.evidence}</td>
              <td className="clock-experiment">{UNSUPPORTED_EDGE.experiment}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="clock-kinetic">
        <h3>What the kinetic model predicts</h3>
        <div className="clock-boundary">
          <p>
            The existing confirmed edges (CCA1/LHY ⊣ TOC1, PCL1 → CCA1/LHY) form a partial
            oscillator. The <code>grn-kinetic-model</code> skill, run with Hill coefficients
            2–8, classifies this scaffold as capable of oscillation under some parameterizations.
          </p>
          <p>
            Adding the candidate TOC1 ⊣ CCA1/LHY return arms would create the classic
            repressilator-like negative feedback loop. The model predicts this closed loop
            robustly oscillates across a wider parameter range — matching the known ~24h period
            of the biological clock.
          </p>
          <p>
            <strong>The 24.2-hour period is a model assumption, not fitted data.</strong> The
            Hill coefficients and degradation rates are symmetric placeholders. The prediction
            is qualitative: "this topology can oscillate," not "it oscillates at exactly this
            frequency."
          </p>
        </div>
      </section>
    </div>
  );
}
