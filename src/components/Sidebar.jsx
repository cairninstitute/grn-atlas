import React, { useState, useEffect, useRef } from 'react';
import '../styles/Sidebar.css';

const KINGDOMS = [
  { id: 'Animalia', label: 'Animalia' },
  { id: 'Plantae', label: 'Plantae' }
];

const SPECIES = {
  Animalia: [
    { tax_id: 9606, symbol: 'human', common: 'Human', scientific: 'Homo sapiens' },
    { tax_id: 10090, symbol: 'mouse', common: 'Mouse', scientific: 'Mus musculus' }
  ],
  Plantae: [
    { tax_id: 3702, symbol: 'arabidopsis', common: 'Arabidopsis', scientific: 'Arabidopsis thaliana' },
    { tax_id: 39947, symbol: 'rice', common: 'Rice', scientific: 'Oryza sativa' },
    { tax_id: 4081, symbol: 'tomato', common: 'Tomato', scientific: 'Solanum lycopersicum' },
    { tax_id: 33119, symbol: 'petunia', common: 'Petunia', scientific: 'Petunia axillaris' },
    { tax_id: 4113, symbol: 'potato', common: 'Potato', scientific: 'Solanum tuberosum' },
    { tax_id: 3847, symbol: 'soybean', common: 'Soybean', scientific: 'Glycine max' },
    { tax_id: 29654, symbol: 'poplar', common: 'Poplar', scientific: 'Populus trichocarpa' },
    { tax_id: 4558, symbol: 'sorghum', common: 'Sorghum', scientific: 'Sorghum bicolor' },
    { tax_id: 8585, symbol: 'grape', common: 'Grape', scientific: 'Vitis vinifera' }
  ]
};

export default function Sidebar({ filters, onFilterChange, onGeneSearch, loading }) {
  const [searchInput, setSearchInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedKingdoms, setSelectedKingdoms] = useState(new Set(filters.kingdom));
  const [selectedSpecies, setSelectedSpecies] = useState(new Set(filters.species));
  const [regulationTypes, setRegulationTypes] = useState(new Set(filters.regulationType));
  const [confidence, setConfidence] = useState(filters.minConfidence);
  const [direction, setDirection] = useState(filters.direction);
  const [maxDepth, setMaxDepth] = useState(filters.maxDepth);
  const searchInputRef = useRef(null);
  const suggestionsRef = useRef(null);

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
      SPECIES[kingdom]?.forEach(s => newSpecies.delete(s.symbol));
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
      visible.push(...SPECIES[kingdom]);
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
                    <span className="suggestion-symbol">{gene.symbol}</span>
                    {gene.is_tf && <span className="tf-badge">TF</span>}
                    <span className="species-badge">{gene.species}</span>
                  </div>
                  <div className="suggestion-secondary">
                    {gene.name}
                  </div>
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
          {KINGDOMS.map((kingdom) => (
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
          <div>2 species (human, arabidopsis)</div>
          <div>19,776 genes</div>
          <div>96,703 interactions</div>
        </div>
      </div>
    </div>
  );
}
