import React from 'react';
import { useResearchSession } from '../../state/ResearchSessionContext';

function ArtifactCard({ title, summary, detail, active, actionLabel, onAction }) {
  return (
    <div className={`artifact-card${active ? ' active' : ''}`}>
      <div className="artifact-card-header">
        <strong>{title}</strong>
        <span className={`artifact-state${active ? ' active' : ''}`}>{active ? 'Available' : 'Not generated'}</span>
      </div>
      <p>{summary || 'No artifact generated yet.'}</p>
      {detail ? <pre className="artifact-card-detail">{detail}</pre> : null}
      {active && actionLabel && onAction ? (
        <button type="button" className="artifact-action" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

export default function ArtifactDrawer({ open, onClose, onNavigate }) {
  const { state } = useResearchSession();
  const artifacts = state.artifacts || {};

  return (
    <div className={`artifact-drawer${open ? ' open' : ''}`} aria-hidden={!open}>
      <div className="artifact-drawer-backdrop" onClick={onClose} />
      <aside className="artifact-drawer-panel">
        <div className="artifact-drawer-header">
          <div>
            <div className="artifact-drawer-kicker">Research artifacts</div>
            <h2>Current workflow outputs</h2>
          </div>
          <button type="button" className="artifact-close" onClick={onClose}>×</button>
        </div>

        <div className="artifact-drawer-body">
          <ArtifactCard
            title="First-pass interpretation"
            active={!!artifacts.firstPass}
            summary={artifacts.firstPass?.summary}
            detail={artifacts.firstPass?.detail}
            actionLabel="Open dataset workflow"
            onAction={() => onNavigate?.('dataset')}
          />
          <ArtifactCard
            title="Consensus ranking"
            active={!!artifacts.consensus}
            summary={artifacts.consensus?.summary}
            detail={artifacts.consensus?.detail}
            actionLabel="Open decision workflow"
            onAction={() => onNavigate?.('decision')}
          />
          <ArtifactCard
            title="Study plan"
            active={!!artifacts.plan}
            summary={artifacts.plan?.summary}
            detail={artifacts.plan?.detail}
            actionLabel="Open decision workflow"
            onAction={() => onNavigate?.('decision')}
          />
          <ArtifactCard
            title="Collaborator report"
            active={!!artifacts.report}
            summary={artifacts.report?.summary}
            detail={artifacts.report?.detail}
            actionLabel="Open decision workflow"
            onAction={() => onNavigate?.('decision')}
          />
        </div>
      </aside>
    </div>
  );
}
