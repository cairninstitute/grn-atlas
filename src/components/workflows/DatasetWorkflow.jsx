import React from 'react';
import WorkflowWorkspace from '../WorkflowWorkspace';

export default function DatasetWorkflow(props) {
  return (
    <WorkflowWorkspace
      {...props}
      kicker="Dataset-first workflow"
      title="Normalize, map, interpret, and rank a user-provided gene set."
      subtitle="Use this when the work starts from a hit list, DEG output, or pasted gene identifiers."
      visibleSections={['context', 'import', 'analysis', 'consensus', 'planning']}
      showExamples={false}
    />
  );
}
