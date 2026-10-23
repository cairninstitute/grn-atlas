import React from 'react';

const CENTER = 170;
const RADIUS = 92;

function pointAt(position, length, radius = RADIUS) {
  const angle = (position / length) * Math.PI * 2 - Math.PI / 2;
  return {
    x: CENTER + Math.cos(angle) * radius,
    y: CENTER + Math.sin(angle) * radius,
    angle,
  };
}

function directionArrow(insert, length, orientation) {
  if (!insert) return null;
  const middle = (insert.start + (insert.end - insert.start) * 0.52) % length;
  const tip = pointAt(middle, length, RADIUS);
  const direction = orientation === 'reverse' ? -1 : 1;
  const tangent = { x: -Math.sin(tip.angle) * direction, y: Math.cos(tip.angle) * direction };
  const radial = { x: Math.cos(tip.angle), y: Math.sin(tip.angle) };
  const base = { x: tip.x - tangent.x * 15, y: tip.y - tangent.y * 15 };
  return [
    `${tip.x + tangent.x * 8},${tip.y + tangent.y * 8}`,
    `${base.x + radial.x * 9},${base.y + radial.y * 9}`,
    `${base.x - radial.x * 9},${base.y - radial.y * 9}`,
  ].join(' ');
}

function JunctionSequence({ side, junction }) {
  if (!junction?.sequence) return null;
  const split = Math.min(20, junction.sequence.length);
  return (
    <div className="clonelab-junction-sequence">
      <span>{side} junction · {junction.position.toLocaleString()} bp</span>
      <code><i>{junction.sequence.slice(0, split)}</i><b>{junction.sequence.slice(split)}</b></code>
    </div>
  );
}

function LinearStructure({ construct, length }) {
  const components = construct.components?.length
    ? construct.components
    : [{ type: 'vector', start: 0, end: length }];
  return (
    <div className="clonelab-linear-structure" aria-label="Linearized molecular component map">
      {components.map((component, index) => {
        const size = component.end - component.start;
        return (
          <div key={`${component.type}-${index}`} className={`clonelab-component ${component.type}`}
            style={{ flexGrow: Math.max(size, length * 0.025) }}
            title={`${component.type}, ${component.start}-${component.end} (${size} bp)`}>
            <strong>{component.type === 'insert'
              ? `${component.orientation === 'reverse' ? '←' : '→'} INSERT`
              : 'VECTOR'}</strong>
            <span>{size.toLocaleString()} bp</span>
          </div>
        );
      })}
    </div>
  );
}

export default function PlasmidMap({ construct, digest }) {
  if (!construct) return null;
  const length = construct.length || construct.sequence?.length || 1;
  const insert = construct.insert_interval;
  const circumference = 2 * Math.PI * RADIUS;
  const insertLength = insert ? insert.end - insert.start : 0;
  const insertDash = circumference * insertLength / length;
  const insertOffset = -circumference * (insert?.start || 0) / length;
  const cutSites = digest?.cut_sites || [];
  const junctionPoints = insert
    ? [{ key: 'L', position: insert.start }, { key: 'R', position: insert.end % length }]
    : [];
  const orientationLabel = construct.orientation
    ? `${construct.orientation} orientation`
    : 'vector only';

  return (
    <article className="clonelab-map-wrap">
      <div className="clonelab-structure-heading">
        <div><span>{construct.hypothesis_id}</span><strong>{construct.label || 'Construct'}</strong></div>
        <em>{orientationLabel}</em>
      </div>
      <svg className="clonelab-map" viewBox="0 0 340 320" role="img"
        aria-label={`${construct.label || 'Construct'} circular molecular structure, ${length} base pairs`}>
        <defs>
          <filter id={`glow-${construct.hypothesis_id}`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <circle cx={CENTER} cy={CENTER} r={RADIUS + 24} className="clonelab-map-guide" />
        <circle cx={CENTER} cy={CENTER} r={RADIUS} className="clonelab-map-backbone" />
        {insert && <circle cx={CENTER} cy={CENTER} r={RADIUS} className="clonelab-map-insert"
          strokeDasharray={`${insertDash} ${circumference - insertDash}`} strokeDashoffset={insertOffset}
          filter={`url(#glow-${construct.hypothesis_id})`} />}
        {insert && <polygon points={directionArrow(insert, length, construct.orientation)} className="clonelab-insert-arrow" />}
        {junctionPoints.map((junction) => {
          const location = pointAt(junction.position, length, RADIUS);
          const label = pointAt(junction.position, length, RADIUS + 18);
          return <g key={junction.key}>
            <circle cx={location.x} cy={location.y} r="5" className="clonelab-junction-dot" />
            <text x={label.x} y={label.y + 4} textAnchor="middle" className="clonelab-junction-label">{junction.key}</text>
          </g>;
        })}
        {cutSites.slice(0, 8).map((site, index) => {
          const inner = pointAt(site.top_cut, length, RADIUS + 12);
          const outer = pointAt(site.top_cut, length, RADIUS + 27);
          const label = pointAt(site.top_cut, length, RADIUS + 39 + (index % 2) * 8);
          return <g key={`${site.enzyme}-${site.top_cut}-${index}`}>
            <line x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} className="clonelab-cut-line" />
            <text x={label.x} y={label.y + 3} textAnchor={label.x < CENTER - 8 ? 'end' : label.x > CENTER + 8 ? 'start' : 'middle'}
              className="clonelab-cut-label">{site.enzyme} · {site.top_cut}</text>
          </g>;
        })}
        <text x={CENTER} y={CENTER - 11} textAnchor="middle" className="clonelab-map-name">{construct.label || 'Construct'}</text>
        <text x={CENTER} y={CENTER + 13} textAnchor="middle" className="clonelab-map-length">{length.toLocaleString()} bp</text>
        <text x={CENTER} y={CENTER + 33} textAnchor="middle" className="clonelab-map-topology">CIRCULAR DNA</text>
      </svg>
      <LinearStructure construct={construct} length={length} />
      <div className="clonelab-structure-key">
        <span><i className="insert" />Insert</span><span><i className="vector" />Vector</span>
        <span><i className="junction" />Junction</span><span><i className="cut" />Digest cut</span>
      </div>
      {construct.junctions && <div className="clonelab-junctions">
        <JunctionSequence side="Left" junction={construct.junctions.left} />
        <JunctionSequence side="Right" junction={construct.junctions.right} />
      </div>}
      <div className="clonelab-construct-identity">
        <span>SHA-256</span><code>{construct.sequence_sha256?.slice(0, 16) || 'not available'}…</code>
        {cutSites.length > 8 && <em>+{cutSites.length - 8} additional cut sites</em>}
      </div>
    </article>
  );
}
