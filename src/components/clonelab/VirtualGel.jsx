import React from 'react';

export default function VirtualGel({ gel }) {
  if (!gel) return null;
  return (
    <section className="clonelab-panel">
      <div className="clonelab-panel-heading">
        <div><span className="clonelab-step">04</span><h2>Predicted gel</h2></div>
        <span className="clonelab-prediction-badge">SIMULATION</span>
      </div>
      <div className="clonelab-gel" role="img" aria-label="Predicted agarose gel lanes">
        {gel.lanes.map((lane) => (
          <div className="clonelab-lane" key={lane.lane_id}>
            <div className="clonelab-well" />
            {lane.bands.map((band) => (
              <button key={band.band_id} className="clonelab-band"
                style={{ top: `${8 + band.migration * 80}%`, opacity: Math.max(0.48, band.relative_intensity) }}
                title={`${band.source_fragments_bp.join(' + ')} bp${band.merged ? ' (co-migrating)' : ''}`}>
                <span className="sr-only">{band.representative_bp} bp</span>
              </button>
            ))}
            <div className="clonelab-lane-label">{lane.label}</div>
          </div>
        ))}
      </div>
      <p className="clonelab-boundary">{gel.model_boundary}</p>
      {gel.calibration && <p className="clonelab-calibration"><strong>{gel.calibration.label}</strong> · {gel.calibration.evidence_type.replaceAll('_', ' ')}</p>}
      <table className="clonelab-table">
        <thead><tr><th>Lane</th><th>Predicted bands</th><th>Hidden</th></tr></thead>
        <tbody>{gel.lanes.map((lane) => <tr key={lane.lane_id}>
          <td>{lane.label}</td>
          <td>{lane.bands.map((band) => `${band.representative_bp}${band.merged ? '*' : ''}`).join(', ') || 'No linear prediction'}</td>
          <td>{lane.hidden_fragments.join(', ') || 'None'}</td>
        </tr>)}</tbody>
      </table>
    </section>
  );
}
