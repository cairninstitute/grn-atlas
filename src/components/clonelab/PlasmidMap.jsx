import React from 'react';

export default function PlasmidMap({ construct }) {
  if (!construct) return null;
  const length = construct.length || construct.sequence?.length || 1;
  const insert = construct.insert_interval;
  const circumference = 2 * Math.PI * 76;
  const insertLength = insert ? insert.end - insert.start : 0;
  const insertDash = circumference * insertLength / length;
  const insertOffset = -circumference * (insert?.start || 0) / length;
  return (
    <div className="clonelab-map-wrap">
      <svg className="clonelab-map" viewBox="0 0 220 220" role="img" aria-label={`Circular construct map, ${length} base pairs`}>
        <circle cx="110" cy="110" r="76" className="clonelab-map-backbone" />
        {insert && <circle cx="110" cy="110" r="76" className="clonelab-map-insert"
          strokeDasharray={`${insertDash} ${circumference - insertDash}`} strokeDashoffset={insertOffset} />}
        <text x="110" y="101" textAnchor="middle" className="clonelab-map-name">{construct.label || 'Construct'}</text>
        <text x="110" y="123" textAnchor="middle" className="clonelab-map-length">{length.toLocaleString()} bp</text>
      </svg>
      <div className="clonelab-map-key"><i /> Insert <span /> Vector backbone</div>
    </div>
  );
}
