import React, { useState, useEffect, useRef } from 'react';
import { geneLabel } from '../utils/geneLabel';
import DataSourcesPanel from './DataSourcesPanel';
import '../styles/Sidebar.css';

// Display metadata for species we may hold data for. The actual list shown is
// driven by which species exist in the database (see the stats fetch below);
// this map only supplies nice labels and kingdom grouping.
const SPECIES_META = {
  human: { common: 'Human', scientific: 'Homo sapiens', kingdom: 'Animalia' },
  mouse: { common: 'Mouse', scientific: 'Mus musculus', kingdom: 'Animalia' },
  arabidopsis: { common: 'Arabidopsis', scientific: 'Arabidopsis thaliana', kingdom: 'Plantae' },
  tomato: { common: 'Tomato', scientific: 'Solanum lycopersicum', kingdom: 'Plantae' },
  petunia: { common: 'Petunia', scientific: 'Petunia axillaris', kingdom: 'Plantae' },
  rice: { common: 'Rice', scientific: 'Oryza sativa', kingdom: 'Plantae' },
};

const KINGDOM_ORDER = ['Animalia', 'Plantae', 'Other'];

// Build the {kingdom: [species]} grouping and kingdom list from the species
// symbols actually present in the data.
function groupSpecies(presentSymbols) {
  const byKingdom = {};
  presentSymbols.forEach((symbol) => {
    const meta = SPECIES_META[symbol] || {};
    const kingdom = meta.kingdom || 'Other';
    const common = meta.common || symbol.charAt(0).toUpperCase() + symbol.slice(1);
    (byKingdom[kingdom] = byKingdom[kingdom] || []).push({
      symbol, common, scientific: meta.scientific || '',
    });
  });
  Object.values(byKingdom).forEach((list) => list.sort((a, b) => a.common.localeCompare(b.common)));
  const kingdoms = KINGDOM_ORDER
    .filter((k) => byKingdom[k])
    .map((k) => ({ id: k, label: k }));
  return { byKingdom, kingdoms };
}

export default function Sidebar({ filters, onFilterChange, onGeneSearch, loading }) {
  const [searchInput, setSearchInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedKingdoms, setSelectedKingdoms] = useState(new Set(filters.kingdom));
  const [selectedSpecies, setSelectedSpecies] = useState(new Set(filters.species));
  const [regulationTypes, setRegulationTypes] = useState(new Set(filters.regulationType));
  const [confidence, setConfidence] = useState(filters.minConfidence);
  const [includeInferred, setIncludeInferred] = useState(filters.includeInferred !== false);
  const [direction, setDirection] = useState(filters.direction);
  const [maxDepth, setMaxDepth] = useState(filters.maxDepth);
  const [speciesByKingdom, setSpeciesByKingdom] = useState({});
  const [kingdoms, setKingdoms] = useState([]);
  const [showDataSources, setShowDataSources] = useState(false);
  const [stats, setStats] = useState(null);
  const searchInputRef = useRef(null);
  const suggestionsRef = useRef(null);

  // Populate the kingdom/species filters from the species actually in the data.
  useEffect(() => {
    fetch('/api/v1/stats')
      .then((r) => r.json())
      .then((stats) => {
        setStats(stats);
        const { byKingdom, kingdoms } = groupSpecies(stats.species_list || []);
        setSpeciesByKingdom(byKingdom);
        setKingdoms(kingdoms);
      })
      .catch((err) => console.error('Failed to load species list:', err));
  }, []);

  // Fetch gene suggestions
  useEffect(() => {
    if (searchInput.length < 2) {
      setSuggestions([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        let url = `/api/v1/genes/search?q=${encodeURIComponent(searchInput)}&limit=10`;
        if (selectedSpecies.size === 1) {
          url += `&species=${[...selectedSpecies][0]}`;
        }
        const response = await fetch(url);
        const data = await response.json();
        let results = data.results || [];
        if (selectedSpecies.size > 1) {
          results = results.filter(g => selectedSpecies.has(g.species));
        }
        setSuggestions(results);
      } catch (err) {
        console.error('Search error:', err);
        setSuggestions([]);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchInput, selectedSpecies]);

  // Handle search
  const handleSearch = (gene) => {
    onGeneSearch(gene.symbol);
    setSearchInput('');
    setSuggestions([]);
    setShowSuggestions(false);
  };

  // Handle kingdom change
  const handleKingdomToggle = (kingdom) => {
    const newKingdoms = new Set(selectedKingdoms);
    if (newKingdoms.has(kingdom)) {
      newKingdoms.delete(kingdom);
    } else {
      newKingdoms.add(kingdom);
    }
    setSelectedKingdoms(newKingdoms);
    
    // Reset species if kingdom is deselected
    if (!newKingdoms.has(kingdom)) {
      const newSpecies = new Set(selectedSpecies);
      speciesByKingdom[kingdom]?.forEach(s => newSpecies.delete(s.symbol));
      setSelectedSpecies(newSpecies);
    }

    onFilterChange({
      ...filters,
      kingdom: Array.from(newKingdoms),
      species: Array.from(selectedSpecies)
    });
  };

  // Handle species change
  const handleSpeciesToggle = (species) => {
    const newSpecies = new Set(selectedSpecies);
    if (newSpecies.has(species)) {
      newSpecies.delete(species);
    } else {
      newSpecies.add(species);
    }
    setSelectedSpecies(newSpecies);

    onFilterChange({
      ...filters,
      species: Array.from(newSpecies)
    });
  };

  // Handle regulation type change
  const handleRegulationTypeToggle = (type) => {
    const newTypes = new Set(regulationTypes);
    if (newTypes.has(type)) {
      newTypes.delete(type);
    } else {
      newTypes.add(type);
    }
    setRegulationTypes(newTypes);

    onFilterChange({
      ...filters,
      regulationType: Array.from(newTypes)
    });
  };

  // Handle confidence change
  const handleConfidenceChange = (e) => {
    const value = parseFloat(e.target.value);
    setConfidence(value);

    onFilterChange({
      ...filters,
      minConfidence: value
    });
  };

  // Handle inferred-edge toggle
  const handleInferredToggle = () => {
    const value = !includeInferred;
    setIncludeInferred(value);
    onFilterChange({ ...filters, includeInferred: value });
  };

  // Handle direction change
  const handleDirectionChange = (e) => {
    setDirection(e.target.value);

    onFilterChange({
      ...filters,
      direction: e.target.value
    });
  };

  // Handle depth change
  const handleDepthChange = (e) => {
    const value = parseInt(e.target.value, 10);
    setMaxDepth(value);

    onFilterChange({
      ...filters,
      maxDepth: value
    });
  };

  const getVisibleSpecies = () => {
    const visible = [];
    selectedKingdoms.forEach(kingdom => {
      visible.push(...(speciesByKingdom[kingdom] || []));
    });
    return visible;
  };

  return (
    <div className="sidebar">
      {/* Gene Search */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">Gene search</h3>
        <div className="search-container">
          <div className="search-input-wrapper">
            <input
              ref={searchInputRef}
              type="text"
              className="search-input"
              placeholder="Search genes..."
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              disabled={loading}
            />
            {loading && <div className="search-spinner">⟳</div>}
          </div>

          {showSuggestions && suggestions.length > 0 && (
            <div className="suggestions-dropdown" ref={suggestionsRef}>
              {suggestions.map((gene) => (
                <div
                  key={gene.id}
                  className="suggestion-item"
                  onClick={() => handleSearch(gene)}
                >
                  <div className="suggestion-main">
                    <span className="suggestion-symbol">{geneLabel(gene).label}</span>
                    {gene.is_tf && <span className="tf-badge">TF</span>}
                    <span className="species-badge">{gene.species}</span>
                  </div>
                  <div className="suggestion-secondary">
                    {gene.name}
                  </div>
                  {gene.synonyms && gene.synonyms.length > 0 && (
                    <div className="suggestion-synonyms">
                      <span className="synonym-label">≈ Arabidopsis ortholog (inferred):</span>{' '}
                      {gene.synonyms.join(', ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Kingdom Filter */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">Kingdom</h3>
        <div className="filter-group">
          {kingdoms.map((kingdom) => (
            <label key={kingdom.id} className="filter-item">
              <input
                type="checkbox"
                checked={selectedKingdoms.has(kingdom.id)}
                onChange={() => handleKingdomToggle(kingdom.id)}
              />
              <span>{kingdom.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Species Filter */}
      {getVisibleSpecies().length > 0 && (
        <div className="sidebar-section">
          <h3 className="sidebar-title">Species</h3>
          <div className="filter-group">
            {getVisibleSpecies().map((species) => (
              <label key={species.symbol} className="filter-item">
                <input
                  type="checkbox"
                  checked={selectedSpecies.has(species.symbol)}
                  onChange={() => handleSpeciesToggle(species.symbol)}
                />
                <span>{species.common}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Evidence Filter */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">Evidence</h3>
        <div className="filter-group">
          <label className="filter-item" title="Edges predicted by projecting the Arabidopsis network through orthology onto tomato/petunia — not measured">
            <input
              type="checkbox"
              checked={includeInferred}
              onChange={handleInferredToggle}
            />
            <span>Include inferred edges</span>
          </label>
        </div>
      </div>

      {/* Regulation Type Filter */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">Regulation type</h3>
        <div className="filter-group">
          {['activation', 'repression', 'unknown'].map((type) => (
            <label key={type} className="filter-item">
              <input
                type="checkbox"
                checked={regulationTypes.has(type)}
                onChange={() => handleRegulationTypeToggle(type)}
              />
              <span style={{ textTransform: 'capitalize' }}>{type}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Confidence Threshold */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">Confidence threshold</h3>
        <input
          type="range"
          className="slider"
          min="0.3"
          max="0.9"
          step="0.05"
          value={confidence}
          onChange={handleConfidenceChange}
        />
        <div className="slider-value">≥ {confidence.toFixed(2)}</div>
      </div>

      {/* Direction */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">Regulation direction</h3>
        <select className="select-input" value={direction} onChange={handleDirectionChange}>
          <option value="both">Both (regulators & targets)</option>
          <option value="regulators">Regulators only</option>
          <option value="targets">Targets only</option>
        </select>
      </div>

      {/* Max Depth */}
      <div className="sidebar-section">
        <h3 className="sidebar-title">Network depth</h3>
        <input
          type="range"
          className="slider"
          min="1"
          max="5"
          value={maxDepth}
          onChange={handleDepthChange}
        />
        <div className="slider-value">{maxDepth} hops</div>
      </div>

      {/* Info */}
      <div className="sidebar-info">
        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
          {stats ? (
            <>
              <div>{stats.species} species</div>
              <div>{stats.genes?.toLocaleString()} genes</div>
              <div>{stats.interactions?.toLocaleString()} interactions</div>
            </>
          ) : (
            <div>Loading…</div>
          )}
        </div>
        <button className="data-sources-btn" onClick={() => setShowDataSources(true)}>
          Data &amp; citations
        </button>
      </div>

      <DataSourcesPanel open={showDataSources} onClose={() => setShowDataSources(false)} />
    </div>
  );
}
