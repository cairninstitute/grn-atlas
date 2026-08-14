import React from 'react';
import WorkflowWorkspace from '../WorkflowWorkspace';

export default function DatasetWorkflow(props) {
  return (
    <WorkflowWorkspace
      {...props}
      kicker="Unified workflow"
      title="Start from a list, phenotype, or research goal."
      subtitle="Optionally use literature-guided candidate discovery, then normalize, map, interpret, rank, and plan in one flow."
      visibleSections={['context', 'phenotype', 'import', 'analysis', 'consensus', 'planning', 'literature']}
      showExamples={false}
    />
  );
}
