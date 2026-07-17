import React, { useState, useCallback, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import ViewTabs from './components/ViewTabs';
import NetworkVisualization from './components/NetworkVisualization';
import GeneDetailPanel from './components/GeneDetailPanel';
import ComparisonView from './components/ComparisonView';
import GenomeComparisonView from './components/GenomeComparisonView';
import InterventionDesigner from './components/InterventionDesigner';
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
    direction: 'both' // 'regulators', 'targets', 'both'
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
            min_confidence: filters.minConfidence
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
        <ViewTabs viewMode={viewMode} onViewChange={setViewMode} />

        <div className="content-area">
          {error && (
            <div className="error-banner">
              <span>{error}</span>
              <button onClick={() => setError(null)}>×</button>
            </div>
          )}

          {viewMode === 'genome' ? (
            <GenomeComparisonView />
          ) : !selectedGene ? (
            <div className="empty-state">
              <div className="empty-icon">🧬</div>
              <h2>Gene Regulatory Network Atlas</h2>
              <p>Search for a gene to get started</p>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                21 species • 591K genes • 6.7M interactions
              </p>
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
    </div>
  );
}
