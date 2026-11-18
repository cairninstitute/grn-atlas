import React, { useEffect, useState } from 'react';
import GeneSearchInput from '../GeneSearchInput';

const JOURNEYS = [
  {
    id: 'network',
    eyebrow: 'Known gene',
    title: 'Understand a regulatory neighborhood',
    description: 'See upstream regulators, downstream targets, evidence strength, and signed interactions.',
    action: 'Open gene explorer',
  },
  {
    id: 'feedback',
    eyebrow: 'Whole species',
    title: 'Find feedback and control systems',
    description: 'Discover signed circuits, connected control cores, and larger feedback architectures.',
    action: 'Discover control systems',
  },
  {
    id: 'intervention',
    eyebrow: 'Experimental goal',
    title: 'Plan a genetic intervention',
    description: 'Compare intervention strategies and move from a network hypothesis toward an assay.',
    action: 'Plan an intervention',
  },
  {
    id: 'clonelab',
    eyebrow: 'Molecular validation',
    title: 'Build and verify a DNA construct',
    description: 'Assemble a virtual construct, optimize diagnostic digests, and predict gel patterns.',
    action: 'Open CloneLab',
  },
];

const EXAMPLES = [
  { symbol: 'AN2', species: 'petunia', note: 'Flower pigmentation' },
  { symbol: 'LHY', species: 'arabidopsis', note: 'Circadian regulation' },
  { symbol: 'TP53', species: 'human', note: 'Tumor suppressor network' },
];

export default function HomeWorkspace({ onNavigate, onGeneSearch, onOpenGeneSet }) {
  const [query, setQuery] = useState('');
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetch('/api/v1/stats')
      .then((response) => response.json())
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  const selectGene = (gene) => {
    onGeneSearch(gene.symbol, gene);
    onNavigate('network');
  };

  const submitSearch = (event) => {
    event.preventDefault();
    const symbol = query.trim();
    if (!symbol) return;
    onGeneSearch(symbol);
    onNavigate('network');
  };

  return (
    <div className="home-workspace">
      <section className="home-hero">
        <div className="home-hero-copy">
          <p className="home-kicker">From gene to hypothesis. From construct to evidence.</p>
          <h1>What do you want to understand?</h1>
          <p>
            Darwin connects regulatory networks, comparative evidence, intervention design, and
            molecular validation. Start with a gene, or choose the kind of question you have.
          </p>

          <form className="home-search" onSubmit={submitSearch}>
            <div className="home-search-field">
              <label htmlFor="darwin-home-search">Search by gene symbol, name, or locus</label>
              <GeneSearchInput
                value={query}
                onChange={setQuery}
                onSelect={selectGene}
                placeholder="Try AN2, LHY, TP53, or an Ensembl/TAIR identifier"
              />
            </div>
            <button type="submit" className="home-search-button">Explore gene</button>
          </form>

          <div className="home-examples" aria-label="Example genes">
            <span>Try an example</span>
            {EXAMPLES.map((example) => (
              <button key={`${example.species}-${example.symbol}`} onClick={() => {
                setQuery(example.symbol);
                onGeneSearch(example.symbol);
                onNavigate('network');
              }}>
                <strong>{example.symbol}</strong>
                <small>{example.note}</small>
              </button>
            ))}
          </div>
        </div>

        <aside className="home-atlas-summary" aria-label="Atlas summary">
          <span className="home-summary-label">Atlas coverage</span>
          <strong>{stats?.species || 8}</strong>
          <span>species</span>
          <div className="home-summary-rule" />
          <strong>{stats?.genes ? stats.genes.toLocaleString() : '142,253'}</strong>
          <span>genes</span>
          <div className="home-summary-rule" />
          <strong>{stats?.interactions ? stats.interactions.toLocaleString() : '4.2M+'}</strong>
          <span>regulatory relationships</span>
          <button onClick={() => onNavigate('organism')}>Browse species coverage</button>
        </aside>
      </section>

      <section className="home-journeys" aria-labelledby="home-journeys-title">
        <div className="home-featured-demos">
          <button className="home-featured-demo" type="button" onClick={() => onNavigate('control-demo')}>
            <span className="home-featured-label">Featured guided demonstration</span>
            <span className="home-featured-title">From millions of interactions to biological control architecture</span>
            <span className="home-featured-copy">Discover feedback cores across eight species, connect them into larger systems, and identify structural controller genes.</span>
            <span className="home-featured-action">Start the demonstration →</span>
          </button>
          <button className="home-featured-demo secondary" type="button" onClick={() => onNavigate('evidence-tier')}>
            <span className="home-featured-label">Evidence integrity tool</span>
            <span className="home-featured-title">Evidence-tier slider</span>
            <span className="home-featured-copy">Watch the feedback core grow and shrink as evidence sources are toggled. Compare graph states across atlas builds.</span>
            <span className="home-featured-action">Open the slider →</span>
          </button>
          <button className="home-featured-demo secondary" type="button" onClick={() => onNavigate('sign-analysis')}>
            <span className="home-featured-label">Sign prediction analysis</span>
            <span className="home-featured-title">Where sign prediction breaks</span>
            <span className="home-featured-copy">Four independent methods all fail on the same task. See why predicting activation vs repression resists global models.</span>
            <span className="home-featured-action">View the analysis →</span>
          </button>
        </div>
        <div className="home-section-heading">
          <div>
            <p className="home-section-kicker">Research paths</p>
            <h2 id="home-journeys-title">Choose a starting point</h2>
          </div>
          <button className="home-text-action" onClick={onOpenGeneSet}>Analyze a gene list instead</button>
        </div>
        <div className="home-journey-grid">
          {JOURNEYS.map((card, index) => (
          <button
            key={card.id}
            type="button"
            className="home-journey-card"
            onClick={() => onNavigate(card.id)}
          >
            <span className="home-journey-number">0{index + 1}</span>
            <span className="home-journey-eyebrow">{card.eyebrow}</span>
            <strong>{card.title}</strong>
            <p>{card.description}</p>
            <span className="home-journey-action">{card.action} <span aria-hidden="true">→</span></span>
          </button>
          ))}
        </div>
      </section>
    </div>
  );
}
