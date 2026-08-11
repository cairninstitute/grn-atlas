"""External literature retrieval and lightweight evidence classification."""

from __future__ import annotations

import json
from datetime import datetime
import urllib.parse
import urllib.request
from typing import Any


EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SUPPORT_WORDS = ("activate", "activates", "regulate", "regulates", "induces", "promotes", "supports", "required")
CONTRADICT_WORDS = ("not", "independent", "fails", "contrary", "repress", "represses", "inhibit", "inhibits", "no effect")


def _classify_text(text: str, source_symbol: str | None = None, target_symbol: str | None = None) -> tuple[str, float]:
    body = (text or "").lower()
    support_hits = sum(1 for w in SUPPORT_WORDS if w in body)
    contradict_hits = sum(1 for w in CONTRADICT_WORDS if w in body)
    if source_symbol and target_symbol:
        s = source_symbol.lower()
        t = target_symbol.lower()
        if s in body and t in body:
            support_hits += 1
        if f"independent of {s}" in body or f"independent from {s}" in body:
            contradict_hits += 2
        if f"no effect of {s}" in body or f"fails to activate {t}" in body:
            contradict_hits += 2
    if contradict_hits > support_hits:
        return "contradict", min(0.9, 0.4 + 0.1 * contradict_hits)
    if support_hits > 0:
        return "support", min(0.9, 0.4 + 0.08 * support_hits)
    return "mention", 0.35


def _query_for_scope(db, scope: str, gene_id: str | None = None, source_id: str | None = None,
                     target_id: str | None = None, query: str | None = None, species: str | None = None) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {"scope": scope}
    if scope == "gene" and gene_id:
        gene = db.get_gene(gene_id)
        label = gene.symbol if gene else gene_id
        meta["gene"] = {"gene_id": gene_id, "symbol": label, "species": getattr(gene, "species", species)}
        return f'"{label}"', meta
    if scope == "edge" and source_id and target_id:
        src = db.get_gene(source_id)
        tgt = db.get_gene(target_id)
        src_label = src.symbol if src else source_id
        tgt_label = tgt.symbol if tgt else target_id
        meta["edge"] = {
            "source_id": source_id, "source_symbol": src_label,
            "target_id": target_id, "target_symbol": tgt_label,
            "species": species or getattr(src, "species", None),
        }
        return f'"{src_label}" AND "{tgt_label}" AND (regulat* OR activ* OR repress* OR interact*)', meta
    if scope in {"pathway", "phenotype"} and query:
        meta["query"] = query
        return query, meta
    raise ValueError("insufficient query parameters for requested scope")


def search_europe_pmc(term: str, years_back: int = 5, page_size: int = 10) -> list[dict[str, Any]]:
    q = term
    if years_back > 0:
        this_year = datetime.utcnow().year
        q = f"{term} AND FIRST_PDATE:[{this_year - years_back}:{this_year}]"
    params = {
        "query": q,
        "format": "json",
        "pageSize": min(max(page_size, 1), 50),
        "resultType": "core",
    }
    url = f"{EUROPE_PMC_SEARCH}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("resultList", {}).get("result", [])


def review_literature(db, scope: str, gene_id: str | None = None, source_id: str | None = None,
                      target_id: str | None = None, query: str | None = None,
                      species: str | None = None, years_back: int = 5,
                      max_results: int = 10) -> dict[str, Any]:
    term, meta = _query_for_scope(db, scope, gene_id, source_id, target_id, query, species)
    source_symbol = meta.get("edge", {}).get("source_symbol")
    target_symbol = meta.get("edge", {}).get("target_symbol")
    try:
        records = search_europe_pmc(term, years_back=years_back, page_size=max_results)
        warnings: list[str] = []
    except Exception as e:
        return {
            "scope": scope,
            "search_term": term,
            "atlas_boundary": "This endpoint retrieves external literature and does not replace atlas-backed evidence.",
            "results": [],
            "summary": {"support": 0, "contradict": 0, "mention": 0},
            "warnings": [f"literature lookup failed: {e}"],
            **meta,
        }

    out = []
    counts = {"support": 0, "contradict": 0, "mention": 0}
    for rec in records[:max_results]:
        title = rec.get("title") or ""
        abstract = rec.get("abstractText") or ""
        classification, confidence = _classify_text(f"{title} {abstract}", source_symbol, target_symbol)
        counts[classification] += 1
        out.append({
            "title": title,
            "pmid": rec.get("pmid"),
            "doi": rec.get("doi"),
            "journal": rec.get("journalTitle"),
            "year": rec.get("pubYear"),
            "authors": rec.get("authorString"),
            "source": rec.get("source"),
            "classification": classification,
            "classification_confidence": round(confidence, 3),
            "snippet": abstract[:400] if abstract else None,
            "url": f"https://europepmc.org/article/{rec.get('source')}/{rec.get('id')}" if rec.get("source") and rec.get("id") else None,
        })
    return {
        "scope": scope,
        "search_term": term,
        "years_back": years_back,
        "atlas_boundary": "This endpoint retrieves external literature and does not replace atlas-backed evidence.",
        "results": out,
        "summary": counts,
        "warnings": warnings,
        **meta,
    }
