import React, { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import ViewTabs from './components/ViewTabs';
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
const ToolboxView = lazy(() => import('./components/ToolboxView'));
const PathwayView = lazy(() => import('./components/PathwayView'));
const CrossSpeciesView = lazy(() => import('./components/CrossSpeciesView'));
const RegulatoryWeatherMap = lazy(() => import('./components/RegulatoryWeatherMap'));
const FeedbackControlView = lazy(() => import('./components/FeedbackControlView'));
const CloneLabWorkspace = lazy(() => import('./components/clonelab/CloneLabWorkspace'));
const CrisprVsDsrnaPanel = lazy(() => import('./components/CrisprVsDsrnaPanel'));
const HomeWorkspace = lazy(() => import('./components/home/HomeWorkspace'));
const ControlAtlasDemo = lazy(() => import('./components/demo/ControlAtlasDemo'));

const SPECIES_TO_KINGDOM = {
  human: 'Animalia',
  mouse: 'Animalia',
  arabidopsis: 'Plantae',
  tomato: 'Plantae',
  petunia: 'Plantae',
  rice: 'Plantae',
};

const EXPLORE_TABS = [
  { id: 'network', label: 'Gene network', requiresGene: true, description: 'Regulators and targets around one focus gene' },
  { id: 'feedback', label: 'Control systems', description: 'Feedback circuits and connected control cores' },
  { id: 'organism', label: 'Species overview', description: 'Coverage and high-level structure for one species' },
  { id: 'crossview', label: 'Cross-species', requiresGene: true, description: 'Compare a focus gene across species' },
  { id: 'pathways', label: 'Regulatory paths', requiresGene: true, description: 'Trace signed routes between genes' },
  { id: 'comparison', label: 'Orthologs', requiresGene: true, description: 'Inspect corresponding genes in other species' },
  { id: 'genome', label: 'Genome context', description: 'Compare genome-scale regulatory context' },
  { id: 'weathermap', label: 'TF landscape', description: 'Survey transcription-factor programs' },
];

const DESIGN_TABS = [
  { id: 'intervention', label: 'Choose an intervention', requiresGene: true, description: 'Plan how to alter a candidate gene or network' },
  { id: 'crispr-compare', label: 'Compare CRISPR / RNAi', requiresGene: true, description: 'Compare intervention modes for a target' },
  { id: 'clonelab', label: 'Build & verify DNA', description: 'Design a construct and diagnostic assay in CloneLab' },
];

const VIEW_GUIDANCE = {
  network: ['Gene regulatory neighborhood', 'Inspect who regulates the focus gene, what it regulates, and how strongly each edge is supported.'],
  feedback: ['Feedback and control systems', 'Discover signed circuits, connected cores, and larger control architectures across a species.'],
  organism: ['Species overview', 'Start with coverage, network composition, and prominent regulators for one organism.'],
  crossview: ['Cross-species comparison', 'Ask whether a regulatory role or neighborhood is conserved across organisms.'],
  pathways: ['Regulatory paths', 'Trace plausible signed routes from an upstream regulator to a downstream target.'],
  comparison: ['Ortholog mapping', 'Find corresponding genes and assess how safely conclusions transfer across species.'],
  genome: ['Genome context', 'Compare regulatory organization at genome scale.'],
  weathermap: ['Transcription-factor landscape', 'Survey broad regulator activity and coverage patterns.'],
  intervention: ['Intervention planning', 'Translate the current network hypothesis into a candidate perturbation strategy.'],
  'crispr-compare': ['CRISPR or RNAi?', 'Compare editing and silencing strategies for the current target.'],
  clonelab: ['CloneLab', 'Build a sequence-defined construct and choose an assay that distinguishes expected outcomes.'],
  toolbox: ['Analysis tools', 'Use focused analyses when you already know the method or output you need.'],
};

const EXPLORE_VIEW_IDS = new Set(EXPLORE_TABS.map(t => t.id));
const DESIGN_VIEW_IDS = new Set(DESIGN_TABS.map(t => t.id));

function getInitialRoute() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get('view');
  if (EXPLORE_VIEW_IDS.has(requested)) return { mode: 'explore', subView: requested };
  if (DESIGN_VIEW_IDS.has(requested)) return { mode: 'design', subView: requested };
  if (requested === 'toolbox') return { mode: 'toolbox', subView: 'network' };
  if (requested === 'control-demo') return { mode: 'demo', subView: 'network' };
  if (params.get('gene')) return { mode: 'explore', subView: 'network' };
  return { mode: 'home', subView: 'network' };
}

function ExplorerInner() {
  const { dispatch } = useResearchSession();
  const initialRoute = useMemo(getInitialRoute, []);
  const [selectedGene, setSelectedGene] = useState(null);
  const [viewMode, setViewMode] = useState(initialRoute.mode);
  const [subView, setSubView] = useState(initialRoute.subView);
  const [filters, setFilters] = useState({
    kingdom: [],
    species: [],
    regulationType: ['activation', 'repression', 'unknown'],
    minConfidence: 0.4,
    maxDepth: 1,
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
  const [chromeCollapsed, setChromeCollapsed] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [disambiguationChoices, setDisambiguationChoices] = useState(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

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
        regulation_type: activeFilters.regulationType.map(t => t === 'unknown' ? 'regulation' : t),
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
    setViewMode(mode);
    if (mode === 'explore' && !EXPLORE_VIEW_IDS.has(subView)) setSubView('network');
    else if (mode === 'design' && !DESIGN_VIEW_IDS.has(subView)) setSubView('intervention');
    setMobileSidebarOpen(false);
  }, [subView]);

  const handleNavigate = useCallback((target) => {
    if (!target) return;
    if (target === 'home') {
      setViewMode('home');
    } else if (EXPLORE_VIEW_IDS.has(target)) {
      setSubView(target);
      setViewMode('explore');
    } else if (DESIGN_VIEW_IDS.has(target)) {
      setSubView(target);
      setViewMode('design');
    } else if (target === 'toolbox') {
      setViewMode('toolbox');
    } else if (target === 'control-demo') {
      setViewMode('demo');
    } else {
      setViewMode('explore');
    }
    setMobileSidebarOpen(false);
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

  const handleGeneSearch = useCallback(async (symbol, geneObj) => {
    setLoading(true);
    setError(null);
    setDisambiguationChoices(null);
    try {
      let data = geneObj;
      if (!data?.id) {
        const response = await fetch(`/api/v1/genes/symbol/${encodeURIComponent(symbol)}`);
        data = await response.json();
      }
      if (data?.ambiguous && data.matches?.length > 1) {
        setDisambiguationChoices(data.matches);
        setLoading(false);
        return;
      }
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
    p.set('view', ['home', 'toolbox', 'demo'].includes(viewMode) ? (viewMode === 'demo' ? 'control-demo' : viewMode) : subView);
    if (filters.species?.length) p.set('species', filters.species.join(','));
    p.set('reg', filters.regulationType.join(','));
    p.set('conf', String(filters.minConfidence));
    p.set('depth', String(filters.maxDepth));
    p.set('dir', filters.direction);
    p.set('inferred', filters.includeInferred ? '1' : '0');
    window.history.replaceState(null, '', `?${p.toString()}`);
  }, [selectedGene, viewMode, subView, filters]);

  useEffect(() => {
    const sessionSpecies = selectedGene?.species || filters?.species?.[0] || null;
    dispatch({ type: 'SET_SPECIES', species: sessionSpecies });
  }, [dispatch, filters, selectedGene]);

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
      setSubView('pathways');
      setViewMode('explore');
    } else if (action === 'path-to') {
      setPathwaySource(null);
      setPathwayTarget(geneSymbol);
      setSubView('pathways');
      setViewMode('explore');
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

  const renderEmptyState = (title = 'Choose a gene to begin') => (
    <div className="empty-state gene-required-state">
      <span className="empty-state-kicker">Focus gene required</span>
      <h2>{title}</h2>
      <p>Use gene search to load a regulatory neighborhood, or start with a documented example.</p>
      <button
        className="mobile-filter-trigger empty-search-trigger"
        onClick={() => {
          setViewMode('explore');
          setSubView('network');
          setMobileSidebarOpen(true);
        }}
      >
        Find a gene
      </button>
      <div className="example-genes">
        {[
          { symbol: 'AN2', note: 'petunia pigmentation' },
          { symbol: 'LHY', note: 'Arabidopsis clock' },
          { symbol: 'TP53', note: 'human tumor suppressor' },
        ].map((ex) => (
          <button key={ex.symbol} className="example-gene-btn" onClick={() => handleGeneSearch(ex.symbol)}>
            <strong>{ex.symbol}</strong>
            <span>{ex.note}</span>
          </button>
        ))}
      </div>
    </div>
  );

  const renderExploreView = () => {
    if (subView === 'organism') {
      return renderWithSuspense(
        <OrganismView
          initialSpecies={filters?.species?.[0]}
          onSpeciesChange={handleSpeciesChange}
          onSelectGene={(symbol) => { handleGeneSearch(symbol); setSubView('network'); }}
        />,
        'Loading organism view…',
      );
    }
    if (subView === 'feedback') {
      return renderWithSuspense(
        <FeedbackControlView
          initialSpecies={filters?.species?.[0] || 'arabidopsis'}
          onSpeciesChange={handleSpeciesChange}
          onSelectGene={(symbol) => { handleGeneSearch(symbol); setSubView('network'); }}
        />,
        'Loading feedback architecture…',
      );
    }
    if (subView === 'weathermap') {
      return renderWithSuspense(<RegulatoryWeatherMap />, 'Loading regulatory map…');
    }
    if (subView === 'genome') {
      return renderWithSuspense(<GenomeComparisonView />, 'Loading genome view…');
    }

    if (!selectedGene) return renderEmptyState();

    if (subView === 'network') {
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
    if (subView === 'pathways') {
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
    if (subView === 'crossview') {
      return renderWithSuspense(
        <CrossSpeciesView selectedGene={selectedGene} onGeneSelect={(id) => focusGeneByRecord({ id })} filters={filters} />,
        'Loading cross-species view…',
      );
    }
    if (subView === 'comparison') {
      return renderWithSuspense(
        <ComparisonView gene={selectedGene} currentSpecies={filters.species[0]} />,
        'Loading orthology view…',
      );
    }

    return renderEmptyState();
  };

  const renderDesignView = () => {
    if (subView === 'clonelab') {
      return renderWithSuspense(<CloneLabWorkspace />, 'Loading CloneLab…');
    }
    if (subView === 'crispr-compare') {
      if (!selectedGene) return renderEmptyState('Select a target before comparing CRISPR and RNAi');
      return renderWithSuspense(
        <CrisprVsDsrnaPanel currentGene={selectedGene} currentSpecies={filters?.species?.[0] || ''} />,
        'Loading CRISPR comparison…',
      );
    }
    if (!selectedGene) return renderEmptyState('Select a target before planning an intervention');
    return renderWithSuspense(
      <InterventionDesigner gene={selectedGene} networkData={networkData} />,
      'Loading intervention designer…',
    );
  };

  const currentSubTabs = viewMode === 'explore' ? EXPLORE_TABS : viewMode === 'design' ? DESIGN_TABS : null;
  const currentGuidance = VIEW_GUIDANCE[viewMode === 'toolbox' ? 'toolbox' : subView];
  const sidebarRelevant = viewMode === 'explore' && ['network', 'crossview', 'pathways', 'comparison'].includes(subView);

  return (
    <div className={`grn-explorer${sidebarRelevant ? '' : ' no-sidebar'}`}>
      {sidebarRelevant && (
        <>
          <Sidebar
            filters={filters}
            onFilterChange={handleFilterChange}
            onGeneSearch={handleGeneSearch}
            loading={loading}
            selectedGene={selectedGene}
            mobileOpen={mobileSidebarOpen}
            onMobileClose={() => setMobileSidebarOpen(false)}
          />
          {mobileSidebarOpen && <button className="sidebar-mobile-backdrop" onClick={() => setMobileSidebarOpen(false)} aria-label="Close gene search" />}
        </>
      )}

      <div className="main-content">
        {!chromeCollapsed && (
          <>
            <AppNavigation mode={viewMode === 'demo' ? 'home' : viewMode} onChange={handlePrimaryModeChange} />
            {!['home', 'demo'].includes(viewMode) && <ResearchContextBar />}
            {selectedGene && viewMode === 'explore' && subView === 'network' && (
              <Toolbar gene={selectedGene} stats={networkData?.stats} cyRef={cyInstanceRef} />
            )}
          </>
        )}

        {!['home', 'demo'].includes(viewMode) && (
          <div className="workspace-chrome">
            <div className="tabs-row">
              {sidebarRelevant && (
                <button className="mobile-filter-trigger" onClick={() => setMobileSidebarOpen(true)}>
                  Find gene / filters
                </button>
              )}
              {currentSubTabs && (
                <ViewTabs viewMode={subView} onViewChange={setSubView} tabs={currentSubTabs} hasGene={!!selectedGene} />
              )}
              <details className="workspace-actions">
                <summary>Actions</summary>
                <div className="workspace-actions-menu">
                  <button onClick={() => setShowGeneSet(true)} title="GO enrichment and network metrics for a gene set">Analyze a gene set</button>
                  <button
                    onClick={() => {
                      setDsRnaTarget(selectedGene || null);
                      setDsRnaCompareTarget(null);
                      setDsRnaSet(analysisGeneIds);
                      setShowDsRna(true);
                    }}
                    title="Design a dsRNA / predict RNAi silencing + off-targets"
                  >Design dsRNA</button>
                  <button onClick={() => setShowArtifacts(true)} title="Open the current workflow artifacts">View generated outputs</button>
                  <button onClick={copyLink} title="Copy a shareable link to this view">{linkCopied ? 'Link copied' : 'Copy link to this view'}</button>
                  <button onClick={() => setChromeCollapsed((c) => !c)}>{chromeCollapsed ? 'Show application header' : 'Focus on workspace'}</button>
                </div>
              </details>
            </div>
            {currentGuidance && (
              <div className="workspace-guide">
                <div>
                  <span>{viewMode === 'design' ? 'Design' : viewMode === 'toolbox' ? 'Tools' : 'Explore'}</span>
                  <strong>{currentGuidance[0]}</strong>
                  <p>{currentGuidance[1]}</p>
                </div>
                {sidebarRelevant && selectedGene && (
                  <button onClick={() => setMobileSidebarOpen(true)} className="workspace-focus-chip">
                    Focus: {selectedGene.label || selectedGene.symbol || selectedGene.id}
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        <div className="content-area">
          {error && (
            <div className="error-banner">
              <span>{error}</span>
              <button onClick={() => setError(null)}>×</button>
            </div>
          )}

          {disambiguationChoices && (
            <div className="disambiguation-panel">
              <div className="disambiguation-header">
                <span>Multiple genes match — which one did you mean?</span>
                <button onClick={() => setDisambiguationChoices(null)}>×</button>
              </div>
              <div className="disambiguation-grid">
                {disambiguationChoices.map((g) => (
                  <button
                    key={g.id}
                    className="disambiguation-choice"
                    onClick={() => {
                      setDisambiguationChoices(null);
                      handleGeneSearch(g.symbol, g);
                    }}
                  >
                    <strong>{g.label || g.symbol}</strong>
                    <span className="disambiguation-species">{g.species}</span>
                    <span className="disambiguation-name">{g.name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {viewMode === 'home' && renderWithSuspense(
            <HomeWorkspace
              onNavigate={handleNavigate}
              onGeneSearch={handleGeneSearch}
              onOpenGeneSet={() => setShowGeneSet(true)}
            />,
            'Loading Darwin…',
          )}
          {viewMode === 'demo' && renderWithSuspense(
            <ControlAtlasDemo
              onBack={() => handleNavigate('home')}
              onOpenControl={(species) => {
                handleSpeciesChange(species);
                handleNavigate('feedback');
              }}
            />,
            'Loading control-system demonstration…',
          )}
          {viewMode === 'explore' && renderExploreView()}
          {viewMode === 'design' && renderDesignView()}
          {viewMode === 'toolbox' && renderWithSuspense(
            <ToolboxView
              gene={selectedGene}
              networkData={networkData}
              filters={filters}
              onNodeAction={handleNodeAction}
              onDepthChange={(depth) => setFilters((prev) => ({ ...prev, maxDepth: depth }))}
            />,
            'Loading toolbox…',
          )}
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
          onClose={() => setShowGeneSet(false)}
          initialGeneIds={analysisGeneIds}
          species={selectedGene?.species}
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
