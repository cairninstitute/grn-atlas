import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import popper from 'cytoscape-popper';
import '../styles/NetworkVisualization.css';

// Register popper extension
cytoscape.use(popper);

export default function NetworkVisualization({ gene, data, filters, expandedNodes, onNodeExpand, onCyInit, onNodeAction }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const tooltipRef = useRef(null);

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
          <div className="confidence-scale">
            <div className="confidence-bar" style={{ width: '100%', height: '4px', background: 'linear-gradient(to right, #BDBDBD, #FDD835, #90CAF9)' }}></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-secondary)' }}>
              <span>Low (0.3)</span>
              <span>High (0.9)</span>
            </div>
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

  // Add the main selected gene
  elements.push({
    data: {
      id: selectedGene.id,
      label: selectedGene.symbol,
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
          type: 'target-edge'
        }
      });
    });
  }

  return elements;
}

// Cytoscape style configuration
function getCytoscapeStyle() {
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
      selector: 'node[is_tf=true][type!="selected"]',
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
      selector: 'node[is_tf=false]',
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
        'width': 'mapData(confidence, 0.3, 0.9, 1, 3)',
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
      selector: 'edge:hover',
      style: {
        'opacity': '1',
        'width': 'mapData(confidence, 0.3, 0.9, 2, 4)'
      }
    }
  ];
}

// Layout configuration
function getLayout(layoutName = 'cose') {
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
