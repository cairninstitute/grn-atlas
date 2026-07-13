"""Petunia expression matrix access + co-expression inference (#1, #2).

Loads the committed `expression_<species>.json.gz` (built by
scripts/fetch_expression.py) and provides:
  - per-gene expression profiles across the sample panel (#1)
  - Pearson co-expression neighbours on log2(TPM+1) (#2 network inference)

Co-expression is a *predicted, undirected* association — it is NOT measured
regulation and does not establish causal direction or activation/repression. It is
labelled distinctly (`Inferred:Expression`) everywhere it surfaces.

Pure functions here (no FastAPI) so they are unit-testable in isolation.
"""
import gzip
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "expression_petunia.json.gz"


class ExpressionMatrix:
    def __init__(self, data: dict):
        self.meta = data.get("meta", {})
        self.samples = data.get("samples", [])
        self.genes: Dict[str, List[float]] = data.get("genes", {})
        self.n = len(self.samples)
        # Precompute log2(TPM+1), mean-centred vector, and norm per gene for Pearson r.
        self._centered: Dict[str, List[float]] = {}
        self._norm: Dict[str, float] = {}
        self._mean_tpm: Dict[str, float] = {}
        for g, tpm in self.genes.items():
            self._mean_tpm[g] = sum(tpm) / self.n if self.n else 0.0
            log = [math.log2(v + 1.0) for v in tpm]
            mu = sum(log) / self.n if self.n else 0.0
            c = [x - mu for x in log]
            norm = math.sqrt(sum(x * x for x in c))
            self._centered[g] = c
            self._norm[g] = norm

    def has(self, gene_id: str) -> bool:
        return gene_id in self.genes

    def profile(self, gene_id: str) -> Optional[dict]:
        if gene_id not in self.genes:
            return None
        tpm = self.genes[gene_id]
        return {
            "gene_id": gene_id,
            "unit": "TPM",
            "mean_tpm": round(self._mean_tpm[gene_id], 3),
            "max_tpm": round(max(tpm), 3) if tpm else 0.0,
            "samples": [{**s, "tpm": tpm[i]} for i, s in enumerate(self.samples)],
        }

    def _pearson(self, a: str, b: str) -> Optional[float]:
        na, nb = self._norm[a], self._norm[b]
        if na == 0 or nb == 0:
            return None
        ca, cb = self._centered[a], self._centered[b]
        dot = sum(x * y for x, y in zip(ca, cb))
        return dot / (na * nb)

    def coexpressed(self, gene_id: str, top: int = 25, min_abs_r: float = 0.7,
                    min_expr: float = 5.0,
                    candidates: Optional[List[str]] = None) -> List[dict]:
        """Genes whose log-expression correlates with `gene_id` across the panel.

        min_expr filters out low-expressed noisy genes (mean TPM). Returns items
        sorted by |r|, each with relationship co-expressed / anti-correlated.
        """
        if gene_id not in self.genes or self._norm[gene_id] == 0:
            return []
        pool = candidates if candidates is not None else self.genes.keys()
        out = []
        for g in pool:
            if g == gene_id or g not in self.genes:
                continue
            if self._mean_tpm[g] < min_expr:
                continue
            r = self._pearson(gene_id, g)
            if r is None or abs(r) < min_abs_r:
                continue
            out.append({"gene_id": g, "r": round(r, 4),
                        "mean_tpm": round(self._mean_tpm[g], 3),
                        "relationship": "co-expressed" if r > 0 else "anti-correlated"})
        out.sort(key=lambda x: abs(x["r"]), reverse=True)
        return out[:top]


DATA_DIR = DEFAULT_PATH.parent


def path_for(species: str) -> Path:
    return DATA_DIR / f"expression_{species}.json.gz"


_cache: Dict[str, Optional[ExpressionMatrix]] = {}


def get_matrix(species: str = "petunia") -> Optional[ExpressionMatrix]:
    """Lazy-load + cache the expression matrix for a species; None if not built.

    Cached by file path so tests can pre-seed `_cache[str(path_for(sp))]`.
    """
    path = path_for(species)
    key = str(path)
    if key not in _cache:
        if not path.exists():
            _cache[key] = None
        else:
            with gzip.open(path, "rt") as fh:
                _cache[key] = ExpressionMatrix(json.load(fh))
    return _cache[key]


def species_with_expression() -> list:
    """Species that currently have a built expression matrix."""
    return sorted(p.name[len("expression_"):-len(".json.gz")]
                  for p in DATA_DIR.glob("expression_*.json.gz"))
