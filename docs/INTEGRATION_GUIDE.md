# GRN Atlas UI - Integration Guide

This is a complete React implementation of the Gene Regulatory Network (GRN) Atlas visualization tool. Follow these steps to integrate it into your existing codebase.

## Installation

### 1. Install Dependencies

```bash
npm install cytoscape cytoscape-popper
```

### 2. File Structure

Place the provided files in your React project:

```
src/
├── components/
│   ├── GeneNetworkExplorer.jsx      (renamed from App)
│   ├── Sidebar.jsx
│   ├── Toolbar.jsx
│   ├── ViewTabs.jsx
│   ├── NetworkVisualization.jsx
│   ├── GeneDetailPanel.jsx
│   ├── ComparisonView.jsx
│   ├── InterventionDesigner.jsx
│   └── PathwayView.jsx
├── services/
│   └── apiService.js
└── styles/
    ├── theme.css
    ├── GeneNetworkExplorer.css
    ├── Sidebar.css
    ├── Toolbar.css
    ├── ViewTabs.css
    ├── NetworkVisualization.css
    ├── GeneDetailPanel.css
    ├── ComparisonView.css
    ├── InterventionDesigner.css
    └── PathwayView.css
```

### 3. Update Your Main App

In your main `App.jsx` or `index.jsx`:

```jsx
import GeneNetworkExplorer from './components/GeneNetworkExplorer';
import './styles/theme.css';

export default function App() {
  return <GeneNetworkExplorer />;
}
```

### 4. Configure API Endpoints

Update `services/apiService.js` to match your FastAPI backend URL:

```javascript
const API_BASE = process.env.REACT_APP_API_URL || '/api/v1';
```

Add to your `.env`:

```
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## FastAPI Backend Implementation

Here's the minimal API structure your backend needs to implement:

### Required Endpoints

```python
from fastapi import FastAPI, HTTPException
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI()

# ============= Models =============

class Gene(BaseModel):
    id: str
    symbol: str
    name: str
    species: str
    ensembl_id: Optional[str]
    is_tf: bool
    gene_type: Optional[str]

class GeneInteraction(BaseModel):
    id: str
    symbol: str
    name: str
    species: str
    is_tf: bool
    confidence: float
    regulation_type: str  # 'activation', 'repression', 'unknown'
    source_databases: List[str]

class NetworkData(BaseModel):
    gene: Gene
    regulators: List[GeneInteraction]
    targets: List[GeneInteraction]
    stats: dict

class PathData(BaseModel):
    genes: List[Gene]
    regulation_types: List[str]
    confidences: List[float]
    sources: List[List[str]]
    overall_confidence: float

# ============= Gene Endpoints =============

@app.get("/api/v1/genes/search")
async def search_genes(q: str, limit: int = 10, species: Optional[str] = None):
    """
    Search for genes by symbol or name
    """
    # TODO: Query your database
    # Return list of genes matching query
    return {
        "results": [
            {
                "id": "ENSG00000141510",
                "symbol": "TP53",
                "name": "Tumor protein 53",
                "species": "human",
                "is_tf": True,
                "gene_type": "protein_coding"
            }
        ]
    }

@app.get("/api/v1/genes/{gene_id}")
async def get_gene(gene_id: str):
    """Get gene details by ID"""
    # TODO: Query your database
    return {
        "id": gene_id,
        "symbol": "TP53",
        "name": "Tumor protein 53",
        "species": "human",
        "ensembl_id": "ENSG00000141510",
        "is_tf": True
    }

@app.get("/api/v1/genes/symbol/{symbol}")
async def get_gene_by_symbol(symbol: str):
    """Get gene details by symbol"""
    # TODO: Query your database
    return await get_gene("ENSG00000141510")

# ============= Pathway Endpoints =============

@app.post("/api/v1/pathways/neighborhood/{gene_id}")
async def get_neighborhood(gene_id: str, 
                          max_depth: int = 1,
                          direction: str = "both",
                          regulation_type: List[str] = ["activation", "repression"],
                          min_confidence: float = 0.3):
    """
    Get regulatory neighborhood around a gene
    
    Args:
        gene_id: Target gene ID
        max_depth: Maximum hops (1-5)
        direction: 'both', 'regulators', or 'targets'
        regulation_type: Filter by regulation type
        min_confidence: Minimum confidence score
    """
    # TODO: Query your regulatory database
    # Build network from regulators and targets
    
    return {
        "gene": {"id": gene_id, "symbol": "TP53"},
        "regulators": [
            {
                "id": "ENSG00000133056",
                "symbol": "ATM",
                "name": "ATM Serine/Threonine Kinase",
                "species": "human",
                "is_tf": True,
                "confidence": 0.95,
                "regulation_type": "activation",
                "source_databases": ["TRRUST", "DoRothEA"]
            }
        ],
        "targets": [
            {
                "id": "ENSG00000124575",
                "symbol": "CDKN1A",
                "name": "Cyclin Dependent Kinase Inhibitor 1A",
                "species": "human",
                "is_tf": False,
                "confidence": 0.92,
                "regulation_type": "activation",
                "source_databases": ["TRRUST"]
            }
        ],
        "stats": {
            "regulators": 12,
            "targets": 8,
            "paths": 3
        }
    }

@app.post("/api/v1/pathways/pathfinding")
async def find_paths(source_gene_id: str,
                     target_symbol: str,
                     max_depth: int = 3,
                     limit: int = 20,
                     min_confidence: float = 0.3,
                     regulation_type: List[str] = ["activation", "repression"]):
    """
    Find regulatory paths between two genes
    
    Returns top N shortest paths
    """
    # TODO: Use graph algorithms (BFS, Dijkstra) to find paths
    # Consider path length and confidence scores
    
    return {
        "paths": [
            {
                "genes": [
                    {"id": "1", "symbol": "TP53", "name": "Tumor protein 53"},
                    {"id": "2", "symbol": "ATM", "name": "ATM Kinase"},
                    {"id": "3", "symbol": "CDKN1A", "name": "CDK Inhibitor 1A"}
                ],
                "regulation_types": ["activation", "activation"],
                "confidences": [0.95, 0.92],
                "sources": [["TRRUST", "DoRothEA"], ["TRRUST"]],
                "overall_confidence": 0.88
            }
        ]
    }

@app.post("/api/v1/pathway/predict-cascade")
async def predict_cascade(target_gene_id: str,
                         interventions: List[dict],
                         depth: int = 3,
                         return_nodes: bool = True):
    """
    Predict cascade effects of regulatory interventions
    
    Args:
        target_gene_id: Target gene
        interventions: List of {"tf_id": str, "direction": "up"/"down", "magnitude": float}
        depth: Cascade depth
        return_nodes: Include node details
        
    Returns:
        Predicted cascade with affected genes and magnitudes
    """
    # TODO: Use systems biology model (boolean networks, ODE, etc.)
    # Simulate regulatory cascade from interventions
    
    return {
        "cascade": [
            {
                "id": "ENSG00000124575",
                "symbol": "CDKN1A",
                "level": 1,
                "direction": "up",
                "magnitude": 1.5,
                "confidence": 0.92
            },
            {
                "id": "ENSG00000171791",
                "symbol": "BAX",
                "level": 1,
                "direction": "up",
                "magnitude": 1.3,
                "confidence": 0.87
            }
        ],
        "average_confidence": 0.89,
        "affected_genes": 2
    }

# ============= Orthology Endpoints =============

@app.get("/api/v1/genes/orthology/{gene_id}")
async def get_orthology(gene_id: str, species: Optional[str] = None):
    """
    Get orthologous genes across species
    Returns regulatory networks for orthologs
    """
    # TODO: Query orthology database (Ensembl, Inparanoid, etc.)
    # Get orthologs and their regulatory networks
    
    return {
        "human": {
            "ortholog_symbol": "TP53",
            "regulators": [
                {
                    "id": "ENSG00000133056",
                    "symbol": "ATM",
                    "is_tf": True,
                    "confidence": 0.95,
                    "regulation_type": "activation"
                }
            ],
            "targets": []
        },
        "arabidopsis": {
            "ortholog_symbol": "AT4G27300",  # Not a real ortholog
            "regulators": [],
            "targets": []
        }
    }

# ============= Stats Endpoints =============

@app.get("/api/v1/stats")
async def get_stats():
    """Get overall database statistics"""
    return {
        "species": 21,
        "genes": 591000,
        "interactions": 6700000,
        "databases": ["TRRUST", "DoRothEA", "PlantRegMap", "JASPAR"]
    }

@app.get("/api/v1/stats/species/{species}")
async def get_species_stats(species: str):
    """Get species-specific statistics"""
    return {
        "species": species,
        "genes": 20000,
        "transcription_factors": 1500,
        "interactions": 250000
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## CORS Configuration

Add CORS middleware to your FastAPI app:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Database Implementation Notes

### PostgreSQL/Neo4j Schema

For optimal performance, structure your data as:

```sql
-- Genes table
CREATE TABLE genes (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR UNIQUE,
    name TEXT,
    species VARCHAR,
    ensembl_id VARCHAR,
    is_tf BOOLEAN,
    gene_type VARCHAR
);

-- Interactions table
CREATE TABLE interactions (
    id VARCHAR PRIMARY KEY,
    source_id VARCHAR REFERENCES genes(id),
    target_id VARCHAR REFERENCES genes(id),
    regulation_type VARCHAR,
    confidence FLOAT,
    source_databases TEXT[],
    PRIMARY KEY (source_id, target_id)
);

-- Create indexes for fast queries
CREATE INDEX idx_symbol ON genes(symbol);
CREATE INDEX idx_source ON interactions(source_id);
CREATE INDEX idx_target ON interactions(target_id);
```

### Neo4j Cypher Example

```cypher
// Create gene nodes
CREATE (tp53:Gene {id: 'ENSG00000141510', symbol: 'TP53', species: 'human'})
CREATE (atm:Gene {id: 'ENSG00000133056', symbol: 'ATM', species: 'human'})

// Create regulatory relationships
CREATE (atm)-[:ACTIVATES {confidence: 0.95, sources: ['TRRUST', 'DoRothEA']}]->(tp53)

// Query neighbors
MATCH (g:Gene {symbol: 'TP53'})<-[r:ACTIVATES|REPRESSES]-(regulator)
RETURN regulator, r
LIMIT 20
```

## Development

### Running Locally

```bash
# Frontend
npm start

# Backend (in separate terminal)
cd backend
uvicorn main:app --reload --port 8000
```

### Testing

```bash
# Test API endpoints
curl http://localhost:8000/api/v1/genes/search?q=TP53

# Test visualization
# Navigate to http://localhost:3000
```

## Performance Optimization

### Recommended Optimizations

1. **Caching**: Use Redis for gene search and neighborhood queries
2. **Pagination**: Limit results for large gene lists
3. **Query Optimization**: Use database indexes on gene symbols and interaction tables
4. **Frontend Caching**: The provided `apiCache` utility caches results for 5 minutes
5. **Lazy Loading**: The detail panel and comparison view load data on demand

### Database Query Examples

```python
# Fast gene search with prefix matching
SELECT * FROM genes 
WHERE symbol ILIKE :query || '%' 
LIMIT 10;

# Efficient neighborhood retrieval
SELECT t.*, r.confidence, r.regulation_type
FROM genes g
JOIN interactions i ON g.id = i.source_id
JOIN genes t ON i.target_id = t.id
WHERE g.id = :gene_id
AND i.confidence >= :min_confidence
LIMIT 1000;
```

## Troubleshooting

### Common Issues

**Network visualization not rendering**
- Ensure Cytoscape.js is installed: `npm install cytoscape`
- Check browser console for errors
- Verify API is returning data

**API requests failing**
- Check CORS configuration
- Verify API base URL in `.env`
- Ensure backend is running on correct port

**Slow searches**
- Add database indexes on gene symbols
- Implement result pagination
- Use full-text search if available

**Layout issues on mobile**
- The UI is responsive, but test on various screen sizes
- Adjust grid-template-columns in ComparisonView for smaller screens

## Next Steps

1. **Implement Database Layer**: Replace mock API responses with real database queries
2. **Add Authentication**: Integrate user login if needed
3. **Export Features**: Implement JSON/GraphML export for networks
4. **Advanced Filtering**: Add more complex filter options
5. **Performance Profiling**: Monitor and optimize slow queries
6. **Testing**: Add unit and integration tests

## Support

For issues or questions:
1. Check this guide
2. Review component prop documentation
3. Check API service error handling
4. Enable browser console debugging

## License

This code is provided as-is for use with your GRN Atlas project.
