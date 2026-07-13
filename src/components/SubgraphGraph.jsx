import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import { getCytoscapeStyle, getLayout } from './NetworkVisualization';
import { geneLabel } from '../utils/geneLabel';

// Render an arbitrary induced subgraph ({nodes, edges} from /pathways/subgraph)
// using the same Cytoscape styling as the main network view.
export default function SubgraphGraph({ nodes, edges, onNodeClick }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !nodes) return;
    const elements = [
      ...nodes.map((n) => ({
        data: {
          id: n.id, label: geneLabel(n).label, symbol: n.symbol, name: n.name,
          is_tf: !!n.is_tf, species: n.species, type: 'target',
        },
      })),
      ...edges.map((e) => ({
        data: {
          id: `${e.source}->${e.target}`,
          source: e.source, target: e.target,
          regulation_type: e.regulation_type || 'unknown',
          confidence: e.confidence || 0.5,
          source_databases: e.source_databases || [],
          inferred: e.inferred ? 1 : 0,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: getCytoscapeStyle(),
      layout: getLayout('cose'),
      wheelSensitivity: 0.1,
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;
    if (onNodeClick) cy.on('tap', 'node', (evt) => onNodeClick(evt.target.data()));

    return () => cy.destroy();
  }, [nodes, edges, onNodeClick]);

  return <div ref={containerRef} className="subgraph-canvas" />;
}
