import React from 'react';
import { useResearchSession } from '../../state/ResearchSessionContext';

function ArtifactChip({ active, label }) {
  return <span className={`research-context-chip${active ? ' active' : ''}`}>{label}</span>;
}

export default function ResearchContextBar() {
  const { state } = useResearchSession();
  const focusGene = state.focusGene?.label || state.focusGene?.symbol || state.focusGene?.id || 'None';
  const candidateCount = state.candidateSet?.length || 0;
  const comparison =
    state.comparison.groupA.length || state.comparison.groupB.length
      ? `${state.comparison.groupA.join(', ') || '–'} vs ${state.comparison.groupB.join(', ') || '–'}`
      : 'Not set';

  return (
    <div className="research-context-bar">
      <div className="research-context-primary">
        <div className="research-context-item">
          <span className="research-context-label">Species</span>
          <strong>{state.species || 'Not set'}</strong>
        </div>
        <div className="research-context-item">
          <span className="research-context-label">Focus gene</span>
          <strong>{focusGene}</strong>
        </div>
        <div className="research-context-item">
          <span className="research-context-label">Intent</span>
          <strong>{state.intent || 'experiment'}</strong>
        </div>
        <div className="research-context-item">
          <span className="research-context-label">Candidates</span>
          <strong>{candidateCount}</strong>
        </div>
        <div className="research-context-item">
          <span className="research-context-label">Comparison</span>
          <strong>{comparison}</strong>
        </div>
      </div>
      <div className="research-context-secondary">
        <ArtifactChip active={!!state.artifacts.firstPass} label="First-pass" />
        <ArtifactChip active={!!state.artifacts.consensus} label="Consensus" />
        <ArtifactChip active={!!state.artifacts.plan} label="Plan" />
        <ArtifactChip active={!!state.artifacts.report} label="Report" />
      </div>
    </div>
  );
}
