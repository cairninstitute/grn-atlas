import React from 'react';
import WorkflowWorkspace from '../WorkflowWorkspace';

export default function DecisionWorkflow(props) {
  return (
    <WorkflowWorkspace
      {...props}
      kicker="Decision workflow"
      title="Turn current evidence into a recommendation, next step, and handoff artifact."
      subtitle="Use this when the main question is what the atlas supports, what remains uncertain, and what should happen next."
      visibleSections={['context', 'analysis', 'consensus', 'planning', 'literature', 'design', 'advanced']}
      showExamples={false}
    />
  );
}
