import React from 'react';
import { useResearchSession } from '../../state/ResearchSessionContext';

export default function ResearchContextBar() {
  const { state } = useResearchSession();
  const focusGene = state.focusGene?.label || state.focusGene?.symbol || state.focusGene?.id || 'None';
  const candidateCount = state.candidateSet?.length || 0;
  const artifactCount = Object.values(state.artifacts || {}).filter(Boolean).length;
  const hasContext = state.species || state.focusGene || candidateCount || artifactCount;

  if (!hasContext) return null;

  return (
    <div className="research-context-bar">
      <span className="research-context-kicker">Working context</span>
      <div className="research-context-primary">
        {state.species && <span><small>Species</small><strong>{state.species}</strong></span>}
        {state.focusGene && <span><small>Focus</small><strong>{focusGene}</strong></span>}
        {candidateCount > 0 && <span><small>Candidates</small><strong>{candidateCount}</strong></span>}
      </div>
      {artifactCount > 0 && <span className="research-context-output">{artifactCount} output{artifactCount === 1 ? '' : 's'} ready</span>}
    </div>
  );
}
