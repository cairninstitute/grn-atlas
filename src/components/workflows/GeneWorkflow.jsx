import React from 'react';
import WorkflowWorkspace from '../WorkflowWorkspace';

export default function GeneWorkflow(props) {
  const { selectedGene, onNavigate, onOpenDsRna } = props;
  return (
    <div className="workflow-workspace">
      <div className="workflow-hero">
        <div>
          <p className="workflow-kicker">Gene-first workflow</p>
          <h1>Explore a known target and choose the next action.</h1>
          <p className="workflow-subtitle">
            Start from a specific gene, inspect its local network and context, then move into
            literature, differential follow-up, perturbation planning, or assay design.
          </p>
        </div>
        {selectedGene && (
          <div className="workflow-hero-actions">
            <button onClick={() => onNavigate?.('advanced')}>Open advanced tools</button>
            <button onClick={() => onNavigate?.('advanced:network')}>Open explorer</button>
            <button onClick={() => onOpenDsRna?.({ target: selectedGene })}>Design dsRNA</button>
          </div>
        )}
      </div>
      <WorkflowWorkspace
        {...props}
        showHero={false}
        showExamples={false}
        visibleSections={['context', 'analysis', 'consensus', 'differential', 'literature', 'design', 'planning']}
      />
    </div>
  );
}
