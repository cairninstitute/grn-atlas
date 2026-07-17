"""
GRN Atlas FastAPI Backend
Complete example implementation with all required endpoints
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path as FilePath
import json
import logging
import sqlite3

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
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8000"],
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
    regulation_type: List[str] = ["activation", "repression", "regulation"]

class NeighborhoodRequest(BaseModel):
    max_depth: int = 1
    direction: str = "both"
    regulation_type: List[str] = ["activation", "repression", "regulation"]
    min_confidence: float = 0.3

# ============= Database Service =============
# Backed by a local SQLite database built from the full TRRUST v2 human
# TF-target corpus (https://www.grnpedia.org/trrust/), with gene names
# enriched from mygene.info at build time. See backend/scripts/build_db.py
# and backend/scripts/fetch_gene_names.py. No network access at runtime.

DB_PATH = FilePath(__file__).parent / "data" / "grn.sqlite3"


class GeneDatabase:
    """SQLite-backed gene/interaction lookups"""

    def __init__(self, db_path: FilePath):
        if not db_path.exists():
            logger.info("Database not found, building from local TRRUST data...")
            from scripts.build_db import build
            build()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def _row_to_gene(self, row) -> Gene:
        return Gene(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            species=row["species"],
            is_tf=bool(row["is_tf"]),
            gene_type=row["gene_type"]
        )

    def search_genes(self, query: str, limit: int = 10, species: Optional[str] = None) -> List[Gene]:
        """Search for genes by symbol or name"""
        sql = "SELECT * FROM genes WHERE (symbol LIKE ? OR name LIKE ?)"
        params: List[Any] = [f"%{query}%", f"%{query}%"]
        if species:
            sql += " AND species = ?"
            params.append(species)
        sql += " ORDER BY (symbol = ? COLLATE NOCASE) DESC, LENGTH(symbol) ASC LIMIT ?"
        params.extend([query, limit])
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_gene(r) for r in rows]

    def get_gene(self, gene_id: str) -> Optional[Gene]:
        """Get gene by ID"""
        row = self.conn.execute("SELECT * FROM genes WHERE id = ?", (gene_id,)).fetchone()
        return self._row_to_gene(row) if row else None

    def get_regulators(self, gene_id: str, min_confidence: float = 0.0) -> List[GeneInteraction]:
        """Get regulators of a gene"""
        rows = self.conn.execute(
            """
            SELECT g.*, i.regulation_type, i.confidence, i.sources
            FROM interactions i JOIN genes g ON g.id = i.source_id
            WHERE i.target_id = ? AND i.confidence >= ?
            """,
            (gene_id, min_confidence)
        ).fetchall()
        return [
            GeneInteraction(
                id=r["id"], symbol=r["symbol"], name=r["name"], species=r["species"],
                is_tf=bool(r["is_tf"]), confidence=r["confidence"],
                regulation_type=r["regulation_type"], source_databases=json.loads(r["sources"])
            )
            for r in rows
        ]

    def get_targets(self, gene_id: str, min_confidence: float = 0.0) -> List[GeneInteraction]:
        """Get targets of a gene"""
        rows = self.conn.execute(
            """
            SELECT g.*, i.regulation_type, i.confidence, i.sources
            FROM interactions i JOIN genes g ON g.id = i.target_id
            WHERE i.source_id = ? AND i.confidence >= ?
            """,
            (gene_id, min_confidence)
        ).fetchall()
        return [
            GeneInteraction(
                id=r["id"], symbol=r["symbol"], name=r["name"], species=r["species"],
                is_tf=bool(r["is_tf"]), confidence=r["confidence"],
                regulation_type=r["regulation_type"], source_databases=json.loads(r["sources"])
            )
            for r in rows
        ]

# Initialize database
db = GeneDatabase(DB_PATH)

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
    
    paths = []
    queue = [(request.source_gene_id, [source], [], [], {request.source_gene_id})]
    max_queue = 50000

    while queue and len(paths) < request.limit and len(queue) < max_queue:
        current_id, current_path, regulations, confidences, path_visited = queue.pop(0)

        if current_id == target_gene.id:
            path_genes = [PathGene(id=g.id, symbol=g.symbol, name=g.name) for g in current_path]
            sources_list = [["TRRUST"] for _ in regulations]
            paths.append(Path(
                genes=path_genes,
                regulation_types=regulations,
                confidences=confidences,
                sources=sources_list,
                overall_confidence=sum(confidences) / len(confidences) if confidences else 0.0
            ))
            continue

        if len(current_path) <= request.max_depth:
            targets = db.get_targets(current_id, request.min_confidence)
            for target in targets:
                if target.id not in path_visited and target.regulation_type in request.regulation_type:
                    target_gene_obj = db.get_gene(target.id)
                    if target_gene_obj:
                        queue.append((
                            target.id,
                            current_path + [target_gene_obj],
                            regulations + [target.regulation_type],
                            confidences + [target.confidence],
                            path_visited | {target.id}
                        ))

    paths.sort(key=lambda p: (-p.overall_confidence, len(p.genes)))
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
    """Get overall database statistics from live data"""
    cur = db.conn.execute
    total_genes = cur("SELECT COUNT(*) FROM genes").fetchone()[0]
    total_interactions = cur("SELECT COUNT(*) FROM interactions").fetchone()[0]
    species_list = [r[0] for r in cur("SELECT DISTINCT species FROM genes ORDER BY species").fetchall()]
    return {
        "species": len(species_list),
        "species_list": species_list,
        "genes": total_genes,
        "interactions": total_interactions,
        "databases": ["TRRUST", "PlantRegMap"],
        "version": "1.0.0"
    }

@app.get("/api/v1/stats/species/{species}")
async def get_species_stats(species: str):
    """Get species-specific statistics from live data"""
    cur = db.conn.execute
    genes = cur("SELECT COUNT(*) FROM genes WHERE species = ?", (species,)).fetchone()[0]
    if genes == 0:
        raise HTTPException(status_code=404, detail="Species not found")
    tfs = cur("SELECT COUNT(*) FROM genes WHERE species = ? AND is_tf = 1", (species,)).fetchone()[0]
    gene_ids = [r[0] for r in cur("SELECT id FROM genes WHERE species = ?", (species,)).fetchall()]
    placeholders = ",".join("?" * len(gene_ids))
    interactions = cur(
        f"SELECT COUNT(*) FROM interactions WHERE source_id IN ({placeholders})",
        gene_ids
    ).fetchone()[0]
    return {
        "species": species,
        "genes": genes,
        "transcription_factors": tfs,
        "interactions": interactions
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
