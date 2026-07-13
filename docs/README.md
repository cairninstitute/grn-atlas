# GRN Atlas - Gene Regulatory Network Visualization Tool

A complete React-based interactive visualization tool for exploring gene regulatory networks across multiple species. Built with Cytoscape.js for network visualization and FastAPI for the backend.

## Features

### 🔗 Network Visualization (Phase 1-2)
- **Interactive Cytoscape.js network visualization** with drag-and-drop node repositioning
- **Real-time confidence score visualization** with color-coded edges
- **Node type differentiation**: Transcription factors (diamonds) vs target genes (circles)
- **Hover tooltips** showing interaction details: confidence, regulation type, source databases
- **Multiple layout options**: Force-directed (CoSE), circular (concentric), hierarchical (Klay)
- **Zoom and pan controls** with fit-to-screen functionality

### 🔍 Gene Search & Filtering (Phase 1)
- **Autocomplete search** with gene symbol, name, and species filtering
- **Multi-level filtering**:
  - Kingdom (Animalia, Plantae)
  - Species (21 supported)
  - Regulation type (activation, repression, unknown)
  - Confidence threshold (0.3-0.9)
  - Network direction (regulators, targets, both)
  - Network depth (1-5 hops)

### 📊 Gene Details Panel (Phase 2)
- **Gene information** display (symbol, name, species, ID)
- **Evidence breakdown** showing source database distribution (TRRUST, DoRothEA, etc.)
- **Sortable interaction lists** (confidence, alphabetical)
- **Confidence scoring guide** with color-coded confidence levels
- **Source database attribution** for each interaction

### ⚖️ Cross-Species Comparison (Phase 3)
- **Side-by-side regulatory network comparison** across multiple species
- **Ortholog discovery** showing conserved regulatory relationships
- **Dynamic species selection** - add/remove species at runtime
- **Regulatory delta visualization** - highlight species-specific interactions
- **Insight cards** showing key regulatory differences

### ✏️ Intervention Designer (Phase 4)
- **Design regulatory interventions** to simulate phenotypic changes
- **Parameterizable interventions**:
  - Target regulator selection
  - Action type (enhance, suppress)
  - Magnitude scaling (0.5-3.0×)
- **Real-time cascade prediction** showing downstream effects
- **Confidence assessment** of predicted effects
- **Design export** as JSON for reproducibility and sharing

### 🛤️ Pathway Explorer (Phase 2-3)
- **Pathfinding between genes** using graph algorithms
- **Multi-hop regulatory routes** with configurable depth
- **Path scoring** based on confidence and evidence
- **Expandable path details** showing complete gene chains
- **Source attribution** for each interaction in the path

## Technology Stack

### Frontend
- **React 18**: Component-based UI framework
- **Cytoscape.js**: Network visualization library
- **Cytoscape-Popper**: Tooltip positioning
- **CSS3**: Modern styling with CSS variables for theming

### Backend (FastAPI)
- **FastAPI**: High-performance Python API framework
- **PostgreSQL/Neo4j**: Graph database options
- **SQLAlchemy**: ORM for database queries
- **CORS Middleware**: Cross-origin request handling

### Data
- 21 species (6 animal/fungi + 15 plants)
- 591K genes
- 6.7M regulatory interactions
- Multiple databases: TRRUST, DoRothEA, PlantRegMap, JASPAR

## Installation

### Prerequisites
- Node.js 14+ 
- npm or yarn
- Python 3.8+
- PostgreSQL or Neo4j database

### Quick Start

```bash
# Clone repository
git clone <repo-url>
cd grn-atlas

# Install frontend dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your API URL and settings

# Start frontend
npm start
# Opens at http://localhost:3000

# In another terminal, start backend (see backend setup guide)
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

## File Structure

```
grn-atlas/
├── components/
│   ├── GeneNetworkExplorer.jsx      Main application container
│   ├── Sidebar.jsx                  Search and filter controls
│   ├── Toolbar.jsx                  Selected gene info and stats
│   ├── ViewTabs.jsx                 View mode selector
│   ├── NetworkVisualization.jsx     Cytoscape visualization
│   ├── GeneDetailPanel.jsx          Gene details and interactions
│   ├── ComparisonView.jsx           Cross-species comparison
│   ├── InterventionDesigner.jsx     Intervention planning
│   └── PathwayView.jsx              Multi-hop pathway search
├── services/
│   └── apiService.js                API client and utilities
├── styles/
│   ├── theme.css                    CSS variables and defaults
│   ├── GeneNetworkExplorer.css       Main layout styles
│   ├── Sidebar.css
│   ├── Toolbar.css
│   ├── ViewTabs.css
│   ├── NetworkVisualization.css
│   ├── GeneDetailPanel.css
│   ├── ComparisonView.css
│   ├── InterventionDesigner.css
│   └── PathwayView.css
├── INTEGRATION_GUIDE.md             Backend integration instructions
├── package.json                     Dependencies
└── .env.example                     Environment configuration template
```

## Component Details

### GeneNetworkExplorer
Main application container managing state and view routing.

**Props**: None (root component)

**State**:
- `selectedGene`: Currently selected gene object
- `viewMode`: Active view ('network', 'pathways', 'comparison', 'design')
- `filters`: Filter configuration object
- `networkData`: Fetched network neighborhood data
- `loading`: Loading state for API calls

### Sidebar
Search and filter controls for gene discovery and network customization.

**Props**:
- `filters`: Current filter state
- `onFilterChange`: Callback for filter updates
- `onGeneSearch`: Callback for gene selection
- `loading`: Loading indicator state

**Features**:
- Autocomplete gene search with suggestions
- Kingdom and species filtering
- Regulation type toggling
- Confidence threshold slider
- Direction and depth controls

### NetworkVisualization
Cytoscape.js network visualization with interactivity.

**Props**:
- `gene`: Selected gene object
- `data`: Network data (regulators and targets)
- `filters`: Active filter settings
- `expandedNodes`: Set of expanded node IDs
- `onNodeExpand`: Node expansion callback

**Features**:
- Force-directed, circular, and hierarchical layouts
- Node color/shape coding by type
- Edge styling by regulation type
- Confidence-based edge thickness
- Interactive controls for zoom and layout switching

### GeneDetailPanel
Right-side panel showing gene information and interactions.

**Props**:
- `gene`: Selected gene details
- `data`: Regulatory interaction data

**Features**:
- Gene metadata display
- Evidence source distribution
- Sortable regulator and target lists
- Confidence visualization
- Expandable lists for large interactions

### ComparisonView
Grid-based side-by-side comparison of regulatory networks across species.

**Props**:
- `gene`: Current gene
- `currentSpecies`: Default species for comparison

**Features**:
- Dynamic species selection
- Ortholog discovery
- Regulator/target matching
- Species-specific insights

### InterventionDesigner
Three-panel interface for designing regulatory interventions.

**Props**:
- `gene`: Target gene
- `networkData`: Network data with regulators

**Features**:
- Left: Regulator list with enhance/suppress buttons
- Middle: Intervention plan with strength sliders
- Right: Predicted cascade preview
- JSON export functionality

### PathwayView
Graph search tool for finding regulatory routes between genes.

**Props**:
- `gene`: Source gene
- `filters`: Search filter settings

**Features**:
- Target gene autocomplete
- Configurable max depth and result limit
- Expandable path details
- Confidence scoring per step

## API Specification

### Gene Endpoints

#### Search genes
```
GET /api/v1/genes/search?q=TP53&limit=10&species=human
```

Response:
```json
{
  "results": [
    {
      "id": "ENSG00000141510",
      "symbol": "TP53",
      "name": "Tumor protein 53",
      "species": "human",
      "is_tf": true
    }
  ]
}
```

#### Get gene by ID
```
GET /api/v1/genes/{gene_id}
```

#### Get gene by symbol
```
GET /api/v1/genes/symbol/{symbol}
```

### Pathway Endpoints

#### Get neighborhood
```
POST /api/v1/pathways/neighborhood/{gene_id}
Content-Type: application/json

{
  "max_depth": 1,
  "direction": "both",
  "regulation_type": ["activation", "repression"],
  "min_confidence": 0.3
}
```

Response:
```json
{
  "gene": { "id": "...", "symbol": "TP53" },
  "regulators": [...],
  "targets": [...],
  "stats": { "regulators": 12, "targets": 8, "paths": 3 }
}
```

#### Find paths
```
POST /api/v1/pathways/pathfinding
Content-Type: application/json

{
  "source_gene_id": "ENSG00000141510",
  "target_symbol": "CDKN1A",
  "max_depth": 3,
  "limit": 20,
  "min_confidence": 0.3
}
```

#### Predict cascade
```
POST /api/v1/pathway/predict-cascade
Content-Type: application/json

{
  "target_gene_id": "ENSG00000141510",
  "interventions": [
    {
      "tf_id": "ENSG00000133056",
      "direction": "up",
      "magnitude": 1.5
    }
  ],
  "depth": 3
}
```

### Orthology Endpoints

#### Get orthology data
```
GET /api/v1/genes/orthology/{gene_id}?species=human,arabidopsis,rice
```

## Configuration

### Environment Variables

```bash
# API Configuration
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_API_TIMEOUT=30000

# Feature Flags
REACT_APP_ENABLE_EXPORT=true
REACT_APP_ENABLE_ADVANCED_FILTERS=true

# Visualization Settings
REACT_APP_DEFAULT_CONFIDENCE=0.6
REACT_APP_MAX_NETWORK_NODES=1000
REACT_APP_DEFAULT_LAYOUT=cose

# Performance
REACT_APP_CACHE_TTL=300000
REACT_APP_DEBOUNCE_SEARCH=300
REACT_APP_MAX_SEARCH_RESULTS=50

# UI Theme
REACT_APP_THEME=light
REACT_APP_COMPACT_MODE=false
```

## Performance Optimization

### Frontend
- **Component memoization** to prevent unnecessary re-renders
- **API response caching** (5-minute TTL by default)
- **Debounced search** (300ms default)
- **Lazy-loaded detail panels**
- **Virtual scrolling** for large gene lists (can be added)

### Backend
- **Database indexing** on gene symbols and interaction tables
- **Query optimization** with smart joins and pagination
- **Redis caching** for frequent searches
- **Connection pooling** for database access

### Network
- **Result pagination** limits data transfer
- **Gzip compression** for API responses
- **CDN for static assets** (optional)

## Testing

### Unit Tests
```bash
npm test
```

### Integration Tests
```bash
npm test -- --testPathPattern=integration
```

### E2E Tests
Consider adding Cypress or Playwright for end-to-end testing.

## Troubleshooting

### Network visualization not rendering
- Verify Cytoscape.js is installed: `npm ls cytoscape`
- Check browser console for JavaScript errors
- Ensure API is returning valid data format

### Slow gene searches
- Add database indexes on gene symbols
- Enable query result pagination
- Consider implementing full-text search

### CORS errors
- Verify FastAPI CORS middleware configuration
- Check REACT_APP_API_URL matches backend URL
- Ensure backend is running and accessible

### Memory issues with large networks
- Reduce max_depth or increase min_confidence filter
- Implement virtual scrolling for detail panels
- Monitor Cytoscape rendering performance

## Roadmap

### Phase 5 (Polish & Performance)
- [ ] Advanced accessibility features
- [ ] Keyboard navigation shortcuts
- [ ] Dark mode toggle
- [ ] Performance monitoring/analytics
- [ ] Unit and integration test suite
- [ ] Documentation improvements
- [ ] Responsive mobile optimization

### Future Enhancements
- [ ] Collaboration features (shared views, annotations)
- [ ] Custom gene list import
- [ ] Phenotype prediction model integration
- [ ] Time-series data visualization
- [ ] Machine learning model explainability
- [ ] Publication export (figures, tables)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.

## Citation

If you use GRN Atlas in your research, please cite:

```bibtex
@software{grn_atlas,
  title={GRN Atlas: Gene Regulatory Network Visualization Tool},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/grn-atlas}
}
```

## Support

- 📖 See [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) for backend integration
- 🐛 Report bugs on GitHub Issues
- 💬 Discuss features in GitHub Discussions
- 📧 Contact: support@example.com

## Acknowledgments

- Built on [Cytoscape.js](https://js.cytoscape.org/) for network visualization
- Data sources: TRRUST, DoRothEA, PlantRegMap, JASPAR
- Icons and UI patterns inspired by modern bioinformatics tools
