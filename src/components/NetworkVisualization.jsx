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
  const expandedRef = useRef(new Set());
  const hiddenByRef = useRef(new Map());
  const [, setSelectedNode] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [nodeTooltip, setNodeTooltip] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [expandCount, setExpandCount] = useState(0);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: convertDataToCytoscape(data, gene),
      style: getCytoscapeStyle(),
      layout: { name: 'preset' },
      wheelSensitivity: 0.1,
      autounselectify: false,
      boxSelectionEnabled: false
    });

    cyRef.current = cy;
    expandedRef.current = new Set();
    hiddenByRef.current = new Map();
    setExpandCount(0);
    onCyInit?.(cy);


    // Node hover - show gene description tooltip
    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      setSelectedNode(node.id());
      node.addClass('hover');
      const name = node.data('name');
      if (name) {
        const pos = evt.renderedPosition;
        setNodeTooltip({
          x: pos.x,
          y: pos.y,
          label: node.data('label'),
          name,
          type: node.data('type'),
        });
      }
    });

    cy.on('mouseout', 'node', (evt) => {
      evt.target.removeClass('hover');
      setNodeTooltip(null);
    });

    cy.on('pan zoom', () => setNodeTooltip(null));

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

    // Node click — expand or collapse neighborhood
    cy.on('tap', 'node', async (evt) => {
      const node = evt.target;
      const nodeId = node.id();
      setSelectedNode(nodeId);
      setContextMenu(null);

      if (nodeId === gene.id) return;

      const expanded = expandedRef.current;

      if (expanded.has(nodeId)) {
        cy.elements(`[expanded_from = "${nodeId}"]`).remove();
        expanded.delete(nodeId);
        node.removeClass('expanded');
        const hidden = hiddenByRef.current.get(nodeId);
        if (hidden) {
          hidden.forEach((ele) => ele.show());
          hiddenByRef.current.delete(nodeId);
        }
        setExpandCount((c) => c - 1);
        runLayout(cy);
        return;
      }

      try {
        const parentTier = node.data('tier') || 0;
        const expandDir = parentTier < 0 ? 'regulators' : parentTier > 0 ? 'targets' : 'both';

        const res = await fetch(`/api/v1/pathways/neighborhood/${encodeURIComponent(nodeId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            max_depth: 1,
            direction: expandDir,
            min_confidence: filters?.minConfidence || 0.4,
          }),
        });
        if (!res.ok) return;
        const nbr = await res.json();

        const neighbors = expandDir === 'regulators'
          ? (nbr.regulators || []).map(n => ({ ...n, _isReg: true }))
          : expandDir === 'targets'
            ? (nbr.targets || []).map(n => ({ ...n, _isReg: false }))
            : [
                ...(nbr.regulators || []).map(n => ({ ...n, _isReg: true })),
                ...(nbr.targets || []).map(n => ({ ...n, _isReg: false })),
              ];

        const newEles = [];
        const parentPos = node.position();

        for (const n of neighbors) {
          const isReg = n._isReg;

          if (cy.getElementById(n.id).length > 0) {
            const edgeId = `${isReg ? n.id : nodeId}-${isReg ? nodeId : n.id}-exp`;
            if (cy.getElementById(edgeId).length === 0) {
              newEles.push({
                group: 'edges',
                data: {
                  id: edgeId,
                  source: isReg ? n.id : nodeId,
                  target: isReg ? nodeId : n.id,
                  regulation_type: n.regulation_type || 'regulation',
                  confidence: n.confidence || 0.5,
                  source_databases: n.source_databases || [],
                  inferred: n.inferred ? 1 : 0,
                  expanded_from: nodeId,
                },
              });
            }
            continue;
          }

          const childTier = isReg ? parentTier - 1 : parentTier + 1;
          newEles.push({
            group: 'nodes',
            data: {
              id: n.id,
              label: nodeLabel(n),
              name: n.name,
              is_tf: n.is_tf,
              type: isReg ? 'regulator' : 'target',
              species: n.species,
              expanded_from: nodeId,
              tier: childTier,
            },
            position: {
              x: parentPos.x + (Math.random() - 0.5) * 80,
              y: parentPos.y + (isReg ? -120 : 120),
            },
          });

          const src = isReg ? n.id : nodeId;
          const tgt = isReg ? nodeId : n.id;
          newEles.push({
            group: 'edges',
            data: {
              id: `${src}-${tgt}-exp`,
              source: src,
              target: tgt,
              regulation_type: n.regulation_type || 'regulation',
              confidence: n.confidence || 0.5,
              source_databases: n.source_databases || [],
              inferred: n.inferred ? 1 : 0,
              expanded_from: nodeId,
            },
          });
        }

        if (newEles.length > 0) {
          cy.add(newEles);
          expanded.add(nodeId);
          node.addClass('expanded');

          const nodeTier = node.data('tier') || 0;
          const siblings = cy.nodes().filter((n) => {
            if (n.id() === nodeId) return false;
            if (n.data('expanded_from') === nodeId) return false;
            return (n.data('tier') || 0) === nodeTier;
          });
          const toHide = cy.collection();
          siblings.forEach((sib) => {
            toHide.merge(sib);
            toHide.merge(sib.connectedEdges());
          });
          toHide.hide();
          hiddenByRef.current.set(nodeId, toHide);

          setExpandCount((c) => c + 1);
          runLayout(cy);
        }
      } catch (err) {
        console.error('Expand failed:', err);
      }
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) setContextMenu(null);
    });

    // Right-click context menu for path-finding
    cy.on('cxttap', 'node', (evt) => {
      const node = evt.target;
      const pos = evt.renderedPosition || evt.position;
      setContextMenu({
        x: pos.x,
        y: pos.y,
        nodeId: node.id(),
        nodeLabel: node.data('label'),
      });
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

      {nodeTooltip && (
        <div className="network-node-tooltip" style={{ left: nodeTooltip.x + 12, top: nodeTooltip.y - 8 }}>
          <strong>{nodeTooltip.label}</strong>
          <span>{nodeTooltip.name}</span>
        </div>
      )}

      {contextMenu && (
        <div className="node-context-menu" style={{ left: contextMenu.x + 10, top: contextMenu.y + 10 }}>
          <div className="context-menu-header">{contextMenu.nodeLabel}</div>
          <button className="context-menu-action" onClick={() => {
            onNodeAction?.(contextMenu.nodeId, contextMenu.nodeLabel, 'view-neighborhood');
            setContextMenu(null);
          }}>Make focus gene</button>
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

        <div style={{ marginTop: '6px', paddingTop: '6px', borderTop: '0.5px solid var(--border)' }}>
          <div className="legend-title">Confidence</div>
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
        <div className="legend-hint">
          Click an upstream gene to see its regulators. Click a downstream gene to see its targets.
          {expandCount > 0 && ' Click again to collapse.'}
          <br />Right-click for more options.
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
        <button className="control-button" title="Re-arrange layout" onClick={() => runLayout(cyRef.current)}>
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

function nodeLabel(gene) {
  const sym = gene.label || gene.symbol;
  const cn = gene.common_name;
  if (cn && cn.toUpperCase() !== sym.toUpperCase()) return `${sym} / ${cn}`;
  return sym;
}

const MAX_PER_ROW = 12;
const X_SPACING = 60;
const ROW_SPACING = 160;
const SUB_ROW_SPACING = 50;

function positionTierNodes(nodes, baseTier) {
  const positions = [];
  const rowCount = Math.ceil(nodes.length / MAX_PER_ROW);
  for (let r = 0; r < rowCount; r++) {
    const start = r * MAX_PER_ROW;
    const slice = nodes.slice(start, start + MAX_PER_ROW);
    const subOffset = baseTier < 0
      ? -(rowCount - 1 - r) * SUB_ROW_SPACING
      : r * SUB_ROW_SPACING;
    const y = baseTier * ROW_SPACING + subOffset;
    slice.forEach((node, i) => {
      positions.push({ node, x: (i - (slice.length - 1) / 2) * X_SPACING, y });
    });
  }
  return positions;
}

function runLayout(cy) {
  const tiers = {};
  cy.nodes().forEach((n) => {
    const t = n.data('tier') || 0;
    (tiers[t] = tiers[t] || []).push(n);
  });

  const allPositions = [];
  Object.keys(tiers).map(Number).sort((a, b) => a - b).forEach((t) => {
    allPositions.push(...positionTierNodes(tiers[t], t));
  });

  allPositions.forEach(({ node, x, y }) => {
    node.animate({ position: { x, y }, duration: 400, easing: 'ease-out' });
  });

  setTimeout(() => cy.fit(undefined, 50), 450);
}

function convertDataToCytoscape(data, selectedGene) {
  const elements = [];
  const processedNodes = new Set();


  function layoutRow(items, tier) {
    const positions = [];
    const rowCount = Math.ceil(items.length / MAX_PER_ROW);
    for (let r = 0; r < rowCount; r++) {
      const slice = items.slice(r * MAX_PER_ROW, (r + 1) * MAX_PER_ROW);
      const subOffset = tier < 0
        ? -(rowCount - 1 - r) * SUB_ROW_SPACING
        : r * SUB_ROW_SPACING;
      const y = tier * ROW_SPACING + subOffset;
      slice.forEach((_, i) => {
        positions.push({ x: (i - (slice.length - 1) / 2) * X_SPACING, y });
      });
    }
    return positions;
  }

  if (data?.nodes?.length && data?.edges?.length) {
    const regs = new Set((data.regulators || []).map(r => r.id));
    const tgts = new Set((data.targets || []).map(t => t.id));
    const regNodes = data.nodes.filter(n => regs.has(n.id));
    const tgtNodes = data.nodes.filter(n => tgts.has(n.id));
    const regPos = layoutRow(regNodes, -1);
    const tgtPos = layoutRow(tgtNodes, 1);
    let rI = 0, tI = 0;

    data.nodes.forEach((node) => {
      const isSelected = node.id === selectedGene.id;
      const isReg = regs.has(node.id);
      const isTgt = tgts.has(node.id);
      let pos;
      if (isSelected) pos = { x: 0, y: 0 };
      else if (isReg) pos = regPos[rI++];
      else if (isTgt) pos = tgtPos[tI++];
      else pos = { x: 0, y: 0 };
      elements.push({
        data: {
          id: node.id, label: nodeLabel(node), name: node.name,
          is_tf: node.is_tf, species: node.species,
          type: isSelected ? 'selected' : (isReg ? 'regulator' : (isTgt ? 'target' : 'intermediate')),
          tier: isSelected ? 0 : (isReg ? -1 : (isTgt ? 1 : 0)),
        },
        position: pos,
      });
      processedNodes.add(node.id);
    });
    data.edges.forEach((edge) => {
      elements.push({
        data: {
          id: `${edge.source_id}-${edge.target_id}-${edge.regulation_type}`,
          source: edge.source_id, target: edge.target_id,
          regulation_type: edge.regulation_type || 'unknown',
          confidence: edge.confidence || 0.5,
          source_databases: edge.source_databases || [],
          inferred: edge.inferred ? 1 : 0, type: 'network-edge',
        }
      });
    });
    return elements;
  }

  elements.push({
    data: {
      id: selectedGene.id, label: nodeLabel(selectedGene), name: selectedGene.name,
      is_tf: selectedGene.is_tf, type: 'selected', species: selectedGene.species, tier: 0,
    },
    position: { x: 0, y: 0 },
  });
  processedNodes.add(selectedGene.id);

  const regPositions = layoutRow(data.regulators || [], -1);
  if (data.regulators) {
    data.regulators.forEach((reg, i) => {
      if (!processedNodes.has(reg.id)) {
        elements.push({
          data: {
            id: reg.id, label: nodeLabel(reg), name: reg.name, is_tf: reg.is_tf,
            type: 'regulator', species: reg.species, tier: -1,
          },
          position: regPositions[i],
        });
        processedNodes.add(reg.id);
      }
      elements.push({
        data: {
          id: `${reg.id}-${selectedGene.id}`, source: reg.id, target: selectedGene.id,
          regulation_type: reg.regulation_type || 'unknown', confidence: reg.confidence || 0.5,
          source_databases: reg.source_databases || [], inferred: reg.inferred ? 1 : 0,
          type: 'regulator-edge',
        }
      });
    });
  }

  const tgtPositions = layoutRow(data.targets || [], 1);
  if (data.targets) {
    data.targets.forEach((tgt, i) => {
      if (!processedNodes.has(tgt.id)) {
        elements.push({
          data: {
            id: tgt.id, label: nodeLabel(tgt), name: tgt.name, is_tf: tgt.is_tf,
            type: 'target', species: tgt.species, tier: 1,
          },
          position: tgtPositions[i],
        });
        processedNodes.add(tgt.id);
      }
      elements.push({
        data: {
          id: `${selectedGene.id}-${tgt.id}`, source: selectedGene.id, target: tgt.id,
          regulation_type: tgt.regulation_type || 'unknown', confidence: tgt.confidence || 0.5,
          source_databases: tgt.source_databases || [], inferred: tgt.inferred ? 1 : 0,
          type: 'target-edge',
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
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 4,
        'font-size': '9px',
        'font-weight': '500',
        'border-width': '1.5px',
        'color': '#ccc',
        'text-max-width': '100px',
        'text-wrap': 'wrap',
        'text-outline-color': '#111',
        'text-outline-width': 1,
      }
    },
    {
      selector: 'node[type="selected"]',
      style: {
        'background-color': '#3B8BD4',
        'border-color': '#185FA5',
        'color': 'white',
        'text-valign': 'center',
        'text-halign': 'center',
        'text-margin-y': 0,
        'font-size': '11px',
        'font-weight': '700',
        'width': '40px',
        'height': '40px',
        'z-index': '10'
      }
    },
    {
      selector: 'node[?is_tf][type!="selected"]',
      style: {
        'background-color': '#7F77DD',
        'border-color': '#534AB7',
        'width': '28px',
        'height': '28px',
        'shape': 'diamond',
        'z-index': '5'
      }
    },
    {
      selector: 'node[!is_tf]',
      style: {
        'background-color': '#888780',
        'border-color': '#5F5E5A',
        'width': '22px',
        'height': '22px',
        'shape': 'ellipse',
        'z-index': '4'
      }
    },
    {
      selector: 'node.expanded',
      style: {
        'border-width': '2.5px',
        'border-color': '#4FC3F7',
        'width': '32px',
        'height': '32px',
      }
    },
    {
      selector: 'node:hover',
      style: {
        'border-width': '2.5px',
        'cursor': 'pointer',
      }
    },
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        'width': 1.5,
        'line-color': 'data(edge_color)',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': 'data(edge_color)',
        'arrow-scale': '1',
        'opacity': '0.65'
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
      selector: 'edge[inferred = 1]',
      style: {
        'opacity': '0.4'
      }
    },
    {
      selector: 'edge:hover',
      style: {
        'opacity': '1',
        'width': 2.5
      }
    }
  ];
}

export function getLayout(layoutName = 'preset') {
  const layouts = {
    preset: { name: 'preset' },
    concentric: {
      name: 'concentric',
      concentric: (node) => {
        if (node.data('type') === 'selected') return 3;
        if (node.data('is_tf')) return 2;
        return 1;
      },
      levelWidth: () => 1,
      minNodeSpacing: 30,
      animate: true,
      animationDuration: 500
    },
  };
  return layouts[layoutName] || layouts.preset;
}
