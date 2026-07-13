import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import '../styles/NetworkVisualization.css';

export default function PathwayGraph({ paths, highlightPath, sourceGene, targetSymbol, sourceIds, targetSymbols, onCyInit, onNodeAction }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);

  const allSourceIds = new Set(sourceIds || (sourceGene ? [sourceGene.id] : []));
  const allTargetSyms = new Set(targetSymbols || (targetSymbol ? [targetSymbol] : []));

  // Build/rebuild graph when paths change
  useEffect(() => {
    if (!containerRef.current || !paths || paths.length === 0) return;

    const elements = buildPathElements(paths, allSourceIds, allTargetSyms);

    const roots = elements
      .filter(el => el.data.type === 'source')
      .map(el => el.data.id);

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: getPathStyle(),
      layout: {
        name: roots.length > 0 ? 'breadthfirst' : 'cose',
        directed: true,
        roots: roots.length > 0 ? roots : undefined,
        spacingFactor: 1.3,
        animate: true,
        animationDuration: 400
      },
      wheelSensitivity: 0.1,
      boxSelectionEnabled: false
    });

    cyRef.current = cy;
    onCyInit?.(cy);

    cy.on('mouseover', 'node', (evt) => evt.target.addClass('hover'));
    cy.on('mouseout', 'node', (evt) => evt.target.removeClass('hover'));

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const pos = evt.renderedPosition || evt.position;
      setContextMenu({ x: pos.x, y: pos.y, nodeId: node.id(), nodeLabel: node.data('label') });
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) setContextMenu(null);
    });

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
      onCyInit?.(null);
      cy.destroy();
    };
  }, [paths, sourceIds, targetSymbols, sourceGene, targetSymbol]);

  // Highlight effect — runs when selection changes without rebuilding the graph
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass('dimmed highlighted');

    if (!highlightPath) return;

    const genes = highlightPath.genes || [];
    const highlightNodeIds = new Set(genes.map(g => g.id));
    const highlightEdgeIds = new Set();
    for (let i = 0; i < genes.length - 1; i++) {
      highlightEdgeIds.add(`${genes[i].id}->${genes[i + 1].id}`);
    }

    cy.elements().forEach(el => {
      const id = el.id();
      if (el.isNode()) {
        el.addClass(highlightNodeIds.has(id) ? 'highlighted' : 'dimmed');
      } else {
        el.addClass(highlightEdgeIds.has(id) ? 'highlighted' : 'dimmed');
      }
    });
  }, [highlightPath]);

  return (
    <div className="network-visualization pathway-graph">
      <div className="network-canvas" ref={containerRef} />

      {tooltip && (
        <div className="network-tooltip">
          <div className="tooltip-header">
            <span className="tooltip-source">{tooltip.source}</span>
            <span className="tooltip-arrow">&rarr;</span>
            <span className="tooltip-target">{tooltip.target}</span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">Type:</span>
            <span className={`tooltip-value regulation-type-${tooltip.type}`}>
              {tooltip.type === 'activation' ? '✓ Activation' : tooltip.type === 'repression' ? '✗ Repression' : tooltip.type === 'regulation' ? '● Regulation' : '? Unknown'}
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

      {contextMenu && (
        <div className="node-context-menu" style={{ left: contextMenu.x + 10, top: contextMenu.y + 10 }}>
          <div className="context-menu-header">{contextMenu.nodeLabel}</div>
          <button className="context-menu-action" onClick={() => {
            onNodeAction?.(contextMenu.nodeId, contextMenu.nodeLabel, 'view-neighborhood');
            setContextMenu(null);
          }}>View neighborhood</button>
          <button className="context-menu-action" onClick={() => {
            onNodeAction?.(contextMenu.nodeId, contextMenu.nodeLabel, 'path-from');
            setContextMenu(null);
          }}>Find paths from here</button>
          <button className="context-menu-action" onClick={() => {
            onNodeAction?.(contextMenu.nodeId, contextMenu.nodeLabel, 'path-to');
            setContextMenu(null);
          }}>Find paths to here</button>
        </div>
      )}

      <div className="network-legend">
        <div className="legend-title">Legend</div>
        <div className="legend-item">
          <div className="legend-symbol node-source"></div>
          <span>Source gene</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol node-path-target"></div>
          <span>Target gene</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol node-intermediate"></div>
          <span>Intermediate</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol edge-activation"></div>
          <span>Activation</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol edge-repression"></div>
          <span>Repression</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol edge-regulation"></div>
          <span>Regulation</span>
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

function buildPathElements(paths, sourceIds, targetSyms) {
  const nodes = new Map();
  const edges = new Map();

  paths.forEach((path) => {
    const genes = path.genes || [];
    genes.forEach((g, i) => {
      if (!nodes.has(g.id)) {
        let type = 'intermediate';
        if (sourceIds.has(g.id)) type = 'source';
        else if (i === genes.length - 1 && targetSyms.has(g.symbol)) type = 'target';
        nodes.set(g.id, { id: g.id, label: g.symbol, name: g.name, type });
      } else {
        const existing = nodes.get(g.id);
        if (sourceIds.has(g.id) && existing.type !== 'source') {
          existing.type = 'source';
        } else if (i === genes.length - 1 && targetSyms.has(g.symbol) && existing.type === 'intermediate') {
          existing.type = 'target';
        }
      }
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
        'height': '45px',
        'transition-property': 'opacity, border-width',
        'transition-duration': '0.2s'
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
      style: { 'border-width': '3px' }
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
        'opacity': '0.8',
        'transition-property': 'opacity, width',
        'transition-duration': '0.2s'
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
      selector: 'edge[regulation_type="regulation"]',
      style: { 'line-color': '#7E57C2', 'target-arrow-color': '#7E57C2', 'edge_color': '#7E57C2' }
    },
    {
      selector: 'edge[regulation_type="unknown"]',
      style: { 'line-color': '#999999', 'target-arrow-color': '#999999', 'edge_color': '#999999' }
    },
    {
      selector: 'edge:hover',
      style: { 'opacity': '1', 'width': 'mapData(confidence, 0.3, 0.9, 2, 4)' }
    },
    // Dimmed elements (not on the selected path)
    {
      selector: '.dimmed',
      style: { 'opacity': 0.15 }
    },
    // Highlighted elements (on the selected path)
    {
      selector: 'node.highlighted',
      style: { 'opacity': 1, 'border-width': '3px', 'z-index': 20 }
    },
    {
      selector: 'edge.highlighted',
      style: { 'opacity': 1, 'width': 'mapData(confidence, 0.3, 0.9, 2, 5)', 'z-index': 20 }
    }
  ];
}
