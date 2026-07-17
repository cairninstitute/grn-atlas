import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import '../styles/NetworkVisualization.css';

// Renders the union of all found paths as a single graph, source -> ... -> target
export default function PathwayGraph({ paths, sourceGene, targetSymbol }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    if (!containerRef.current || !paths || paths.length === 0) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: buildPathElements(paths, sourceGene),
      style: getPathStyle(),
      layout: {
        name: 'breadthfirst',
        directed: true,
        roots: sourceGene ? [sourceGene.id] : undefined,
        spacingFactor: 1.3,
        animate: true,
        animationDuration: 400
      },
      wheelSensitivity: 0.1,
      boxSelectionEnabled: false
    });

    cyRef.current = cy;

    cy.on('mouseover', 'node', (evt) => evt.target.addClass('hover'));
    cy.on('mouseout', 'node', (evt) => evt.target.removeClass('hover'));

    cy.on('mouseover', 'edge', (evt) => {
      const edge = evt.target;
      setTooltip({
        source: edge.source().data('label'),
        target: edge.target().data('label'),
        type: edge.data('regulation_type'),
        confidence: edge.data('confidence'),
        sources: edge.data('source_databases')
      });
      edge.addClass('hover');
    });

    cy.on('mouseout', 'edge', (evt) => {
      evt.target.removeClass('hover');
      setTooltip(null);
    });

    cy.fit(cy.elements(), 50);

    const handleResize = () => cy.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cy.destroy();
    };
  }, [paths, sourceGene, targetSymbol]);

  return (
    <div className="network-visualization pathway-graph">
      <div className="network-canvas" ref={containerRef} />

      {tooltip && (
        <div className="network-tooltip">
          <div className="tooltip-header">
            <span className="tooltip-source">{tooltip.source}</span>
            <span className="tooltip-arrow">→</span>
            <span className="tooltip-target">{tooltip.target}</span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">Type:</span>
            <span className={`tooltip-value regulation-type-${tooltip.type}`}>
              {tooltip.type === 'activation' ? '✓ Activation' : tooltip.type === 'repression' ? '✗ Repression' : '? Unknown'}
            </span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">Confidence:</span>
            <span className="tooltip-value">{(tooltip.confidence * 100).toFixed(0)}%</span>
          </div>
          {tooltip.sources?.length > 0 && (
            <div className="tooltip-row">
              <span className="tooltip-label">Sources:</span>
              <div className="tooltip-sources">
                {tooltip.sources.map((s, i) => <span key={i} className="source-badge">{s}</span>)}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="network-legend">
        <div className="legend-title">Legend</div>
        <div className="legend-item">
          <div className="legend-symbol node-source"></div>
          <span>{sourceGene?.symbol || 'Source'}</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol node-path-target"></div>
          <span>{targetSymbol || 'Target'}</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol node-intermediate"></div>
          <span>Intermediate gene</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol edge-activation"></div>
          <span>Activation</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol edge-repression"></div>
          <span>Repression</span>
        </div>
      </div>

      <div className="network-controls">
        <button className="control-button" title="Zoom in" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)}>🔍+</button>
        <button className="control-button" title="Zoom out" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() / 1.2)}>🔍-</button>
        <button className="control-button" title="Fit to screen" onClick={() => cyRef.current?.fit(cyRef.current?.elements(), 50)}>⊡</button>
      </div>
    </div>
  );
}

// Union all found paths into a single deduplicated node/edge set
function buildPathElements(paths, sourceGene) {
  const nodes = new Map();
  const edges = new Map();

  paths.forEach((path) => {
    const genes = path.genes || [];
    genes.forEach((g, i) => {
      if (nodes.has(g.id)) return;
      let type = 'intermediate';
      if (sourceGene && g.id === sourceGene.id) type = 'source';
      else if (i === genes.length - 1) type = 'target';
      nodes.set(g.id, { id: g.id, label: g.symbol, name: g.name, type });
    });

    for (let i = 0; i < genes.length - 1; i++) {
      const key = `${genes[i].id}->${genes[i + 1].id}`;
      if (edges.has(key)) continue;
      edges.set(key, {
        id: key,
        source: genes[i].id,
        target: genes[i + 1].id,
        regulation_type: path.regulation_types?.[i] || 'unknown',
        confidence: path.confidences?.[i] ?? 0.5,
        source_databases: path.sources?.[i] || []
      });
    }
  });

  return [
    ...Array.from(nodes.values()).map((data) => ({ data })),
    ...Array.from(edges.values()).map((data) => ({ data }))
  ];
}

function getPathStyle() {
  return [
    {
      selector: 'node',
      style: {
        'content': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '12px',
        'font-weight': '500',
        'padding': '8px',
        'border-width': '2px',
        'color': 'white',
        'text-max-width': '100px',
        'text-wrap': 'wrap',
        'background-color': '#888780',
        'border-color': '#5F5E5A',
        'width': '45px',
        'height': '45px'
      }
    },
    {
      selector: 'node[type="source"]',
      style: {
        'background-color': '#3B8BD4',
        'border-color': '#185FA5',
        'width': '60px',
        'height': '60px',
        'z-index': '10'
      }
    },
    {
      selector: 'node[type="target"]',
      style: {
        'background-color': '#E8A33D',
        'border-color': '#B87A1F',
        'shape': 'diamond',
        'width': '55px',
        'height': '55px',
        'z-index': '10'
      }
    },
    {
      selector: 'node:hover',
      style: { 'border-width': '3px', 'box-shadow': '0 0 0 2px rgba(0,0,0,0.1)' }
    },
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        'width': 'mapData(confidence, 0.3, 0.9, 1, 3)',
        'line-color': 'data(edge_color)',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': 'data(edge_color)',
        'arrow-scale': '1.5',
        'opacity': '0.8'
      }
    },
    {
      selector: 'edge[regulation_type="activation"]',
      style: { 'line-color': '#4CAF50', 'target-arrow-color': '#4CAF50', 'edge_color': '#4CAF50' }
    },
    {
      selector: 'edge[regulation_type="repression"]',
      style: { 'line-color': '#F44336', 'target-arrow-color': '#F44336', 'target-arrow-shape': 'tee', 'edge_color': '#F44336' }
    },
    {
      selector: 'edge[regulation_type="unknown"]',
      style: { 'line-color': '#999999', 'target-arrow-color': '#999999', 'edge_color': '#999999' }
    },
    {
      selector: 'edge:hover',
      style: { 'opacity': '1', 'width': 'mapData(confidence, 0.3, 0.9, 2, 4)' }
    }
  ];
}
