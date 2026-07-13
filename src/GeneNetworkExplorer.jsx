import React, { useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import ViewTabs from './components/ViewTabs';
import NetworkVisualization from './components/NetworkVisualization';
import GeneDetailPanel from './components/GeneDetailPanel';
import ComparisonView from './components/ComparisonView';
import GenomeComparisonView from './components/GenomeComparisonView';
import GeneSetPanel from './components/GeneSetPanel';
import DsRnaPanel from './components/DsRnaPanel';
import OrganismView from './components/OrganismView';
import { COLLECTIONS } from './collections';
import InterventionDesigner from './components/InterventionDesigner';
import AnalysisView from './components/AnalysisView';
import PathwayView from './components/PathwayView';
import './styles/GeneNetworkExplorer.css';

export default function GeneNetworkExplorer() {
  const [selectedGene, setSelectedGene] = useState(null);
  const [viewMode, setViewMode] = useState('network');
  const [filters, setFilters] = useState({
    kingdom: ['Animalia'],
    species: ['human'],
    regulationType: ['activation', 'repression'],
    minConfidence: 0.6,
    maxDepth: 3,
    direction: 'both', // 'regulators', 'targets', 'both'
    includeInferred: true
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [networkData, setNetworkData] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const cyInstanceRef = useRef(null);
  const [pathwaySource, setPathwaySource] = useState(null);
  const [pathwayTarget, setPathwayTarget] = useState(null);

  const handleCyInit = useCallback((cy) => {
    cyInstanceRef.current = cy;
  }, []);

  // Search for a gene
  const handleGeneSearch = useCallback(async (symbol) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/v1/genes/symbol/${symbol}`);
      const data = await response.json();
      
      if (data && data.id) {
        setSelectedGene(data);
        // Fetch network data
        const networkResponse = await fetch(`/api/v1/pathways/neighborhood/${data.id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            max_depth: filters.maxDepth,
            direction: filters.direction,
            regulation_type: filters.regulationType,
            min_confidence: filters.minConfidence,
            include_inferred: filters.includeInferred
          })
        });
        const networkJson = await networkResponse.json();
        setNetworkData(networkJson);
      } else {
        setError('Gene not found');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // Restore state from a shared permalink on first load.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get('view')) setViewMode(p.get('view'));
    const fp = {};
    if (p.get('species')) fp.species = p.get('species').split(',');
    if (p.get('reg')) fp.regulationType = p.get('reg').split(',');
    if (p.get('conf')) fp.minConfidence = parseFloat(p.get('conf'));
    if (p.get('depth')) fp.maxDepth = parseInt(p.get('depth'), 10);
    if (p.get('dir')) fp.direction = p.get('dir');
    if (p.get('inferred')) fp.includeInferred = p.get('inferred') === '1';
    if (Object.keys(fp).length) setFilters((f) => ({ ...f, ...fp }));
    if (p.get('gene')) handleGeneSearch(p.get('gene'));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the URL in sync so the current view is always shareable.
  useEffect(() => {
    const p = new URLSearchParams();
    if (selectedGene) p.set('gene', selectedGene.symbol);
    p.set('view', viewMode);
    if (filters.species?.length) p.set('species', filters.species.join(','));
    p.set('reg', filters.regulationType.join(','));
    p.set('conf', String(filters.minConfidence));
    p.set('depth', String(filters.maxDepth));
    p.set('dir', filters.direction);
    p.set('inferred', filters.includeInferred ? '1' : '0');
    window.history.replaceState(null, '', `?${p.toString()}`);
  }, [selectedGene, viewMode, filters]);

  const [showGeneSet, setShowGeneSet] = useState(false);
  const [showDsRna, setShowDsRna] = useState(false);
  const [dsRnaTarget, setDsRnaTarget] = useState(null);
  const [collection, setCollection] = useState(null);
  const openCollection = useCallback((col) => {
    setCollection(col);
    setShowGeneSet(true);
  }, []);
  const analysisGeneIds = React.useMemo(() => {
    if (!selectedGene) return [];
    const ids = new Set([selectedGene.id]);
    (networkData?.regulators || []).forEach((r) => ids.add(r.id));
    (networkData?.targets || []).forEach((t) => ids.add(t.id));
    return [...ids];
  }, [selectedGene, networkData]);

  const [linkCopied, setLinkCopied] = useState(false);
  const copyLink = useCallback(() => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 1500);
    });
  }, []);

  const handleNodeAction = useCallback((geneId, geneSymbol, action) => {
    if (action === 'view-neighborhood') {
      handleGeneSearch(geneSymbol);
    } else if (action === 'path-from') {
      setPathwaySource(geneSymbol);
      setPathwayTarget(null);
      setViewMode('pathways');
    } else if (action === 'path-to') {
      setPathwaySource(null);
      setPathwayTarget(geneSymbol);
      setViewMode('pathways');
    }
  }, [handleGeneSearch]);

  // Update filters
  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
  }, []);

  // Handle node expansion in network
  const handleNodeExpand = useCallback((nodeId) => {
    const newExpandedNodes = new Set(expandedNodes);
    if (newExpandedNodes.has(nodeId)) {
      newExpandedNodes.delete(nodeId);
    } else {
      newExpandedNodes.add(nodeId);
    }
    setExpandedNodes(newExpandedNodes);
  }, [expandedNodes]);

  return (
    <div className="grn-explorer">
      <Sidebar 
        filters={filters}
        onFilterChange={handleFilterChange}
        onGeneSearch={handleGeneSearch}
        loading={loading}
      />
      
      <div className="main-content">
        {selectedGene && (
          <Toolbar gene={selectedGene} stats={networkData?.stats} cyRef={cyInstanceRef} />
        )}
        <div className="tabs-row">
          <ViewTabs viewMode={viewMode} onViewChange={setViewMode} />
          <div className="tabs-actions">
            <button className="copy-link-btn" onClick={() => setShowGeneSet(true)}
              title="GO enrichment and network metrics for a gene set">
              📊 Analyze
            </button>
            <button className="copy-link-btn" onClick={() => { setDsRnaTarget(null); setShowDsRna(true); }}
              title="Design a dsRNA / predict RNAi silencing + off-targets">
              🧬 dsRNA
            </button>
            <button className="copy-link-btn" onClick={copyLink} title="Copy a shareable link to this view">
              {linkCopied ? '✓ Copied' : '🔗 Copy link'}
            </button>
          </div>
        </div>

        <div className="content-area">
          {error && (
            <div className="error-banner">
              <span>{error}</span>
              <button onClick={() => setError(null)}>×</button>
            </div>
          )}

          {viewMode === 'analysis' ? (
            <AnalysisView />
          ) : viewMode === 'genome' ? (
            <GenomeComparisonView />
          ) : viewMode === 'organism' ? (
            <OrganismView onSelectGene={(symbol) => { handleGeneSearch(symbol); setViewMode('network'); }} />
          ) : !selectedGene ? (
            <div className="empty-state">
              <div className="empty-icon">🧬</div>
              <h2>Gene Regulatory Network Atlas</h2>
              <p>Search for a gene, or try an example:</p>
              <div className="example-genes">
                {[
                  { symbol: 'TP53', note: 'human tumor suppressor' },
                  { symbol: 'MYC', note: 'human oncogene' },
                  { symbol: 'LHY', note: 'Arabidopsis clock' },
                  { symbol: 'LFY', note: 'plant flowering' },
                ].map((ex) => (
                  <button key={ex.symbol} className="example-gene-btn"
                    onClick={() => handleGeneSearch(ex.symbol)}>
                    <strong>{ex.symbol}</strong>
                    <span>{ex.note}</span>
                  </button>
                ))}
              </div>
              <p className="empty-hint">
                Explore regulators and targets, trace pathways, compare chromosomes across
                species, and design interventions. Some plant edges are <em>inferred</em> from
                Arabidopsis via orthology (shown dashed and labeled) — see “Data &amp; citations”.
              </p>
              <div className="collections">
                <div className="collections-label">Curated collections</div>
                <div className="collection-btns">
                  {COLLECTIONS.map((col) => (
                    <button key={col.id} className="collection-btn"
                      onClick={() => openCollection(col)} title={col.description}>
                      {col.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              {viewMode === 'network' && (
                <>
                  <NetworkVisualization
                    gene={selectedGene}
                    data={networkData}
                    filters={filters}
                    expandedNodes={expandedNodes}
                    onNodeExpand={handleNodeExpand}
                    onCyInit={handleCyInit}
                    onNodeAction={handleNodeAction}
                  />
                  <GeneDetailPanel
                    gene={selectedGene}
                    data={networkData}
                    onDesignDsRna={() => { setDsRnaTarget(selectedGene); setShowDsRna(true); }}
                  />
                </>
              )}

              {viewMode === 'pathways' && (
                <PathwayView
                  gene={selectedGene}
                  filters={filters}
                  onCyInit={handleCyInit}
                  onNodeAction={handleNodeAction}
                  initialSource={pathwaySource}
                  initialTarget={pathwayTarget}
                />
              )}

              {viewMode === 'comparison' && (
                <ComparisonView
                  gene={selectedGene}
                  currentSpecies={filters.species[0]}
                />
              )}

              {viewMode === 'design' && (
                <InterventionDesigner
                  gene={selectedGene}
                  networkData={networkData}
                />
              )}
            </>
          )}
        </div>
      </div>

      <DsRnaPanel open={showDsRna} onClose={() => setShowDsRna(false)}
        initialTarget={dsRnaTarget?.symbol} initialSpecies={dsRnaTarget?.species} />

      <GeneSetPanel
        open={showGeneSet}
        onClose={() => { setShowGeneSet(false); setCollection(null); }}
        initialGeneIds={collection ? collection.geneIds : analysisGeneIds}
        species={collection ? collection.species : selectedGene?.species}
        includeInferred={filters.includeInferred}
      />
    </div>
  );
}
