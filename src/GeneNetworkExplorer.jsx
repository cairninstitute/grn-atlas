import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import ViewTabs from './components/ViewTabs';
import { COLLECTIONS } from './collections';
import AppNavigation from './components/app/AppNavigation';
import ArtifactDrawer from './components/artifacts/ArtifactDrawer';
import ResearchContextBar from './components/context/ResearchContextBar';
import { ResearchSessionProvider, useResearchSession } from './state/ResearchSessionContext';
import './styles/GeneNetworkExplorer.css';
import './styles/AppShell.css';

const NetworkVisualization = lazy(() => import('./components/NetworkVisualization'));
const GeneDetailPanel = lazy(() => import('./components/GeneDetailPanel'));
const ComparisonView = lazy(() => import('./components/ComparisonView'));
const GenomeComparisonView = lazy(() => import('./components/GenomeComparisonView'));
const GeneSetPanel = lazy(() => import('./components/GeneSetPanel'));
const DsRnaPanel = lazy(() => import('./components/DsRnaPanel'));
const OrganismView = lazy(() => import('./components/OrganismView'));
const InterventionDesigner = lazy(() => import('./components/InterventionDesigner'));
const AnalysisView = lazy(() => import('./components/AnalysisView'));
const PathwayView = lazy(() => import('./components/PathwayView'));
const HomeWorkspace = lazy(() => import('./components/home/HomeWorkspace'));
const DatasetWorkflow = lazy(() => import('./components/workflows/DatasetWorkflow'));
const DecisionWorkflow = lazy(() => import('./components/workflows/DecisionWorkflow'));
const GeneWorkflow = lazy(() => import('./components/workflows/GeneWorkflow'));

const SPECIES_TO_KINGDOM = {
  human: 'Animalia',
  mouse: 'Animalia',
  arabidopsis: 'Plantae',
  tomato: 'Plantae',
  petunia: 'Plantae',
  rice: 'Plantae',
};

const LEGACY_VIEW_IDS = new Set(['network', 'organism', 'pathways', 'comparison', 'genome', 'design', 'analysis']);
const ADVANCED_TABS = [
  { id: 'network', label: 'Explorer', icon: '🔗' },
  { id: 'organism', label: 'Organism', icon: '🌐' },
  { id: 'pathways', label: 'Paths', icon: '🛤️' },
  { id: 'comparison', label: 'Orthology', icon: '⚖️' },
  { id: 'genome', label: 'Genome', icon: '🧬' },
  { id: 'design', label: 'Design', icon: '✏️' },
  { id: 'analysis', label: 'Lab', icon: '🔬' },
];

function ExplorerInner() {
  const { dispatch } = useResearchSession();
  const [selectedGene, setSelectedGene] = useState(null);
  const [viewMode, setViewMode] = useState('home');
  const [advancedView, setAdvancedView] = useState('network');
  const [filters, setFilters] = useState({
    kingdom: ['Animalia'],
    species: ['human'],
    regulationType: ['activation', 'repression'],
    minConfidence: 0.6,
    maxDepth: 3,
    direction: 'both',
    includeInferred: true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [networkData, setNetworkData] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const cyInstanceRef = useRef(null);
  const [pathwaySource, setPathwaySource] = useState(null);
  const [pathwayTarget, setPathwayTarget] = useState(null);
  const [showGeneSet, setShowGeneSet] = useState(false);
  const [showDsRna, setShowDsRna] = useState(false);
  const [showArtifacts, setShowArtifacts] = useState(false);
  const [dsRnaTarget, setDsRnaTarget] = useState(null);
  const [dsRnaCompareTarget, setDsRnaCompareTarget] = useState(null);
  const [dsRnaSet, setDsRnaSet] = useState([]);
  const [workflowDsRnaSeed, setWorkflowDsRnaSeed] = useState(null);
  const [collection, setCollection] = useState(null);
  const [linkCopied, setLinkCopied] = useState(false);

  const renderWithSuspense = useCallback((node, fallback = 'Loading workspace…') => (
    <Suspense fallback={<div className="empty-state">{fallback}</div>}>
      {node}
    </Suspense>
  ), []);

  const handleCyInit = useCallback((cy) => {
    cyInstanceRef.current = cy;
  }, []);

  const loadNeighborhood = useCallback(async (geneId, activeFilters = filters) => {
    const networkResponse = await fetch(`/api/v1/pathways/neighborhood/${geneId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        max_depth: activeFilters.maxDepth,
        direction: activeFilters.direction,
        regulation_type: activeFilters.regulationType,
        min_confidence: activeFilters.minConfidence,
        include_inferred: activeFilters.includeInferred,
      }),
    });
    setNetworkData(await networkResponse.json());
  }, [filters]);

  const syncSpeciesContext = useCallback((nextSpecies) => {
    if (!nextSpecies) return;
    const normalized = nextSpecies.trim().toLowerCase();
    const nextKingdom = SPECIES_TO_KINGDOM[normalized];
    setFilters((prev) => {
      if (prev.species?.[0] === normalized && (!nextKingdom || prev.kingdom?.[0] === nextKingdom)) {
        return prev;
      }
      return {
        ...prev,
        species: [normalized],
        kingdom: nextKingdom ? [nextKingdom] : prev.kingdom,
      };
    });
    dispatch({ type: 'SET_SPECIES', species: normalized });
  }, [dispatch]);

  const handlePrimaryModeChange = useCallback((mode) => {
    setViewMode(mode === 'advanced' ? 'advanced' : mode);
  }, []);

  const handleNavigate = useCallback((target) => {
    if (!target) return;
    if (target.startsWith('advanced:')) {
      setAdvancedView(target.split(':')[1] || 'network');
      setViewMode('advanced');
      return;
    }
    if (LEGACY_VIEW_IDS.has(target)) {
      setAdvancedView(target);
      setViewMode('advanced');
      return;
    }
    setViewMode(target);
  }, []);

  const focusGeneByRecord = useCallback(async (geneLike) => {
    if (!geneLike) return;
    const geneId = geneLike.gene_id || geneLike.id;
    if (!geneId) return;
    setLoading(true);
    setError(null);
    try {
      const geneResponse = await fetch(`/api/v1/genes/${geneId}`);
      const geneData = await geneResponse.json();
      if (!geneData?.id) {
        setError('Gene not found');
        return;
      }
      setSelectedGene(geneData);
      syncSpeciesContext(geneData.species);
      dispatch({ type: 'SET_FOCUS_GENE', gene: geneData });
      await loadNeighborhood(geneData.id, filters);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [dispatch, filters, syncSpeciesContext]);

  const handleGeneSearch = useCallback(async (symbol) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/v1/genes/symbol/${symbol}`);
      const data = await response.json();
      if (!data?.id) {
        setError('Gene not found');
        return;
      }
      setSelectedGene(data);
      syncSpeciesContext(data.species);
      dispatch({ type: 'SET_FOCUS_GENE', gene: data });
      await loadNeighborhood(data.id, filters);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [dispatch, filters, loadNeighborhood, syncSpeciesContext]);

  useEffect(() => {
    if (!selectedGene?.id) return;
    loadNeighborhood(selectedGene.id, filters).catch((err) => setError(err.message));
  }, [filters, loadNeighborhood, selectedGene]);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const requestedView = p.get('view');
    if (requestedView) {
      if (LEGACY_VIEW_IDS.has(requestedView)) {
        setViewMode('advanced');
        setAdvancedView(requestedView);
      } else {
        setViewMode(requestedView);
      }
    }
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

  useEffect(() => {
    const p = new URLSearchParams();
    if (selectedGene) p.set('gene', selectedGene.symbol);
    p.set('view', viewMode === 'advanced' ? advancedView : viewMode);
    if (filters.species?.length) p.set('species', filters.species.join(','));
    p.set('reg', filters.regulationType.join(','));
    p.set('conf', String(filters.minConfidence));
    p.set('depth', String(filters.maxDepth));
    p.set('dir', filters.direction);
    p.set('inferred', filters.includeInferred ? '1' : '0');
    window.history.replaceState(null, '', `?${p.toString()}`);
  }, [selectedGene, viewMode, advancedView, filters]);

  useEffect(() => {
    const sessionSpecies = selectedGene?.species || filters?.species?.[0] || null;
    dispatch({ type: 'SET_SPECIES', species: sessionSpecies });
  }, [dispatch, filters, selectedGene]);

  const openCollection = useCallback((col) => {
    setCollection(col);
    setShowGeneSet(true);
  }, []);

  const analysisGeneIds = useMemo(() => {
    if (!selectedGene) return [];
    const ids = new Set([selectedGene.id]);
    (networkData?.regulators || []).forEach((r) => ids.add(r.id));
    (networkData?.targets || []).forEach((t) => ids.add(t.id));
    return [...ids];
  }, [selectedGene, networkData]);

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
      setAdvancedView('pathways');
      setViewMode('advanced');
    } else if (action === 'path-to') {
      setPathwaySource(null);
      setPathwayTarget(geneSymbol);
      setAdvancedView('pathways');
      setViewMode('advanced');
    }
  }, [handleGeneSearch]);

  const handleFilterChange = useCallback((newFilters) => {
    setFilters(newFilters);
  }, []);

  const handleSpeciesChange = useCallback((nextSpecies) => {
    if (!nextSpecies) return;
    const normalized = nextSpecies.trim().toLowerCase();
    const nextKingdom = SPECIES_TO_KINGDOM[normalized];
    setFilters((prev) => ({
      ...prev,
      species: [normalized],
      kingdom: nextKingdom ? [nextKingdom] : prev.kingdom,
    }));
    dispatch({ type: 'SET_SPECIES', species: normalized });
    if (selectedGene?.species && selectedGene.species !== normalized) {
      setSelectedGene(null);
      setNetworkData(null);
      setExpandedNodes(new Set());
      setPathwaySource(null);
      setPathwayTarget(null);
      dispatch({ type: 'SET_FOCUS_GENE', gene: null });
    }
  }, [dispatch, selectedGene]);

  const handleNodeExpand = useCallback((nodeId) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const handleWorkflowSessionSync = useCallback((payload) => {
    dispatch({ type: 'SYNC_WORKFLOW', payload });
  }, [dispatch]);

  const sharedWorkflowProps = {
    selectedGene,
    networkData,
    filters,
    onNavigate: handleNavigate,
    onSpeciesChange: handleSpeciesChange,
    onFocusGeneChange: focusGeneByRecord,
    onOpenGeneSetAnalysis: () => setShowGeneSet(true),
    onDsRnaSeedChange: setWorkflowDsRnaSeed,
    onNetworkDepthChange: (depth) => setFilters((prev) => ({ ...prev, maxDepth: depth })),
    onSessionSync: handleWorkflowSessionSync,
    onOpenDsRna: (payload) => {
      setDsRnaTarget(payload?.target || selectedGene);
      setDsRnaCompareTarget(payload?.compareTarget || null);
      setDsRnaSet(payload?.geneSet || analysisGeneIds);
      setShowDsRna(true);
    },
  };

  const renderAdvancedView = () => {
    if (advancedView === 'analysis') {
      return renderWithSuspense(
        <AnalysisView
          gene={selectedGene}
          networkData={networkData}
          filters={filters}
          onNodeAction={handleNodeAction}
          onDepthChange={(depth) => setFilters((prev) => ({ ...prev, maxDepth: depth }))}
        />,
        'Loading analysis lab…',
      );
    }
    if (advancedView === 'genome') return renderWithSuspense(<GenomeComparisonView />, 'Loading genome view…');
    if (advancedView === 'organism') {
      return renderWithSuspense(
        <OrganismView
          initialSpecies={filters?.species?.[0]}
          onSpeciesChange={handleSpeciesChange}
          onSelectGene={(symbol) => { handleGeneSearch(symbol); setAdvancedView('network'); }}
        />,
        'Loading organism view…',
      );
    }

    if (!selectedGene) {
      return (
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
              <button key={ex.symbol} className="example-gene-btn" onClick={() => handleGeneSearch(ex.symbol)}>
                <strong>{ex.symbol}</strong>
                <span>{ex.note}</span>
              </button>
            ))}
          </div>
          <div className="collections">
            <div className="collections-label">Curated collections</div>
            <div className="collection-btns">
              {COLLECTIONS.map((col) => (
                <button key={col.id} className="collection-btn" onClick={() => openCollection(col)} title={col.description}>
                  {col.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      );
    }

    if (advancedView === 'network') {
      return renderWithSuspense(
        <>
          <NetworkVisualization
            gene={selectedGene}
            data={networkData}
            filters={filters}
            expandedNodes={expandedNodes}
            onNodeExpand={handleNodeExpand}
            onCyInit={handleCyInit}
            onNodeAction={handleNodeAction}
            onDepthChange={(depth) => setFilters((prev) => ({ ...prev, maxDepth: depth }))}
          />
          <GeneDetailPanel
            gene={selectedGene}
            data={networkData}
            onDesignDsRna={() => {
              setDsRnaTarget(selectedGene);
              setDsRnaCompareTarget(null);
              setDsRnaSet(analysisGeneIds);
              setShowDsRna(true);
            }}
          />
        </>,
        'Loading explorer…',
      );
    }

    if (advancedView === 'pathways') {
      return renderWithSuspense(
        <PathwayView
          gene={selectedGene}
          filters={filters}
          onCyInit={handleCyInit}
          onNodeAction={handleNodeAction}
          initialSource={pathwaySource}
          initialTarget={pathwayTarget}
        />,
        'Loading path view…',
      );
    }

    if (advancedView === 'comparison') {
      return renderWithSuspense(
        <ComparisonView gene={selectedGene} currentSpecies={filters.species[0]} />,
        'Loading orthology view…',
      );
    }

    if (advancedView === 'design') {
      return renderWithSuspense(
        <InterventionDesigner gene={selectedGene} networkData={networkData} />,
        'Loading design tools…',
      );
    }

    return <div className="empty-state">Unknown advanced view.</div>;
  };

  return (
    <div className="grn-explorer">
      <Sidebar
        filters={filters}
        onFilterChange={handleFilterChange}
        onGeneSearch={handleGeneSearch}
        loading={loading}
        selectedGene={selectedGene}
      />

      <div className="main-content">
        {selectedGene && (
          <Toolbar gene={selectedGene} stats={networkData?.stats} cyRef={cyInstanceRef} />
        )}

        <AppNavigation mode={viewMode} onChange={handlePrimaryModeChange} />
        <ResearchContextBar />

        <div className="tabs-row">
          {viewMode === 'advanced' && (
            <ViewTabs viewMode={advancedView} onViewChange={setAdvancedView} tabs={ADVANCED_TABS} />
          )}
          <div className="tabs-actions">
            <button className="copy-link-btn" onClick={() => setShowArtifacts(true)} title="Open the current workflow artifacts">
              🗂 Artifacts
            </button>
            <button className="copy-link-btn" onClick={() => setShowGeneSet(true)} title="GO enrichment and network metrics for a gene set">
              📊 Analyze
            </button>
            <button
              className="copy-link-btn"
              onClick={() => {
                setDsRnaTarget(workflowDsRnaSeed?.target || selectedGene || null);
                setDsRnaCompareTarget(workflowDsRnaSeed?.compareTarget || null);
                setDsRnaSet(workflowDsRnaSeed?.geneSet?.length ? workflowDsRnaSeed.geneSet : analysisGeneIds);
                setShowDsRna(true);
              }}
              title="Design a dsRNA / predict RNAi silencing + off-targets"
            >
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

          {viewMode === 'home' && renderWithSuspense(<HomeWorkspace onSelectMode={handlePrimaryModeChange} />, 'Loading home…')}
          {viewMode === 'gene' && renderWithSuspense(<GeneWorkflow {...sharedWorkflowProps} />, 'Loading gene workflow…')}
          {viewMode === 'dataset' && renderWithSuspense(<DatasetWorkflow {...sharedWorkflowProps} />, 'Loading unified workflow…')}
          {viewMode === 'phenotype' && renderWithSuspense(<DatasetWorkflow {...sharedWorkflowProps} />, 'Loading unified workflow…')}
          {viewMode === 'decision' && renderWithSuspense(<DecisionWorkflow {...sharedWorkflowProps} />, 'Loading decision workflow…')}
          {viewMode === 'advanced' && renderAdvancedView()}
        </div>
      </div>

      <ArtifactDrawer
        open={showArtifacts}
        onClose={() => setShowArtifacts(false)}
        onNavigate={(target) => {
          setShowArtifacts(false);
          handleNavigate(target);
        }}
      />

      <Suspense fallback={null}>
        <DsRnaPanel
          open={showDsRna}
          onClose={() => setShowDsRna(false)}
          initialTarget={dsRnaTarget}
          initialCompareTarget={dsRnaCompareTarget}
          initialSpecies={dsRnaTarget?.species || filters?.species?.[0]}
          initialSet={dsRnaSet}
          onFocusGeneChange={focusGeneByRecord}
        />

        <GeneSetPanel
          open={showGeneSet}
          onClose={() => { setShowGeneSet(false); setCollection(null); }}
          initialGeneIds={collection ? collection.geneIds : analysisGeneIds}
          species={collection ? collection.species : selectedGene?.species}
          includeInferred={filters.includeInferred}
        />
      </Suspense>
    </div>
  );
}

export default function GeneNetworkExplorer() {
  return (
    <ResearchSessionProvider>
      <ExplorerInner />
    </ResearchSessionProvider>
  );
}
