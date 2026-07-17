import React, { useState, useEffect } from 'react';
import PathwayGraph from './PathwayGraph';
import '../styles/PathwayView.css';

export default function PathwayView({ gene, filters, onCyInit, onNodeAction, initialSource, initialTarget }) {
  const [sourceGene, setSourceGene] = useState('');
  const [sourceSuggestions, setSourceSuggestions] = useState([]);
  const [resolvedSource, setResolvedSource] = useState(null);
  const [targetGene, setTargetGene] = useState('');
  const [targetSuggestions, setTargetSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [maxDepth, setMaxDepth] = useState(3);
  const [pathLimit, setPathLimit] = useState(20);

  // Accumulated searches: each entry is { id, sourceSymbol, targetSymbol, paths, visible }
  const [searches, setSearches] = useState([]);
  const [selectedPath, setSelectedPath] = useState(null); // { searchIdx, pathIdx } or null for all

  // Seed source gene from the main selected gene
  useEffect(() => {
    if (gene) {
      setSourceGene(gene.symbol);
      setResolvedSource(gene);
    }
  }, [gene]);

  // Handle initialSource/initialTarget from node actions
  useEffect(() => {
    if (initialSource) {
      setSourceGene(initialSource);
      setResolvedSource(null);
    }
  }, [initialSource]);

  useEffect(() => {
    if (initialTarget) {
      setTargetGene(initialTarget);
    }
  }, [initialTarget]);

  const speciesParam = filters.species?.length === 1 ? `&species=${filters.species[0]}` : '';

  // Source gene suggestions
  useEffect(() => {
    if (sourceGene.length < 2) { setSourceSuggestions([]); return; }
    const timer = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/v1/genes/search?q=${encodeURIComponent(sourceGene)}&limit=5${speciesParam}`);
        const data = await resp.json();
        setSourceSuggestions(data.results || []);
      } catch (err) { console.error(err); }
    }, 300);
    return () => clearTimeout(timer);
  }, [sourceGene, speciesParam]);

  // Target gene suggestions
  useEffect(() => {
    if (targetGene.length < 2) { setTargetSuggestions([]); return; }
    const timer = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/v1/genes/search?q=${encodeURIComponent(targetGene)}&limit=5${speciesParam}`);
        const data = await resp.json();
        setTargetSuggestions(data.results || []);
      } catch (err) { console.error(err); }
    }, 300);
    return () => clearTimeout(timer);
  }, [targetGene, speciesParam]);

  const handleSelectSource = (sug) => {
    setSourceGene(sug.symbol);
    setResolvedSource(sug);
    setSourceSuggestions([]);
  };

  const handleSelectTarget = (symbol) => {
    setTargetGene(symbol);
    setTargetSuggestions([]);
  };

  const handleFindPaths = async () => {
    if (!targetGene) { setError('Please select a target gene'); return; }

    // Resolve source if user typed but didn't pick from suggestions
    let src = resolvedSource;
    if (!src || src.symbol.toLowerCase() !== sourceGene.toLowerCase()) {
      try {
        const resp = await fetch(`/api/v1/genes/search?q=${encodeURIComponent(sourceGene)}&limit=1`);
        const data = await resp.json();
        if (data.results?.length > 0) {
          src = data.results[0];
          setResolvedSource(src);
        } else {
          setError(`Gene "${sourceGene}" not found`);
          return;
        }
      } catch (err) { setError(err.message); return; }
    }

    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/pathways/pathfinding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_gene_id: src.id,
          target_symbol: targetGene,
          max_depth: maxDepth,
          limit: pathLimit,
          min_confidence: filters.minConfidence
        })
      });

      const data = await response.json();
      const newPaths = data.paths || [];
      if (newPaths.length === 0) {
        setError(`No paths found from ${src.symbol} to ${targetGene}`);
      } else {
        const newSearch = {
          id: Date.now(),
          sourceSymbol: src.symbol,
          sourceGene: src,
          targetSymbol: targetGene,
          paths: newPaths,
          visible: true
        };
        setSearches(prev => [...prev, newSearch]);
        setSelectedPath(null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleSearch = (idx) => {
    setSearches(prev => prev.map((s, i) => i === idx ? { ...s, visible: !s.visible } : s));
    setSelectedPath(null);
  };

  const removeSearch = (idx) => {
    setSearches(prev => prev.filter((_, i) => i !== idx));
    setSelectedPath(null);
  };

  const clearAll = () => {
    setSearches([]);
    setSelectedPath(null);
  };

  // Collect all visible paths for the graph
  const visibleSearches = searches.filter(s => s.visible);
  const allVisiblePaths = visibleSearches.flatMap(s => s.paths);

  // Always show all visible paths; pass selected path for highlighting
  let highlightPath = null;
  if (selectedPath !== null) {
    const search = searches[selectedPath.searchIdx];
    if (search) highlightPath = search.paths[selectedPath.pathIdx];
  }

  // Collect all unique source/target symbols for legend
  const sourceSymbols = [...new Set(visibleSearches.map(s => s.sourceSymbol))];
  const targetSymbols = [...new Set(visibleSearches.map(s => s.targetSymbol))];

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleFindPaths();
  };

  const totalPaths = searches.reduce((n, s) => n + s.paths.length, 0);

  return (
    <div className="pathway-view">
      {/* Search Panel */}
      <div className="pathway-search-panel">
        <div className="search-container">
          <div className="search-row">
            <div className="search-field">
              <label>From</label>
              <div className="target-field">
                <input
                  type="text"
                  className="target-input"
                  placeholder="Source gene..."
                  value={sourceGene}
                  onChange={(e) => setSourceGene(e.target.value)}
                  onKeyPress={handleKeyPress}
                />
                {sourceSuggestions.length > 0 && (
                  <div className="suggestions">
                    {sourceSuggestions.map((sug) => (
                      <div key={sug.id} className="suggestion" onClick={() => handleSelectSource(sug)}>
                        <span className="sug-symbol">{sug.symbol}</span>
                        <span className="species-badge">{sug.species}</span>
                        <span className="sug-name">{sug.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <button className="swap-button" onClick={() => {
              const tmpGene = sourceGene;
              const tmpResolved = resolvedSource;
              setSourceGene(targetGene);
              setTargetGene(tmpGene);
              setResolvedSource(null);
            }} title="Swap source and target">⇄</button>

            <div className="search-field flex-grow">
              <label>To</label>
              <div className="target-field">
                <input
                  type="text"
                  className="target-input"
                  placeholder="Target gene..."
                  value={targetGene}
                  onChange={(e) => setTargetGene(e.target.value)}
                  onKeyPress={handleKeyPress}
                />
                {targetSuggestions.length > 0 && (
                  <div className="suggestions">
                    {targetSuggestions.map((sug) => (
                      <div key={sug.id} className="suggestion" onClick={() => handleSelectTarget(sug.symbol)}>
                        <span className="sug-symbol">{sug.symbol}</span>
                        <span className="species-badge">{sug.species}</span>
                        <span className="sug-name">{sug.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="search-options">
            <div className="option">
              <label>Max depth</label>
              <input type="range" min="1" max="5" value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value, 10))} className="slider" />
              <span className="option-value">{maxDepth} hops</span>
            </div>
            <div className="option">
              <label>Max paths</label>
              <input type="range" min="5" max="100" step="5" value={pathLimit}
                onChange={(e) => setPathLimit(parseInt(e.target.value, 10))} className="slider" />
              <span className="option-value">{pathLimit}</span>
            </div>
            <button className="search-button" onClick={handleFindPaths} disabled={loading || !targetGene || !sourceGene}>
              {loading ? '⟳ Searching...' : searches.length > 0 ? '+ Add paths' : 'Find paths'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="error-banner"><span>{error}</span></div>}

      {/* Results */}
      {searches.length > 0 ? (
        <div className="pathway-results">
          {/* Search chips */}
          <div className="searches-bar">
            <div className="searches-list">
              {searches.map((s, idx) => (
                <div key={s.id} className={`search-chip ${s.visible ? 'search-chip-visible' : 'search-chip-hidden'}`}>
                  <button className="chip-toggle" onClick={() => toggleSearch(idx)}
                    title={s.visible ? 'Hide paths' : 'Show paths'}>
                    {s.visible ? '◉' : '○'}
                  </button>
                  <span className="chip-label" onClick={() => toggleSearch(idx)}>
                    {s.sourceSymbol} → {s.targetSymbol}
                    <span className="chip-count">{s.paths.length}</span>
                  </span>
                  <button className="chip-remove" onClick={() => removeSearch(idx)} title="Remove">×</button>
                </div>
              ))}
            </div>
            <button className="clear-all-btn" onClick={clearAll}>Clear all</button>
          </div>

          {/* Toggle bar for individual paths */}
          <div className="view-toggle">
            <button className={`toggle-btn ${selectedPath === null ? 'active' : ''}`}
              onClick={() => setSelectedPath(null)}>
              All ({allVisiblePaths.length})
            </button>
            {visibleSearches.map((s, sIdx) => {
              const realIdx = searches.indexOf(s);
              return s.paths.map((_, pIdx) => (
                <button key={`${realIdx}-${pIdx}`}
                  className={`toggle-btn ${selectedPath?.searchIdx === realIdx && selectedPath?.pathIdx === pIdx ? 'active' : ''}`}
                  onClick={() => setSelectedPath(
                    selectedPath?.searchIdx === realIdx && selectedPath?.pathIdx === pIdx
                      ? null
                      : { searchIdx: realIdx, pathIdx: pIdx }
                  )}>
                  {s.sourceSymbol[0]}→{s.targetSymbol[0]} #{pIdx + 1}
                </button>
              ));
            })}
          </div>

          <PathwayGraph
            paths={allVisiblePaths}
            highlightPath={highlightPath}
            sourceGene={null}
            targetSymbol={null}
            sourceIds={visibleSearches.map(s => s.sourceGene?.id).filter(Boolean)}
            targetSymbols={targetSymbols}
            onCyInit={onCyInit}
            onNodeAction={onNodeAction}
          />

          {/* Path cards grouped by search */}
          <div className="paths-list">
            {searches.map((s, sIdx) => s.visible && (
              <div key={s.id} className="search-group">
                <div className="search-group-header">
                  {s.sourceSymbol} → {s.targetSymbol}
                  <span className="search-group-count">{s.paths.length} path{s.paths.length !== 1 ? 's' : ''}</span>
                </div>
                {s.paths.map((path, pIdx) => (
                  <PathCard key={pIdx} path={path} index={pIdx + 1}
                    selected={selectedPath?.searchIdx === sIdx && selectedPath?.pathIdx === pIdx}
                    onClick={() => setSelectedPath(
                      selectedPath?.searchIdx === sIdx && selectedPath?.pathIdx === pIdx
                        ? null : { searchIdx: sIdx, pathIdx: pIdx }
                    )}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-state-pathway">
          <div className="empty-icon">🛤️</div>
          <p>Search for paths between two genes</p>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Add multiple searches to build up a connected network
          </p>
        </div>
      )}
    </div>
  );
}

function PathCard({ path, index, selected, onClick }) {
  const [expanded, setExpanded] = useState(false);

  const genes = path.genes || [];
  const hops = genes.length - 1;
  const avgConfidence = path.confidences ?
    path.confidences.reduce((a, b) => a + b, 0) / path.confidences.length : 0;

  return (
    <div className={`path-card ${selected ? 'path-card-selected' : ''}`}>
      <div className="path-header" onClick={() => setExpanded(!expanded)}>
        <div className="path-number" onClick={(e) => { e.stopPropagation(); onClick(); }}>#{index}</div>

        <div className="path-summary">
          <div className="path-genes">
            {genes.slice(0, 5).map((gene, i) => (
              <React.Fragment key={i}>
                <span className="path-gene">{gene.symbol}</span>
                {i < genes.length - 1 && <span className="path-arrow">→</span>}
              </React.Fragment>
            ))}
            {genes.length > 5 && <span className="path-ellipsis">... ({genes.length - 5} more)</span>}
          </div>
        </div>

        <div className="path-stats">
          <div className="stat">
            <span className="stat-label">Hops</span>
            <span className="stat-value">{hops}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Confidence</span>
            <span className="stat-value">{(avgConfidence * 100).toFixed(0)}%</span>
          </div>
        </div>

        <div className="expand-icon">{expanded ? '▼' : '▶'}</div>
      </div>

      {expanded && (
        <div className="path-details">
          <div className="genes-table">
            {genes.map((gene, i) => (
              <div key={i} className="gene-row">
                <div className="gene-index">{i + 1}.</div>
                <div className="gene-cell">
                  <span className="gene-symbol">{gene.symbol}</span>
                  <span className="gene-name">{gene.name}</span>
                </div>

                {i < genes.length - 1 && (
                  <>
                    <div className="interaction-cell">
                      <span className={`regulation-type ${path.regulation_types?.[i]}`}>
                        {path.regulation_types?.[i] === 'activation' ?
                          '✓ Activates' :
                          path.regulation_types?.[i] === 'repression' ?
                          '✗ Represses' :
                          path.regulation_types?.[i] === 'regulation' ?
                          '● Regulates' :
                          '? Unknown'
                        }
                      </span>
                    </div>
                    <div className="confidence-cell">
                      <span className="confidence-value">
                        {((path.confidences?.[i] || 0) * 100).toFixed(0)}%
                      </span>
                      <div className="confidence-bar">
                        <div className="confidence-fill" style={{
                          width: `${(path.confidences?.[i] || 0) * 100}%`
                        }}></div>
                      </div>
                    </div>
                    <div className="source-cell">
                      <span className="source">
                        {path.sources?.[i]?.join(', ') || 'Unknown'}
                      </span>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>

          <div className="path-summary-stats">
            <div className="summary-box">
              <span className="summary-label">Path confidence</span>
              <span className="summary-value">
                {(path.overall_confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="summary-box">
              <span className="summary-label">Sources</span>
              <span className="summary-value">
                {new Set([...(path.sources?.flat() || [])]).size}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
