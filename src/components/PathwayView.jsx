import React, { useState, useEffect } from 'react';
import PathwayGraph from './PathwayGraph';
import '../styles/PathwayView.css';

export default function PathwayView({ gene, filters }) {
  const [targetGene, setTargetGene] = useState('');
  const [targetSuggestions, setTargetSuggestions] = useState([]);
  const [paths, setPaths] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [maxDepth, setMaxDepth] = useState(3);
  const [pathLimit, setPathLimit] = useState(20);

  // Fetch target gene suggestions
  useEffect(() => {
    if (targetGene.length < 2) {
      setTargetSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/v1/genes/search?q=${encodeURIComponent(targetGene)}&limit=5`);
        const data = await response.json();
        setTargetSuggestions(data.results || []);
      } catch (err) {
        console.error('Search error:', err);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [targetGene]);

  // Find paths
  const handleFindPaths = async () => {
    if (!targetGene) {
      setError('Please select a target gene');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/pathways/pathfinding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_gene_id: gene.id,
          target_symbol: targetGene,
          max_depth: maxDepth,
          limit: pathLimit,
          min_confidence: filters.minConfidence
        })
      });

      const data = await response.json();
      setPaths(data.paths || []);
      if (data.paths?.length === 0) {
        setError(`No paths found from ${gene.symbol} to ${targetGene}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTarget = (geneSymbol) => {
    setTargetGene(geneSymbol);
    setTargetSuggestions([]);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleFindPaths();
    }
  };

  return (
    <div className="pathway-view">
      {/* Search Panel */}
      <div className="pathway-search-panel">
        <div className="search-container">
          <div className="search-row">
            <div className="search-field">
              <label>From</label>
              <div className="source-field">
                <span className="source-gene">{gene.symbol}</span>
              </div>
            </div>

            <div className="search-arrow">→</div>

            <div className="search-field flex-grow">
              <label>To</label>
              <div className="target-field">
                <input
                  type="text"
                  className="target-input"
                  placeholder="Search target gene..."
                  value={targetGene}
                  onChange={(e) => setTargetGene(e.target.value)}
                  onKeyPress={handleKeyPress}
                />
                {targetSuggestions.length > 0 && (
                  <div className="suggestions">
                    {targetSuggestions.map((sug) => (
                      <div 
                        key={sug.id}
                        className="suggestion"
                        onClick={() => handleSelectTarget(sug.symbol)}
                      >
                        <span className="sug-symbol">{sug.symbol}</span>
                        <span className="sug-name">{sug.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Options */}
          <div className="search-options">
            <div className="option">
              <label>Max depth</label>
              <input
                type="range"
                min="1"
                max="5"
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value, 10))}
                className="slider"
              />
              <span className="option-value">{maxDepth} hops</span>
            </div>

            <div className="option">
              <label>Max paths</label>
              <input
                type="range"
                min="5"
                max="100"
                step="5"
                value={pathLimit}
                onChange={(e) => setPathLimit(parseInt(e.target.value, 10))}
                className="slider"
              />
              <span className="option-value">{pathLimit}</span>
            </div>

            <button 
              className="search-button"
              onClick={handleFindPaths}
              disabled={loading || !targetGene}
            >
              {loading ? '⟳ Searching...' : '🔍 Find paths'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
        </div>
      )}

      {/* Results */}
      {paths && paths.length > 0 ? (
        <div className="pathway-results">
          <div className="results-header">
            <h3>Found {paths.length} path{paths.length !== 1 ? 's' : ''}</h3>
            <p>Showing regulatory routes from {gene.symbol} to {targetGene}</p>
          </div>

          <PathwayGraph paths={paths} sourceGene={gene} targetSymbol={targetGene} />

          <div className="paths-list">
            {paths.map((path, idx) => (
              <PathCard key={idx} path={path} index={idx + 1} />
            ))}
          </div>
        </div>
      ) : paths !== null && paths.length === 0 ? (
        <div className="no-results">
          <div className="no-results-icon">🔍</div>
          <p>No regulatory paths found</p>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Try adjusting depth or confidence filters
          </p>
        </div>
      ) : (
        <div className="empty-state-pathway">
          <div className="empty-icon">🛤️</div>
          <p>Search for paths between two genes</p>
        </div>
      )}
    </div>
  );
}

// Individual path card
function PathCard({ path, index }) {
  const [expanded, setExpanded] = useState(false);

  const genes = path.genes || [];
  const hops = genes.length - 1;
  const minConfidence = Math.min(...(path.confidences || [1]));
  const avgConfidence = path.confidences ? 
    path.confidences.reduce((a, b) => a + b, 0) / path.confidences.length : 0;

  return (
    <div className="path-card">
      <div className="path-header" onClick={() => setExpanded(!expanded)}>
        <div className="path-number">#{index}</div>
        
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
