import React from 'react';

const CARDS = [
  {
    id: 'gene',
    title: 'Start from a gene',
    description: 'Known target exploration: network, expression, perturbation, orthology, and assay follow-up.',
  },
  {
    id: 'dataset',
    title: 'Start from a list, phenotype, or goal',
    description: 'Use one unified workflow: optionally begin with literature-guided candidate discovery, or skip straight to importing and mapping genes.',
  },
  {
    id: 'decision',
    title: 'Decide what to do next',
    description: 'Turn evidence into a recommendation, minimal next step, and collaborator-ready handoff artifact.',
  },
  {
    id: 'demo',
    title: 'Demo: Model gene to crop target',
    description: 'Guided walkthrough: start with an Arabidopsis gene, trace orthologs into crops, and design a dsRNA to silence the crop target.',
  },
];

export default function HomeWorkspace({ onSelectMode }) {
  return (
    <div className="workflow-workspace">
      <div className="workflow-hero">
        <div>
          <p className="workflow-kicker">From gene to hypothesis</p>
          <h1>Choose the way your research question starts.</h1>
          <p className="workflow-subtitle">
            Darwin organizes research around your question, not a tool catalog. Choose how your
            investigation starts — you can still reach all analysis panels under Advanced tools.
          </p>
        </div>
      </div>

      <div className="workflow-example-grid">
        {CARDS.map((card) => (
          <button
            key={card.id}
            type="button"
            className="workflow-example-card workflow-example-card-action"
            onClick={() => onSelectMode(card.id)}
          >
            <div className="workflow-example-title">{card.title}</div>
            <p>{card.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
