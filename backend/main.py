"""
GRN Atlas FastAPI Backend
Complete example implementation with all required endpoints
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GRN Atlas API",
    description="Gene Regulatory Network visualization backend",
    version="1.0.0"
)

# ============= CORS Configuration =============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= Pydantic Models =============

class Gene(BaseModel):
    id: str
    symbol: str
    name: str
    species: str
    ensembl_id: Optional[str] = None
    is_tf: bool = False
    gene_type: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "ENSG00000141510",
                "symbol": "TP53",
                "name": "Tumor protein 53",
                "species": "human",
                "ensembl_id": "ENSG00000141510",
                "is_tf": True,
                "gene_type": "protein_coding"
            }
        }

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
    stats: Dict[str, int]

class PathGene(BaseModel):
    id: str
    symbol: str
    name: str

class Path(BaseModel):
    genes: List[PathGene]
    regulation_types: List[str]
    confidences: List[float]
    sources: List[List[str]]
    overall_confidence: float

class CascadeEffect(BaseModel):
    id: str
    symbol: str
    level: int
    direction: str  # 'up', 'down'
    magnitude: float
    confidence: float

class CascadeResult(BaseModel):
    cascade: List[CascadeEffect]
    average_confidence: float
    affected_genes: int

class Intervention(BaseModel):
    tf_id: str
    direction: str  # 'up', 'down'
    magnitude: float

class CascadeRequest(BaseModel):
    target_gene_id: str
    interventions: List[Intervention]
    depth: int = 3
    return_nodes: bool = True


class PathFindingRequest(BaseModel):
    source_gene_id: str
    target_symbol: str
    max_depth: int = 3
    limit: int = 20
    min_confidence: float = 0.3
    regulation_type: List[str] = ["activation", "repression"]

class NeighborhoodRequest(BaseModel):
    max_depth: int = 1
    direction: str = "both"
    regulation_type: List[str] = ["activation", "repression"]
    min_confidence: float = 0.3

# ============= Mock Database Service =============
# In production, replace this with actual database queries

class MockGeneDatabase:
    """Mock database service for demonstration"""
    
    def __init__(self):
        # Real data: subset of TRRUST v2 human TF-target interactions
        # (https://www.grnpedia.org/trrust/), centered on the TP53 regulatory
        # neighborhood. Gene names are TRRUST symbols (no full names/Ensembl
        # IDs in the source file). Confidence is a heuristic derived from
        # distinct-PubMed-reference count per pair, not a TRRUST-provided score.
        self.genes = {
            "BAX": Gene(id="BAX", symbol="BAX", name="BAX", species="human", is_tf=False, gene_type="protein_coding"),
            "BCL2": Gene(id="BCL2", symbol="BCL2", name="BCL2", species="human", is_tf=False, gene_type="protein_coding"),
            "BCL2L1": Gene(id="BCL2L1", symbol="BCL2L1", name="BCL2L1", species="human", is_tf=False, gene_type="protein_coding"),
            "BRCA2": Gene(id="BRCA2", symbol="BRCA2", name="BRCA2", species="human", is_tf=False, gene_type="protein_coding"),
            "CDKN1A": Gene(id="CDKN1A", symbol="CDKN1A", name="CDKN1A", species="human", is_tf=False, gene_type="protein_coding"),
            "DDB1": Gene(id="DDB1", symbol="DDB1", name="DDB1", species="human", is_tf=False, gene_type="protein_coding"),
            "DNMT1": Gene(id="DNMT1", symbol="DNMT1", name="DNMT1", species="human", is_tf=True, gene_type="protein_coding"),
            "DUSP1": Gene(id="DUSP1", symbol="DUSP1", name="DUSP1", species="human", is_tf=False, gene_type="protein_coding"),
            "E2F1": Gene(id="E2F1", symbol="E2F1", name="E2F1", species="human", is_tf=True, gene_type="protein_coding"),
            "EZH2": Gene(id="EZH2", symbol="EZH2", name="EZH2", species="human", is_tf=True, gene_type="protein_coding"),
            "GADD45A": Gene(id="GADD45A", symbol="GADD45A", name="GADD45A", species="human", is_tf=False, gene_type="protein_coding"),
            "ING1": Gene(id="ING1", symbol="ING1", name="ING1", species="human", is_tf=True, gene_type="protein_coding"),
            "KLF4": Gene(id="KLF4", symbol="KLF4", name="KLF4", species="human", is_tf=True, gene_type="protein_coding"),
            "MDM2": Gene(id="MDM2", symbol="MDM2", name="MDM2", species="human", is_tf=True, gene_type="protein_coding"),
            "MMP2": Gene(id="MMP2", symbol="MMP2", name="MMP2", species="human", is_tf=False, gene_type="protein_coding"),
            "MYCN": Gene(id="MYCN", symbol="MYCN", name="MYCN", species="human", is_tf=True, gene_type="protein_coding"),
            "NF1": Gene(id="NF1", symbol="NF1", name="NF1", species="human", is_tf=True, gene_type="protein_coding"),
            "PAX5": Gene(id="PAX5", symbol="PAX5", name="PAX5", species="human", is_tf=True, gene_type="protein_coding"),
            "PPARG": Gene(id="PPARG", symbol="PPARG", name="PPARG", species="human", is_tf=True, gene_type="protein_coding"),
            "SIRT1": Gene(id="SIRT1", symbol="SIRT1", name="SIRT1", species="human", is_tf=True, gene_type="protein_coding"),
            "TNFRSF10B": Gene(id="TNFRSF10B", symbol="TNFRSF10B", name="TNFRSF10B", species="human", is_tf=False, gene_type="protein_coding"),
            "TP53": Gene(id="TP53", symbol="TP53", name="TP53", species="human", is_tf=True, gene_type="protein_coding"),
            "YY1": Gene(id="YY1", symbol="YY1", name="YY1", species="human", is_tf=True, gene_type="protein_coding"),
        }

        self.interactions = {
            ("TP53", "CDKN1A"): {"regulation_type": "activation", "confidence": 0.95, "sources": ["TRRUST"]},
            ("TP53", "BAX"): {"regulation_type": "activation", "confidence": 0.95, "sources": ["TRRUST"]},
            ("TP53", "MDM2"): {"regulation_type": "activation", "confidence": 0.95, "sources": ["TRRUST"]},
            ("TP53", "BCL2"): {"regulation_type": "repression", "confidence": 0.95, "sources": ["TRRUST"]},
            ("SIRT1", "TP53"): {"regulation_type": "repression", "confidence": 0.8, "sources": ["TRRUST"]},
            ("TP53", "GADD45A"): {"regulation_type": "repression", "confidence": 0.8, "sources": ["TRRUST"]},
            ("TP53", "MMP2"): {"regulation_type": "activation", "confidence": 0.8, "sources": ["TRRUST"]},
            ("TP53", "TNFRSF10B"): {"regulation_type": "activation", "confidence": 0.8, "sources": ["TRRUST"]},
            ("YY1", "TP53"): {"regulation_type": "activation", "confidence": 0.8, "sources": ["TRRUST"]},
            ("E2F1", "TP53"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("ING1", "TP53"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("KLF4", "TP53"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("MYCN", "TP53"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("NF1", "TP53"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("PAX5", "TP53"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("PPARG", "TP53"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("TP53", "BCL2L1"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("TP53", "BRCA2"): {"regulation_type": "repression", "confidence": 0.7, "sources": ["TRRUST"]},
            ("TP53", "DDB1"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("TP53", "DNMT1"): {"regulation_type": "repression", "confidence": 0.7, "sources": ["TRRUST"]},
            ("TP53", "DUSP1"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("TP53", "EZH2"): {"regulation_type": "repression", "confidence": 0.7, "sources": ["TRRUST"]},
            ("KLF4", "CDKN1A"): {"regulation_type": "activation", "confidence": 0.95, "sources": ["TRRUST"]},
            ("SIRT1", "CDKN1A"): {"regulation_type": "repression", "confidence": 0.8, "sources": ["TRRUST"]},
            ("YY1", "TNFRSF10B"): {"regulation_type": "repression", "confidence": 0.8, "sources": ["TRRUST"]},
            ("E2F1", "BCL2"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("ING1", "BAX"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("ING1", "CDKN1A"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("PPARG", "BCL2"): {"regulation_type": "activation", "confidence": 0.7, "sources": ["TRRUST"]},
            ("DNMT1", "TNFRSF10B"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("E2F1", "CDKN1A"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("E2F1", "DNMT1"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("E2F1", "DUSP1"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("E2F1", "MDM2"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("E2F1", "MYCN"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("E2F1", "PPARG"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("EZH2", "CDKN1A"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("EZH2", "MMP2"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("EZH2", "TP53"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("KLF4", "MMP2"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("MYCN", "BAX"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("MYCN", "CDKN1A"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("PAX5", "BAX"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("PAX5", "BCL2"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("PAX5", "CDKN1A"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("PAX5", "MYCN"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("PPARG", "BCL2L1"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("PPARG", "CDKN1A"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("SIRT1", "EZH2"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("SIRT1", "PPARG"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("SIRT1", "TNFRSF10B"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("TP53", "E2F1"): {"regulation_type": "repression", "confidence": 0.6, "sources": ["TRRUST"]},
            ("TP53", "PAX5"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
            ("YY1", "NF1"): {"regulation_type": "activation", "confidence": 0.6, "sources": ["TRRUST"]},
        }
    
    def search_genes(self, query: str, limit: int = 10, species: Optional[str] = None) -> List[Gene]:
        """Search for genes by symbol or name"""
        results = []
        query_lower = query.lower()
        
        for gene in self.genes.values():
            if (query_lower in gene.symbol.lower() or 
                query_lower in gene.name.lower()):
                if species is None or gene.species == species:
                    results.append(gene)
                    if len(results) >= limit:
                        break
        
        return results
    
    def get_gene(self, gene_id: str) -> Optional[Gene]:
        """Get gene by ID"""
        return self.genes.get(gene_id)
    
    def get_regulators(self, gene_id: str, min_confidence: float = 0.0) -> List[GeneInteraction]:
        """Get regulators of a gene"""
        regulators = []
        
        for (source_id, target_id), interaction in self.interactions.items():
            if target_id == gene_id and interaction["confidence"] >= min_confidence:
                source_gene = self.genes.get(source_id)
                if source_gene:
                    regulators.append(GeneInteraction(
                        id=source_gene.id,
                        symbol=source_gene.symbol,
                        name=source_gene.name,
                        species=source_gene.species,
                        is_tf=source_gene.is_tf,
                        confidence=interaction["confidence"],
                        regulation_type=interaction["regulation_type"],
                        source_databases=interaction["sources"]
                    ))
        
        return regulators
    
    def get_targets(self, gene_id: str, min_confidence: float = 0.0) -> List[GeneInteraction]:
        """Get targets of a gene"""
        targets = []
        
        for (source_id, target_id), interaction in self.interactions.items():
            if source_id == gene_id and interaction["confidence"] >= min_confidence:
                target_gene = self.genes.get(target_id)
                if target_gene:
                    targets.append(GeneInteraction(
                        id=target_gene.id,
                        symbol=target_gene.symbol,
                        name=target_gene.name,
                        species=target_gene.species,
                        is_tf=target_gene.is_tf,
                        confidence=interaction["confidence"],
                        regulation_type=interaction["regulation_type"],
                        source_databases=interaction["sources"]
                    ))
        
        return targets

# Initialize database
db = MockGeneDatabase()

# ============= Root Endpoint =============

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "name": "GRN Atlas API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

# ============= Gene Search Endpoints =============

@app.get("/api/v1/genes/search", response_model=Dict[str, List[Gene]])
async def search_genes(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, le=50, description="Maximum results"),
    species: Optional[str] = Query(None, description="Filter by species")
):
    """
    Search for genes by symbol or name
    
    - **q**: Search query (gene symbol or name)
    - **limit**: Maximum number of results (1-50)
    - **species**: Optional species filter
    """
    try:
        results = db.search_genes(q, limit, species)
        return {"results": results}
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.get("/api/v1/genes/{gene_id}", response_model=Gene)
async def get_gene(gene_id: str):
    """
    Get gene details by Ensembl ID
    """
    gene = db.get_gene(gene_id)
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")
    return gene

@app.get("/api/v1/genes/symbol/{symbol}", response_model=Gene)
async def get_gene_by_symbol(symbol: str):
    """
    Get gene details by symbol
    """
    results = db.search_genes(symbol, limit=1)
    if not results:
        raise HTTPException(status_code=404, detail="Gene not found")
    return results[0]

# ============= Pathway Endpoints =============

@app.post("/api/v1/pathways/neighborhood/{gene_id}", response_model=NetworkData)
async def get_neighborhood(gene_id: str, request: NeighborhoodRequest = NeighborhoodRequest()):
    """
    Get regulatory neighborhood around a gene

    - **gene_id**: Target gene Ensembl ID
    - **max_depth**: Maximum network hops (1-5)
    - **direction**: 'both', 'regulators', or 'targets'
    - **regulation_type**: Filter by regulation type
    - **min_confidence**: Minimum confidence score (0.3-0.9)
    """
    gene = db.get_gene(gene_id)
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # Get regulators and targets
    regulators = db.get_regulators(gene_id, request.min_confidence) if request.direction in ["both", "regulators"] else []
    targets = db.get_targets(gene_id, request.min_confidence) if request.direction in ["both", "targets"] else []

    # Filter by regulation type
    regulators = [r for r in regulators if r.regulation_type in request.regulation_type]
    targets = [t for t in targets if t.regulation_type in request.regulation_type]
    
    return NetworkData(
        gene=gene,
        regulators=regulators,
        targets=targets,
        stats={
            "regulators": len(regulators),
            "targets": len(targets),
            "paths": 0  # Can be calculated from path finding algorithm
        }
    )
@app.post("/api/v1/pathways/pathfinding", response_model=Dict[str, List[Path]])
async def find_paths(request: PathFindingRequest):
    """
    Find regulatory paths between two genes using BFS algorithm
    """
    source = db.get_gene(request.source_gene_id)
    target_results = db.search_genes(request.target_symbol, limit=1)
    
    if not source or not target_results:
        raise HTTPException(status_code=404, detail="Gene not found")
    
    target_gene = target_results[0]
    
    # Simple BFS pathfinding (in production, use more sophisticated algorithm)
    paths = []
    visited = set()
    queue = [(request.source_gene_id, [source], [], [])]
    
    while queue and len(paths) < request.limit:
        current_id, current_path, regulations, confidences = queue.pop(0)
        
        if current_id == target_gene.id:
            path_genes = [PathGene(id=g.id, symbol=g.symbol, name=g.name) for g in current_path]
            sources = [["TRRUST"] for _ in regulations]
            paths.append(Path(
                genes=path_genes,
                regulation_types=regulations,
                confidences=confidences,
                sources=sources,
                overall_confidence=sum(confidences) / len(confidences) if confidences else 0.0
            ))
            continue
        
        if len(current_path) < request.max_depth:
            targets = db.get_targets(current_id, request.min_confidence)
            for target in targets:
                if target.id not in visited and target.regulation_type in request.regulation_type:
                    visited.add(target.id)
                    target_gene_obj = db.get_gene(target.id)
                    if target_gene_obj:
                        queue.append((
                            target.id,
                            current_path + [target_gene_obj],
                            regulations + [target.regulation_type],
                            confidences + [target.confidence]
                        ))
    
    return {"paths": paths}

@app.post("/api/v1/pathway/predict-cascade", response_model=CascadeResult)
async def predict_cascade(request: CascadeRequest):
    """
    Predict cascade effects of regulatory interventions

    Simulates regulatory cascade using simple propagation model
    """
    if not request.interventions:
        raise HTTPException(status_code=400, detail="At least one intervention required")

    gene = db.get_gene(request.target_gene_id)
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    cascade_effects = []

    # Simple cascade simulation - in production, use ODE/boolean network model
    targets = db.get_targets(request.target_gene_id, min_confidence=0.5)
    for i, target in enumerate(targets[:5]):  # Limit to first 5 targets
        # Calculate cascade magnitude based on interventions
        magnitude = 1.0
        for intervention in request.interventions:
            if intervention.direction == "up":
                magnitude *= intervention.magnitude
            else:
                magnitude *= (2.0 - intervention.magnitude)
        
        cascade_effects.append(CascadeEffect(
            id=target.id,
            symbol=target.symbol,
            level=1,
            direction="up" if magnitude > 1.0 else "down",
            magnitude=abs(magnitude),
            confidence=target.confidence * 0.95  # Slightly reduced confidence for predictions
        ))
    
    return CascadeResult(
        cascade=cascade_effects,
        average_confidence=sum(e.confidence for e in cascade_effects) / len(cascade_effects) if cascade_effects else 0.0,
        affected_genes=len(cascade_effects)
    )

# ============= Orthology Endpoints =============

@app.get("/api/v1/genes/orthology/{gene_id}")
async def get_orthology(
    gene_id: str,
    species: Optional[str] = Query(None, description="Comma-separated species list")
):
    """
    Get orthologous genes and their regulatory networks across species
    """
    gene = db.get_gene(gene_id)
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")
    
    # Parse species list
    target_species = species.split(",") if species else ["human", "arabidopsis", "rice"]
    
    result = {}
    for sp in target_species:
        regulators = db.get_regulators(gene_id, min_confidence=0.5)
        targets = db.get_targets(gene_id, min_confidence=0.5)
        
        result[sp] = {
            "ortholog_symbol": gene.symbol,  # In production, lookup actual ortholog
            "regulators": [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "is_tf": r.is_tf,
                    "confidence": r.confidence,
                    "regulation_type": r.regulation_type
                }
                for r in regulators
            ],
            "targets": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "is_tf": t.is_tf,
                    "confidence": t.confidence,
                    "regulation_type": t.regulation_type
                }
                for t in targets
            ]
        }
    
    return result

# ============= Statistics Endpoints =============

@app.get("/api/v1/stats")
async def get_stats():
    """Get overall database statistics"""
    return {
        "species": 21,
        "genes": 591000,
        "interactions": 6700000,
        "databases": ["TRRUST", "DoRothEA", "PlantRegMap", "JASPAR"],
        "last_updated": "2024-01-15",
        "version": "1.0.0"
    }

@app.get("/api/v1/stats/species/{species}")
async def get_species_stats(species: str):
    """Get species-specific statistics"""
    species_stats = {
        "human": {"genes": 20000, "transcription_factors": 1500, "interactions": 250000},
        "arabidopsis": {"genes": 27000, "transcription_factors": 1800, "interactions": 120000},
        "rice": {"genes": 40000, "transcription_factors": 2000, "interactions": 180000},
    }
    
    if species not in species_stats:
        raise HTTPException(status_code=404, detail="Species not found")
    
    return {
        "species": species,
        **species_stats[species]
    }

# ============= Error Handlers =============

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return {
        "error": exc.detail,
        "status_code": exc.status_code
    }

# ============= Startup Events =============

@app.on_event("startup")
async def startup_event():
    logger.info("GRN Atlas API starting up...")
    logger.info("Database initialized with mock data")
    logger.info("CORS enabled for frontend development")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("GRN Atlas API shutting down...")

# ============= Health Check Endpoint =============

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
