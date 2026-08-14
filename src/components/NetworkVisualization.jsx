import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import popper from 'cytoscape-popper';
import '../styles/NetworkVisualization.css';

// Register popper extension
cytoscape.use(popper);

export default function NetworkVisualization({
  gene,
  data,
  filters,
  expandedNodes: _expandedNodes,
  onNodeExpand: _onNodeExpand,
  onCyInit,
  onNodeAction,
  onDepthChange,
}) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [, setSelectedNode] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    // Initialize Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      elements: convertDataToCytoscape(data, gene),
      style: getCytoscapeStyle(),
      layout: getLayout(),
      wheelSensitivity: 0.1,
      autounselectify: false,
      boxSelectionEnabled: false
    });

    cyRef.current = cy;
    onCyInit?.(cy);

    // Node hover - show tooltip with confidence and sources
    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode(node.id());
      node.addClass('hover');
    });

    cy.on('mouseout', 'node', (evt) => {
      evt.target.removeClass('hover');
    });

    // Edge hover - show detailed tooltip
    cy.on('mouseover', 'edge', (evt) => {
      const edge = evt.target;
      const sourceNode = edge.source();
      const targetNode = edge.target();

      const tooltipContent = {
        source: sourceNode.data('label'),
        target: targetNode.data('label'),
        type: edge.data('regulation_type'),
        confidence: edge.data('confidence'),
        sources: edge.data('source_databases')
      };

      setTooltip(tooltipContent);
      edge.addClass('hover');
    });

    cy.on('mouseout', 'edge', (evt) => {
      evt.target.removeClass('hover');
      setTooltip(null);
    });

    // Node click - show context menu
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode(node.id());
      const pos = evt.renderedPosition || evt.position;
      setContextMenu({
        x: pos.x,
        y: pos.y,
        nodeId: node.id(),
        nodeLabel: node.data('label')
      });
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) setContextMenu(null);
    });

    // Fit to view on load
    cy.fit(cy.elements(), 50);

    // Responsive resize
    const handleResize = () => {
      if (cy) cy.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      onCyInit?.(null);
      cy.destroy();
    };
  }, [data, gene, filters]);

  return (
    <div className="network-visualization">
      <div className="network-canvas" ref={containerRef} />

      <div className="network-depth-bar">
        <span className="network-depth-label">Neighborhood depth</span>
        <div className="network-depth-switcher">
          {[1, 2, 3].map((depth) => (
            <button
              key={depth}
              className={`depth-button ${filters?.maxDepth === depth ? 'active' : ''}`}
              title={`Show ${depth}-hop neighborhood`}
              onClick={() => onDepthChange?.(depth)}
            >
              {depth} hop{depth === 1 ? '' : 's'}
            </button>
          ))}
        </div>
      </div>
      
      {tooltip && (
        <div className="network-tooltip">
          <div className="tooltip-header">
            <span className="tooltip-arrow">→</span>
            <span className="tooltip-source">{tooltip.source}</span>
            <span className="tooltip-target">{tooltip.target}</span>
          </div>
          
          <div className="tooltip-row">
            <span className="tooltip-label">Type:</span>
            <span className={`tooltip-value regulation-type-${tooltip.type}`}>
              {tooltip.type === 'activation' ? '✓ Activation' : tooltip.type === 'repression' ? '✗ Repression' : '● Regulation'}
            </span>
          </div>
          
          <div className="tooltip-row">
            <span className="tooltip-label">Confidence:</span>
            <span className="tooltip-value">{(tooltip.confidence * 100).toFixed(0)}%</span>
          </div>
          
          <div className="tooltip-row">
            <span className="tooltip-label">Sources:</span>
            <div className="tooltip-sources">
              {tooltip.sources?.map((source, idx) => (
                <span key={idx} className="source-badge">{source}</span>
              ))}
            </div>
          </div>
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
          <span>Current focus gene</span>
        </div>
        
        <div className="legend-item">
          <div className="legend-symbol node-tf"></div>
          <span>Transcription Factor</span>
        </div>
        
        <div className="legend-item">
          <div className="legend-symbol node-target"></div>
          <span>Target Gene</span>
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

        <div style={{ marginTop: '12px', paddingTop: '8px', borderTop: '0.5px solid var(--border)' }}>
          <div className="legend-title" style={{ fontSize: '11px', marginBottom: '4px' }}>Confidence</div>
          <div className="legend-item">
            <div className="legend-symbol edge-confidence-high"></div>
            <span>High: solid</span>
          </div>
          <div className="legend-item">
            <div className="legend-symbol edge-confidence-medium"></div>
            <span>Medium: dashed</span>
          </div>
          <div className="legend-item">
            <div className="legend-symbol edge-confidence-low"></div>
            <span>Low: dotted</span>
          </div>
        </div>
      </div>

      <div className="network-controls">
        <button className="control-button" title="Zoom in" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.2)}>
          🔍+
        </button>
        <button className="control-button" title="Zoom out" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() / 1.2)}>
          🔍-
        </button>
        <button className="control-button" title="Fit to screen" onClick={() => cyRef.current?.fit(cyRef.current?.elements(), 50)}>
          ⊡
        </button>
        <button className="control-button" title="Circular layout" onClick={() => applyLayout('concentric')}>
          ◯
        </button>
        <button className="control-button" title="Hierarchical layout" onClick={() => applyLayout('klay')}>
          ⬇
        </button>
      </div>
    </div>
  );

  function applyLayout(layoutName) {
    if (!cyRef.current) return;
    const layout = cyRef.current.layout(getLayout(layoutName));
    layout.run();
  }
}

// Convert API data to Cytoscape elements format
function convertDataToCytoscape(data, selectedGene) {
  const elements = [];
  const processedNodes = new Set();
  const selectedLabel = selectedGene.label || selectedGene.symbol;

  if (data?.nodes?.length && data?.edges?.length) {
    data.nodes.forEach((node) => {
      const isSelected = node.id === selectedGene.id;
      const isDirectRegulator = !!data.regulators?.some((reg) => reg.id === node.id);
      const isDirectTarget = !!data.targets?.some((target) => target.id === node.id);
      elements.push({
        data: {
          id: node.id,
          label: node.label || node.symbol,
          name: node.name,
          is_tf: node.is_tf,
          type: isSelected ? 'selected' : (isDirectRegulator ? 'regulator' : (isDirectTarget ? 'target' : 'intermediate')),
          species: node.species,
        }
      });
      processedNodes.add(node.id);
    });

    data.edges.forEach((edge) => {
      elements.push({
        data: {
          id: `${edge.source_id}-${edge.target_id}-${edge.regulation_type}`,
          source: edge.source_id,
          target: edge.target_id,
          regulation_type: edge.regulation_type || 'unknown',
          confidence: edge.confidence || 0.5,
          source_databases: edge.source_databases || [],
          inferred: edge.inferred ? 1 : 0,
          type: 'network-edge',
        }
      });
    });

    return elements;
  }

  // Add the main selected gene
  elements.push({
    data: {
      id: selectedGene.id,
      label: selectedLabel,
      name: selectedGene.name,
      is_tf: selectedGene.is_tf,
      type: 'selected',
      species: selectedGene.species
    }
  });
  processedNodes.add(selectedGene.id);

  // Add regulators (genes that regulate the selected gene)
  if (data.regulators) {
    data.regulators.forEach((regulator) => {
      if (!processedNodes.has(regulator.id)) {
        elements.push({
          data: {
            id: regulator.id,
            label: regulator.symbol,
            name: regulator.name,
            is_tf: regulator.is_tf,
            type: 'regulator',
            species: regulator.species
          }
        });
        processedNodes.add(regulator.id);
      }

      // Add edge from regulator to selected gene
      elements.push({
        data: {
          id: `${regulator.id}-${selectedGene.id}`,
          source: regulator.id,
          target: selectedGene.id,
          regulation_type: regulator.regulation_type || 'unknown',
          confidence: regulator.confidence || 0.5,
          source_databases: regulator.source_databases || [],
          inferred: regulator.inferred ? 1 : 0,
          type: 'regulator-edge'
        }
      });
    });
  }

  // Add targets (genes regulated by the selected gene)
  if (data.targets) {
    data.targets.forEach((target) => {
      if (!processedNodes.has(target.id)) {
        elements.push({
          data: {
            id: target.id,
            label: target.symbol,
            name: target.name,
            is_tf: target.is_tf,
            type: 'target',
            species: target.species
          }
        });
        processedNodes.add(target.id);
      }

      // Add edge from selected gene to target
      elements.push({
        data: {
          id: `${selectedGene.id}-${target.id}`,
          source: selectedGene.id,
          target: target.id,
          regulation_type: target.regulation_type || 'unknown',
          confidence: target.confidence || 0.5,
          source_databases: target.source_databases || [],
          inferred: target.inferred ? 1 : 0,
          type: 'target-edge'
        }
      });
    });
  }

  return elements;
}

// Cytoscape style configuration
export function getCytoscapeStyle() {
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
        'color': 'var(--text-primary)',
        'text-max-width': '100px',
        'text-wrap': 'wrap'
      }
    },
    {
      selector: 'node[type="selected"]',
      style: {
        'background-color': '#3B8BD4',
        'border-color': '#185FA5',
        'color': 'white',
        'width': '60px',
        'height': '60px',
        'z-index': '10'
      }
    },
    {
      selector: 'node[?is_tf][type!="selected"]',
      style: {
        'background-color': '#7F77DD',
        'border-color': '#534AB7',
        'color': 'white',
        'width': '50px',
        'height': '50px',
        'shape': 'diamond',
        'z-index': '5'
      }
    },
    {
      selector: 'node[!is_tf]',
      style: {
        'background-color': '#888780',
        'border-color': '#5F5E5A',
        'color': 'white',
        'width': '45px',
        'height': '45px',
        'shape': 'ellipse',
        'z-index': '4'
      }
    },
    {
      selector: 'node:hover',
      style: {
        'border-width': '3px',
        'box-shadow': '0 0 0 2px rgba(0,0,0,0.1)'
      }
    },
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        'width': 2.5,
        'line-color': 'data(edge_color)',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': 'data(edge_color)',
        'arrow-scale': '1.5',
        'opacity': '0.7'
      }
    },
    {
      selector: 'edge[regulation_type="activation"]',
      style: {
        'line-color': '#4CAF50',
        'target-arrow-color': '#4CAF50',
        'edge_color': '#4CAF50'
      }
    },
    {
      selector: 'edge[regulation_type="repression"]',
      style: {
        'line-color': '#F44336',
        'target-arrow-color': '#F44336',
        'target-arrow-shape': 'tee',
        'edge_color': '#F44336'
      }
    },
    {
      selector: 'edge[regulation_type="regulation"]',
      style: {
        'line-color': '#7E57C2',
        'target-arrow-color': '#7E57C2',
        'edge_color': '#7E57C2'
      }
    },
    {
      selector: 'edge[regulation_type="unknown"]',
      style: {
        'line-color': '#999999',
        'target-arrow-color': '#999999',
        'edge_color': '#999999'
      }
    },
    {
      selector: 'edge[confidence >= 0.75]',
      style: {
        'line-style': 'solid'
      }
    },
    {
      selector: 'edge[confidence >= 0.6][confidence < 0.75]',
      style: {
        'line-style': 'dashed'
      }
    },
    {
      selector: 'edge[confidence < 0.6]',
      style: {
        'line-style': 'dotted'
      }
    },
    {
      // Orthology-projected (inferred) edges: faded.
      selector: 'edge[inferred = 1]',
      style: {
        'opacity': '0.45'
      }
    },
    {
      selector: 'edge:hover',
      style: {
        'opacity': '1',
        'width': 3.5
      }
    }
  ];
}

// Layout configuration
export function getLayout(layoutName = 'cose') {
  const layouts = {
    cose: {
      name: 'cose',
      directed: true,
      roots: undefined,
      randomize: false,
      animate: true,
      animationDuration: 500,
      animationEasing: 'ease-out',
      nodeSpacing: 10,
      edgeElasticity: 0.45,
      nodeRepulsion: 4500,
      gravity: 0.25,
      cooling: 0.9
    },
    concentric: {
      name: 'concentric',
      concentric: (node) => {
        if (node.data('type') === 'selected') return 3;
        if (node.data('is_tf')) return 2;
        return 1;
      },
      levelWidth: () => 90,
      animate: true,
      animationDuration: 500
    },
    klay: {
      name: 'klay',
      nodePlacementStrategy: 'SIMPLE',
      klay: {
        direction: 'DOWN',
        compactComponents: true,
        separateConnectedComponents: false
      }
    }
  };
  return layouts[layoutName] || layouts.cose;
}
