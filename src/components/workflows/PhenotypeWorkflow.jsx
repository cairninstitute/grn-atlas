import React from 'react';
import WorkflowWorkspace from '../WorkflowWorkspace';

export default function PhenotypeWorkflow(props) {
  return (
    <WorkflowWorkspace
      {...props}
      kicker="Phenotype-first workflow"
      title="Move from phenotype or intervention goal to species-grounded candidate genes."
      subtitle="Use literature-guided ideation, atlas mapping, ranking, support boundaries, and planning in one flow."
      visibleSections={['context', 'phenotype', 'import', 'analysis', 'consensus', 'planning', 'literature']}
      showExamples={false}
    />
  );
}
