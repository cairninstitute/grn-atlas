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
];

export default function HomeWorkspace({ onSelectMode }) {
  return (
    <div className="workflow-workspace">
      <div className="workflow-hero">
        <div>
          <p className="workflow-kicker">Workflow-first atlas</p>
          <h1>Choose the way your research question starts.</h1>
          <p className="workflow-subtitle">
            The UI is now organized around researcher entry modes instead of a flat tool catalog.
            You can still reach the legacy panels under Advanced tools, but the primary path is now
            question-first and context-persistent.
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
