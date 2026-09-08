import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import '../styles/CrossSpeciesView.css';

const SPECIES_META = {
  arabidopsis: { label: 'Arabidopsis', latin: 'A. thaliana', kingdom: 'plant' },
  tomato:      { label: 'Tomato',      latin: 'S. lycopersicum', kingdom: 'plant' },
  petunia:     { label: 'Petunia',     latin: 'P. axillaris', kingdom: 'plant' },
  potato:      { label: 'Potato',      latin: 'S. tuberosum', kingdom: 'plant' },
  rice:        { label: 'Rice',        latin: 'O. sativa', kingdom: 'plant' },
  pepper:      { label: 'Pepper',      latin: 'C. annuum', kingdom: 'plant' },
  human:       { label: 'Human',       latin: 'H. sapiens', kingdom: 'animal' },
  mouse:       { label: 'Mouse',       latin: 'M. musculus', kingdom: 'animal' },
};

const SP_COLOR_A = '#4FC3F7';
const SP_COLOR_B = '#FFB74D';
const SHARED_COLOR = '#4CAF50';

function truncLabel(s, max = 10) {
  if (!s || s.length <= max) return s;
  return s.slice(0, max - 1) + '…';
}

function buildGlobalSlotMap(speciesData, curatedOnly) {
  const familyCount = {};
  for (const sp of Object.keys(speciesData)) {
    const d = speciesData[sp];
    if (!d.edges?.length) continue;
    const seen = new Set();
    for (const e of d.edges) {
      if (curatedOnly && e.inferred) continue;
      const key = (e.family || e.partner_symbol || e.partner_id).toUpperCase();
      if (!seen.has(key)) {
        seen.add(key);
        familyCount[key] = (familyCount[key] || 0) + 1;
      }
    }
  }
  const sorted = Object.entries(familyCount)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const slotMap = {};
  const total = sorted.length;
  sorted.forEach(([key], i) => {
    const angle = (2 * Math.PI * i) / total - Math.PI / 2;
    slotMap[key] = angle;
  });
  return slotMap;
}

const CX = 150;
const CY = 120;
const RADIUS = 90;

function MiniNetwork({ data, centerSymbol, onSelect, slotMap, curatedOnly }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [nodeTooltip, setNodeTooltip] = useState(null);

  useEffect(() => {
    if (!containerRef.current || !data?.edges?.length) return;

    const visibleEdges = curatedOnly
      ? data.edges.filter((e) => !e.inferred)
      : data.edges;

    if (!visibleEdges.length) {
      if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; }
      return;
    }

    const elements = [];
    const centerId = data.gene_id;
    const positions = {};

    positions[centerId] = { x: CX, y: CY };
    elements.push({
      data: { id: centerId, label: truncLabel(centerSymbol, 12), type: 'center' },
    });

    const seen = new Set([centerId]);
    for (const e of visibleEdges) {
      if (seen.has(e.partner_id)) continue;
      seen.add(e.partner_id);
      const familyKey = (e.family || e.partner_symbol || e.partner_id).toUpperCase();
      const angle = slotMap[familyKey];
      if (angle === undefined) continue;
      positions[e.partner_id] = {
        x: CX + RADIUS * Math.cos(angle),
        y: CY + RADIUS * Math.sin(angle),
      };
      elements.push({
        data: {
          id: e.partner_id,
          label: truncLabel(e.partner_symbol),
          fullName: e.partner_name || '',
          type: e.inferred ? 'inferred' : 'curated',
        },
      });
    }

    for (const e of visibleEdges) {
      if (!positions[e.partner_id]) continue;
      const edgeId = e.direction === 'regulator'
        ? `${e.partner_id}->${centerId}`
        : `${centerId}->${e.partner_id}`;
      elements.push({
        data: {
          id: edgeId,
          source: e.direction === 'regulator' ? e.partner_id : centerId,
          target: e.direction === 'regulator' ? centerId : e.partner_id,
          regulation: e.regulation_type,
          edgeClass: e.inferred ? 'inferred' : 'curated',
        },
      });
    }

    const nPartners = Object.keys(positions).length - 1;
    const showLabels = nPartners <= 16;

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node[type="center"]',
          style: {
            'background-color': '#3B8BD4', label: 'data(label)',
            'font-size': '11px', 'text-valign': 'center', 'text-halign': 'center',
            color: '#fff', 'text-outline-color': '#3B8BD4', 'text-outline-width': 2,
            width: 40, height: 40,
          },
        },
        {
          selector: 'node[type="curated"]',
          style: {
            'background-color': '#4CAF50',
            label: showLabels ? 'data(label)' : '', 'font-size': '8px',
            'text-valign': 'bottom', 'text-margin-y': 3, color: '#ccc',
            width: 22, height: 22,
          },
        },
        {
          selector: 'node[type="inferred"]',
          style: {
            'background-color': '#3a3a3a', 'border-width': 2,
            'border-color': '#B0B0B0', 'border-style': 'dashed',
            label: showLabels ? 'data(label)' : '', 'font-size': '8px',
            'text-valign': 'bottom', 'text-margin-y': 3, color: '#999',
            width: 20, height: 20,
          },
        },
        {
          selector: 'edge[edgeClass="curated"]',
          style: {
            'line-color': '#4CAF50', 'target-arrow-color': '#4CAF50',
            width: 1.5, 'target-arrow-shape': 'triangle',
            'curve-style': 'bezier', opacity: 0.7,
          },
        },
        {
          selector: 'edge[edgeClass="inferred"]',
          style: {
            'line-color': '#B0B0B0', 'target-arrow-color': '#B0B0B0',
            'line-style': 'dashed', width: 1, 'target-arrow-shape': 'triangle',
            'curve-style': 'bezier', opacity: 0.5,
          },
        },
        {
          selector: 'edge[regulation="repression"][edgeClass="curated"]',
          style: { 'target-arrow-shape': 'tee', 'line-color': '#E57373', 'target-arrow-color': '#E57373' },
        },
        {
          selector: 'edge[regulation="repression"][edgeClass="inferred"]',
          style: { 'target-arrow-shape': 'tee' },
        },
      ],
      layout: {
        name: 'preset',
        positions: (node) => positions[node.id()] || { x: CX, y: CY },
      },
      userZoomingEnabled: false, userPanningEnabled: false,
      boxSelectionEnabled: false, autoungrabify: true,
    });

    cyRef.current = cy;
    cy.on('tap', 'node', (evt) => {
      const id = evt.target.id();
      if (id !== centerId) onSelect?.(id);
    });
    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      const fullName = node.data('fullName');
      if (!fullName) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pos = evt.renderedPosition;
      setNodeTooltip({
        x: pos.x + 12,
        y: pos.y - 8,
        label: node.data('label'),
        name: fullName,
      });
    });
    cy.on('mouseout', 'node', () => setNodeTooltip(null));
    cy.on('pan zoom', () => setNodeTooltip(null));
    return () => { if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; } };
  }, [data, centerSymbol, onSelect, slotMap, curatedOnly]);

  if (!data?.edges?.length) return null;
  const hasVisible = curatedOnly ? data.edges.some((e) => !e.inferred) : true;
  if (!hasVisible) return null;
  return (
    <div style={{ position: 'relative' }}>
      <div ref={containerRef} className="crossview-mini-cy" />
      {nodeTooltip && (
        <div className="crossview-node-tooltip" style={{ left: nodeTooltip.x, top: nodeTooltip.y }}>
          <strong>{nodeTooltip.label}</strong>
          <span>{nodeTooltip.name}</span>
        </div>
      )}
    </div>
  );
}

// ---- Comparison overlay: merge two species into one explorable graph ----

const COMP_CX = 400;
const COMP_CY = 300;
const COMP_RADIUS = 200;

const COMP_STYLES = [
  {
    selector: 'node[nodeType="center"]',
    style: {
      'background-color': '#3B8BD4', label: 'data(label)',
      'font-size': '14px', 'text-valign': 'center', 'text-halign': 'center',
      color: '#fff', 'text-outline-color': '#3B8BD4', 'text-outline-width': 2,
      width: 55, height: 55,
    },
  },
  {
    selector: 'node[nodeType="expanded"]',
    style: {
      'background-color': '#7E57C2', label: 'data(label)',
      'font-size': '12px', 'text-valign': 'center', 'text-halign': 'center',
      color: '#fff', 'text-outline-color': '#7E57C2', 'text-outline-width': 2,
      width: 45, height: 45,
    },
  },
  {
    selector: 'node[nodeType="shared"]',
    style: {
      'background-color': SHARED_COLOR, label: 'data(label)',
      'font-size': '10px', 'text-valign': 'bottom', 'text-margin-y': 4,
      color: '#eee', 'text-outline-color': '#222', 'text-outline-width': 1,
      width: 28, height: 28,
    },
  },
  {
    selector: 'node[nodeType="onlyA"]',
    style: {
      'background-color': SP_COLOR_A, 'background-opacity': 0.5,
      'border-width': 2, 'border-color': SP_COLOR_A, 'border-style': 'dashed',
      label: 'data(label)', 'font-size': '9px',
      'text-valign': 'bottom', 'text-margin-y': 4,
      color: SP_COLOR_A, 'text-outline-color': '#222', 'text-outline-width': 1,
      width: 22, height: 22,
    },
  },
  {
    selector: 'node[nodeType="onlyB"]',
    style: {
      'background-color': SP_COLOR_B, 'background-opacity': 0.5,
      'border-width': 2, 'border-color': SP_COLOR_B, 'border-style': 'dashed',
      label: 'data(label)', 'font-size': '9px',
      'text-valign': 'bottom', 'text-margin-y': 4,
      color: SP_COLOR_B, 'text-outline-color': '#222', 'text-outline-width': 1,
      width: 22, height: 22,
    },
  },
  {
    selector: 'edge[edgeType="shared"]',
    style: {
      'line-color': SHARED_COLOR, 'target-arrow-color': SHARED_COLOR,
      width: 2.5, 'target-arrow-shape': 'triangle',
      'curve-style': 'bezier', opacity: 0.85,
    },
  },
  {
    selector: 'edge[edgeType="onlyA"]',
    style: {
      'line-color': SP_COLOR_A, 'target-arrow-color': SP_COLOR_A,
      'line-style': 'dashed', width: 1.5, 'target-arrow-shape': 'triangle',
      'curve-style': 'bezier', opacity: 0.5,
    },
  },
  {
    selector: 'edge[edgeType="onlyB"]',
    style: {
      'line-color': SP_COLOR_B, 'target-arrow-color': SP_COLOR_B,
      'line-style': 'dashed', width: 1.5, 'target-arrow-shape': 'triangle',
      'curve-style': 'bezier', opacity: 0.5,
    },
  },
  {
    selector: 'edge[regulation="repression"]',
    style: { 'target-arrow-shape': 'tee' },
  },
];

function buildFamilyMaps(edges, curatedOnly) {
  const filtered = curatedOnly ? edges.filter((e) => !e.inferred) : edges;
  const map = new Map();
  for (const e of filtered) {
    const fam = (e.family || e.partner_symbol).toUpperCase();
    if (!map.has(fam)) map.set(fam, []);
    map.get(fam).push(e);
  }
  return map;
}

function pickLabel(edgesForFam) {
  return edgesForFam.reduce((best, e) => {
    const s = e.family || e.partner_symbol;
    return !best || s.length < best.length ? s : best;
  }, '');
}

const ComparisonNetwork = forwardRef(function ComparisonNetwork({ dataA, dataB, speciesA, speciesB, geneSymbol, curatedOnly, onSelect }, ref) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const expandedRef = useRef(new Set());
  const [expandCount, setExpandCount] = useState(0);
  const [compStats, setCompStats] = useState({ shared: 0, onlyA: 0, onlyB: 0 });
  const [nodeTooltip, setNodeTooltip] = useState(null);

  useImperativeHandle(ref, () => ({
    tapNode(label) {
      const cy = cyRef.current;
      if (!cy) return;
      const node = cy.nodes().filter((n) => n.data('label') === label).first();
      if (node.length) node.emit('tap');
    },
  }), []);

  const runLayout = useCallback((cy, animate = true) => {
    const n = cy.nodes().length;
    const repulsion = n > 60 ? 20000 : n > 30 ? 12000 : 8000;
    const edgeLen = n > 60 ? 180 : n > 30 ? 140 : 100;
    cy.layout({
      name: 'cose',
      animate,
      animationDuration: animate ? 600 : 0,
      nodeRepulsion: () => repulsion,
      idealEdgeLength: () => edgeLen,
      edgeElasticity: () => 80,
      gravity: n > 60 ? 0.15 : 0.25,
      numIter: 500,
      padding: 50,
      fit: true,
      nodeOverlap: 30,
      stop: () => cy.fit(undefined, 50),
    }).run();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const familiesA = buildFamilyMaps(dataA.edges || [], curatedOnly);
    const familiesB = buildFamilyMaps(dataB.edges || [], curatedOnly);

    const allFamilies = new Set([...familiesA.keys(), ...familiesB.keys()]);
    const famArray = [...allFamilies].sort((a, b) => {
      const s1 = (familiesA.has(a) ? 1 : 0) + (familiesB.has(a) ? 1 : 0);
      const s2 = (familiesA.has(b) ? 1 : 0) + (familiesB.has(b) ? 1 : 0);
      if (s1 !== s2) return s2 - s1;
      return a.localeCompare(b);
    });

    const elements = [];
    const centerId = '__center__';

    elements.push({
      data: { id: centerId, label: geneSymbol, nodeType: 'center', depth: 0 },
    });

    let shared = 0, onlyAc = 0, onlyBc = 0;

    famArray.forEach((fam) => {
      const inA = familiesA.has(fam);
      const inB = familiesB.has(fam);
      const isShared = inA && inB;

      if (isShared) shared++;
      else if (inA) onlyAc++;
      else onlyBc++;

      const edgesForFam = [...(familiesA.get(fam) || []), ...(familiesB.get(fam) || [])];
      const bestLabel = pickLabel(edgesForFam);

      const geneIdA = inA ? familiesA.get(fam)[0].partner_id : null;
      const geneIdB = inB ? familiesB.get(fam)[0].partner_id : null;

      const nodeId = `fam_${fam}`;
      const nodeType = isShared ? 'shared' : inA ? 'onlyA' : 'onlyB';

      const bestName = edgesForFam.find((e) => e.partner_name)?.partner_name || '';
      elements.push({
        data: {
          id: nodeId, label: truncLabel(bestLabel, 12), nodeType,
          fullName: bestName,
          family: fam, geneIdA, geneIdB, depth: 1, parent_node: centerId,
        },
      });

      const addEdge = (e, suffix, source) => {
        const src = e.direction === 'regulator' ? nodeId : centerId;
        const tgt = e.direction === 'regulator' ? centerId : nodeId;
        const edgeType = isShared ? 'shared' : (source === 'A' ? 'onlyA' : 'onlyB');
        elements.push({
          data: {
            id: `${src}->${tgt}_${suffix}`,
            source: src, target: tgt,
            regulation: e.regulation_type, edgeType,
          },
        });
      };

      if (inA) addEdge(familiesA.get(fam)[0], `A_${fam}`, 'A');
      if (inB && !isShared) addEdge(familiesB.get(fam)[0], `B_${fam}`, 'B');
    });

    setCompStats({ shared, onlyA: onlyAc, onlyB: onlyBc });

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: COMP_STYLES,
      layout: { name: 'preset', positions: () => ({ x: COMP_CX, y: COMP_CY }) },
      userZoomingEnabled: true, userPanningEnabled: true,
      boxSelectionEnabled: false, autoungrabify: false,
    });

    cyRef.current = cy;
    expandedRef.current = new Set();
    setExpandCount(0);

    // Animated initial layout
    requestAnimationFrame(() => runLayout(cy, true));

    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      const fullName = node.data('fullName');
      if (!fullName) return;
      const pos = evt.renderedPosition;
      setNodeTooltip({
        x: pos.x + 12,
        y: pos.y - 8,
        label: node.data('label'),
        name: fullName,
      });
    });
    cy.on('mouseout', 'node', () => setNodeTooltip(null));
    cy.on('pan zoom', () => setNodeTooltip(null));

    cy.on('tap', 'node', async (evt) => {
      const node = evt.target;
      const nodeId = node.id();
      if (nodeId === centerId) return;

      const expanded = expandedRef.current;

      if (expanded.has(nodeId)) {
        cy.elements(`[parent_node = "${nodeId}"]`).remove();
        expanded.delete(nodeId);
        node.data('nodeType', node.data('origType') || node.data('nodeType'));
        setExpandCount((c) => c - 1);
        runLayout(cy, true);
        return;
      }

      const geneIdA = node.data('geneIdA');
      const geneIdB = node.data('geneIdB');
      const fetchId = geneIdA || geneIdB;
      if (!fetchId) return;

      try {
        const res = await fetch(`/api/v1/crossview/${encodeURIComponent(fetchId)}?min_confidence=0.5&max_edges=15`);
        if (!res.ok) return;
        const crossData = await res.json();

        const spDataA = crossData.species?.[speciesA];
        const spDataB = crossData.species?.[speciesB];

        const newFamsA = buildFamilyMaps(spDataA?.edges || [], curatedOnly);
        const newFamsB = buildFamilyMaps(spDataB?.edges || [], curatedOnly);

        const newFamilies = new Set([...newFamsA.keys(), ...newFamsB.keys()]);
        const parentPos = node.position();
        const newEles = [];

        for (const fam of newFamilies) {
          const childId = `fam_${fam}`;

          if (cy.getElementById(childId).length > 0) {
            const edgeId = `${nodeId}->${childId}_exp`;
            if (cy.getElementById(edgeId).length === 0) {
              const inA = newFamsA.has(fam);
              const inB = newFamsB.has(fam);
              const isShared = inA && inB;
              const edgeType = isShared ? 'shared' : inA ? 'onlyA' : 'onlyB';
              const rep = (newFamsA.get(fam) || newFamsB.get(fam))[0];
              const src = rep.direction === 'regulator' ? childId : nodeId;
              const tgt = rep.direction === 'regulator' ? nodeId : childId;
              newEles.push({
                group: 'edges',
                data: {
                  id: edgeId, source: src, target: tgt,
                  regulation: rep.regulation_type, edgeType,
                  parent_node: nodeId,
                },
              });
            }
            continue;
          }

          const inA = newFamsA.has(fam);
          const inB = newFamsB.has(fam);
          const isShared = inA && inB;

          const edgesForFam = [...(newFamsA.get(fam) || []), ...(newFamsB.get(fam) || [])];
          const bestLabel = pickLabel(edgesForFam);

          const newGeneIdA = inA ? newFamsA.get(fam)[0].partner_id : null;
          const newGeneIdB = inB ? newFamsB.get(fam)[0].partner_id : null;
          const nodeType = isShared ? 'shared' : inA ? 'onlyA' : 'onlyB';

          const childName = edgesForFam.find((e) => e.partner_name)?.partner_name || '';
          newEles.push({
            group: 'nodes',
            data: {
              id: childId, label: truncLabel(bestLabel, 12), nodeType,
              fullName: childName,
              family: fam, geneIdA: newGeneIdA, geneIdB: newGeneIdB,
              depth: (node.data('depth') || 1) + 1, parent_node: nodeId,
            },
            position: {
              x: parentPos.x + (Math.random() - 0.5) * 60,
              y: parentPos.y + (Math.random() - 0.5) * 60,
            },
          });

          const rep = (newFamsA.get(fam) || newFamsB.get(fam))[0];
          const edgeType = isShared ? 'shared' : inA ? 'onlyA' : 'onlyB';
          const src = rep.direction === 'regulator' ? childId : nodeId;
          const tgt = rep.direction === 'regulator' ? nodeId : childId;

          newEles.push({
            group: 'edges',
            data: {
              id: `${src}->${tgt}_exp_${fam}`,
              source: src, target: tgt,
              regulation: rep.regulation_type, edgeType,
              parent_node: nodeId,
            },
          });
        }

        if (newEles.length > 0) {
          cy.add(newEles);
          expanded.add(nodeId);
          node.data('origType', node.data('nodeType'));
          node.data('nodeType', 'expanded');
          setExpandCount((c) => c + 1);
          runLayout(cy, true);
        }
      } catch (err) {
        console.error('Expand failed:', err);
      }
    });

    return () => { if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null; } };
  }, [dataA, dataB, speciesA, speciesB, geneSymbol, curatedOnly, runLayout]);

  const metaA = SPECIES_META[speciesA] || { label: speciesA };
  const metaB = SPECIES_META[speciesB] || { label: speciesB };

  return (
    <div className="comparison-panel">
      <div className="comparison-header">
        <h3>{metaA.label} vs {metaB.label}</h3>
        <div className="comparison-stats">
          <span className="comparison-stat" style={{ color: SHARED_COLOR }}>
            {compStats.shared} shared
          </span>
          <span className="comparison-stat" style={{ color: SP_COLOR_A }}>
            {compStats.onlyA} {metaA.label} only
          </span>
          <span className="comparison-stat" style={{ color: SP_COLOR_B }}>
            {compStats.onlyB} {metaB.label} only
          </span>
        </div>
      </div>
      <div className="comparison-legend">
        <span className="comparison-legend-item">
          <span className="comparison-legend-dot" style={{ background: SHARED_COLOR }} />
          Conserved in both
        </span>
        <span className="comparison-legend-item">
          <span className="comparison-legend-dot comparison-legend-dot-dashed" style={{ borderColor: SP_COLOR_A }} />
          {metaA.label} only
        </span>
        <span className="comparison-legend-item">
          <span className="comparison-legend-dot comparison-legend-dot-dashed" style={{ borderColor: SP_COLOR_B }} />
          {metaB.label} only
        </span>
        <span className="comparison-legend-item" style={{ color: '#B39DDB' }}>
          Click a gene to expand its network
        </span>
      </div>
      <div style={{ position: 'relative' }}>
        <div ref={containerRef} className="comparison-cy" />
        {nodeTooltip && (
          <div className="crossview-node-tooltip" style={{ left: nodeTooltip.x, top: nodeTooltip.y }}>
            <strong>{nodeTooltip.label}</strong>
            <span>{nodeTooltip.name}</span>
          </div>
        )}
      </div>
    </div>
  );
});

// ---- Main component ----

const DEMO_GENE_ID = 'TP53';

const DEMO_STEPS = [
  { caption: 'Loading TP53 — the most studied gene in biology', delay: 2500 },
  { caption: 'Selecting Human…', action: 'selectHuman', delay: 1500 },
  { caption: 'Selecting Mouse — let\'s compare', action: 'selectMouse', delay: 2500 },
  { caption: 'Green nodes are conserved regulators shared across both species', delay: 3000 },
  { caption: 'Expanding MYC — a key oncogene regulated by TP53…', action: 'expandMYC', delay: 3500 },
  { caption: 'Expanding E2F1 — a cell cycle regulator downstream of both TP53 and MYC…', action: 'expandE2F1', delay: 3500 },
  { caption: 'TP53 represses E2F1, E2F1 activates MYC, TP53 represses MYC — a regulatory circuit', delay: 4500 },
  { caption: 'One gene. Two species. Conserved regulatory circuits.', delay: 4000 },
];

export default function CrossSpeciesView({ selectedGene, onGeneSelect, filters }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [compareSpecies, setCompareSpecies] = useState([]);
  const [showInferred, setShowInferred] = useState(false);
  const [demoActive, setDemoActive] = useState(false);
  const [demoCaption, setDemoCaption] = useState('');
  const demoAbortRef = useRef(null);
  const comparisonRef = useRef(null);

  const geneId = selectedGene?.id || selectedGene;
  const curatedOnly = !showInferred;

  const fetchData = useCallback(async (id) => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/crossview/${encodeURIComponent(id)}?min_confidence=0.5&max_edges=20`);
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      setData(await res.json());
      setCompareSpecies([]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(geneId); }, [geneId, fetchData]);

  const stopDemo = useCallback(() => {
    if (demoAbortRef.current) demoAbortRef.current.abort();
    setDemoActive(false);
    setDemoCaption('');
  }, []);

  const startDemo = useCallback(async () => {
    stopDemo();
    const controller = new AbortController();
    demoAbortRef.current = controller;
    setDemoActive(true);

    const wait = (ms) => new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, ms);
      controller.signal.addEventListener('abort', () => { clearTimeout(timer); reject(new Error('aborted')); });
    });

    try {
      setShowInferred(false);
      setCompareSpecies([]);
      if (geneId !== DEMO_GENE_ID) {
        await fetchData(DEMO_GENE_ID);
        await wait(500);
      }

      for (const step of DEMO_STEPS) {
        if (controller.signal.aborted) break;
        setDemoCaption(step.caption);

        if (step.action === 'selectHuman') {
          setCompareSpecies(['human']);
        } else if (step.action === 'selectMouse') {
          setCompareSpecies(['human', 'mouse']);
        } else if (step.action === 'expandMYC') {
          await wait(800);
          comparisonRef.current?.tapNode('MYC');
        } else if (step.action === 'expandE2F1') {
          await wait(800);
          comparisonRef.current?.tapNode('E2F1');
        }

        await wait(step.delay);
      }

      setDemoCaption('');
      setDemoActive(false);
    } catch {
      // aborted
    }
  }, [geneId, fetchData, stopDemo]);

  const slotMap = useMemo(() => {
    if (!data?.species) return {};
    return buildGlobalSlotMap(data.species, curatedOnly);
  }, [data, curatedOnly]);

  const handleCardClick = (sp) => {
    const d = data?.species?.[sp];
    const hasEdges = curatedOnly
      ? d?.edges?.some((e) => !e.inferred)
      : d?.edges?.length > 0;
    if (!hasEdges) return;

    setCompareSpecies((prev) => {
      if (prev.includes(sp)) return prev.filter((s) => s !== sp);
      if (prev.length < 2) return [...prev, sp];
      return [prev[1], sp];
    });
  };

  if (!geneId) {
    return (
      <div className="crossview-container">
        <div className="crossview-empty">
          <h2>Cross-species regulatory view</h2>
          <p>Search for a gene to see its regulatory network across all species in Darwin.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="crossview-container">
        <div className="crossview-empty">Loading cross-species data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="crossview-container">
        <div className="crossview-empty crossview-error">Error: {error}</div>
      </div>
    );
  }

  if (!data) return null;

  const { gene, species, summary } = data;

  const orderedSpecies = Object.keys(species).sort((a, b) => {
    const da = species[a], db = species[b];
    const countEdges = (d) => {
      if (!d.edges?.length) return 0;
      return curatedOnly ? d.edges.filter((e) => !e.inferred).length : d.edges.length;
    };
    const ea = countEdges(da), eb = countEdges(db);
    if (ea !== eb) return eb - ea;
    const fa = da.found ? 1 : 0, fb = db.found ? 1 : 0;
    return fb - fa;
  });

  const curatedSpeciesCount = Object.values(species).filter(
    (d) => d.edges?.some((e) => !e.inferred)
  ).length;

  const inComparison = compareSpecies.length === 2;

  return (
    <div className="crossview-container">
      <div className="crossview-header">
        <div className="crossview-title">
          <h2>{gene.symbol}</h2>
          <span className="crossview-subtitle">
            {gene.name} &middot; {SPECIES_META[gene.species]?.latin || gene.species}
            {gene.is_tf && <span className="crossview-badge">TF</span>}
          </span>
        </div>
        <div className="crossview-stats">
          <div className="crossview-stat">
            <span className="crossview-stat-value">
              {curatedOnly ? curatedSpeciesCount : summary.n_species_with_data}
            </span>
            <span className="crossview-stat-label">species with data</span>
          </div>
          <div className="crossview-stat">
            <span className="crossview-stat-value">{summary.total_curated_edges}</span>
            <span className="crossview-stat-label">curated edges</span>
          </div>
          {showInferred && (
            <div className="crossview-stat">
              <span className="crossview-stat-value">{summary.total_inferred_edges}</span>
              <span className="crossview-stat-label">inferred edges</span>
            </div>
          )}
          {summary.conserved_partners?.length > 0 && (
            <div className="crossview-stat">
              <span className="crossview-stat-value">{summary.conserved_partners.length}</span>
              <span className="crossview-stat-label">conserved partners</span>
            </div>
          )}
        </div>
        {demoActive ? (
          <button className="crossview-demo-btn crossview-demo-stop" onClick={stopDemo}>
            Stop Demo
          </button>
        ) : (
          <button className="crossview-demo-btn" onClick={startDemo}>
            Play Demo
          </button>
        )}
      </div>

      {demoCaption && (
        <div className="crossview-demo-caption">
          <span>{demoCaption}</span>
        </div>
      )}

      <div className="crossview-legend">
        <span className="crossview-legend-item">
          <span className="crossview-legend-dot crossview-legend-curated" /> Curated (measured)
        </span>
        {showInferred && (
          <span className="crossview-legend-item">
            <span className="crossview-legend-dot crossview-legend-inferred" /> Inferred (predicted)
          </span>
        )}
        <span className="crossview-legend-item">
          <span className="crossview-legend-line crossview-legend-activation" /> Activation
        </span>
        <span className="crossview-legend-item">
          <span className="crossview-legend-line crossview-legend-repression" /> Repression
        </span>
        <label className="crossview-toggle">
          <input
            type="checkbox"
            checked={showInferred}
            onChange={(e) => setShowInferred(e.target.checked)}
          />
          Show inferred edges
        </label>
      </div>

      {!inComparison && (
        <div className="crossview-hint">
          {compareSpecies.length === 0
            ? 'Click two species cards to compare their networks'
            : `Click a second species to compare with ${SPECIES_META[compareSpecies[0]]?.label || compareSpecies[0]}`}
        </div>
      )}

      {inComparison && (
        <div className="comparison-wrapper">
          <button
            className="comparison-close"
            onClick={() => setCompareSpecies([])}
          >
            Close comparison
          </button>
          <ComparisonNetwork
            ref={comparisonRef}
            dataA={species[compareSpecies[0]]}
            dataB={species[compareSpecies[1]]}
            speciesA={compareSpecies[0]}
            speciesB={compareSpecies[1]}
            geneSymbol={gene.symbol}
            curatedOnly={curatedOnly}
            onSelect={onGeneSelect}
          />
        </div>
      )}

      <div className={inComparison ? 'crossview-grid-collapsed' : 'crossview-grid'}>
        {orderedSpecies.map((sp) => {
          const d = species[sp];
          const meta = SPECIES_META[sp] || { label: sp, latin: sp, kingdom: 'unknown' };
          const isHome = d.is_home;
          const curatedEdges = d.edges?.filter((e) => !e.inferred) || [];
          const hasVisibleData = curatedOnly
            ? curatedEdges.length > 0
            : d.found && d.edges?.length > 0;
          const isSelected = compareSpecies.includes(sp);
          const selectIdx = compareSpecies.indexOf(sp);

          return (
            <div
              key={sp}
              className={`crossview-card ${isHome ? 'crossview-card-home' : ''} ${isSelected ? 'crossview-card-compare' : ''} ${!d.found ? 'crossview-card-empty' : ''}`}
              style={isSelected ? { borderColor: selectIdx === 0 ? SP_COLOR_A : SP_COLOR_B } : undefined}
              onClick={() => handleCardClick(sp)}
            >
              <div className="crossview-card-header">
                <div>
                  <span className="crossview-card-species">{meta.label}</span>
                  <span className="crossview-card-latin">{meta.latin}</span>
                </div>
                {d.found && (
                  <div className="crossview-card-symbol">
                    {d.symbol}
                    {d.ortholog_type && (
                      <span className="crossview-card-orthotype">{d.ortholog_type}</span>
                    )}
                  </div>
                )}
              </div>

              {hasVisibleData ? (
                <>
                  <MiniNetwork
                    data={d}
                    centerSymbol={d.symbol}
                    onSelect={onGeneSelect}
                    slotMap={slotMap}
                    curatedOnly={curatedOnly}
                  />
                  <div className="crossview-card-footer">
                    {curatedEdges.length > 0 && (
                      <span className="crossview-edge-count crossview-curated-count">
                        {d.n_curated} curated
                      </span>
                    )}
                    {showInferred && d.n_inferred > 0 && (
                      <span className="crossview-edge-count crossview-inferred-count">
                        {d.n_inferred} inferred
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <div className="crossview-card-nodata">
                  {!d.found
                    ? 'No ortholog identified'
                    : curatedOnly && d.n_inferred > 0
                      ? `${d.n_inferred} inferred edges only`
                      : 'No edges above threshold'}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
