"""External literature retrieval and lightweight evidence classification."""

from __future__ import annotations

import json
from datetime import datetime
import re
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any


EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SUPPORT_WORDS = ("activate", "activates", "regulate", "regulates", "induces", "promotes", "supports", "required")
CONTRADICT_WORDS = ("not", "independent", "fails", "contrary", "repress", "represses", "inhibit", "inhibits", "no effect")
PHENOTYPE_DIRECT_WORDS = ("petunia", "flower color", "floral pigmentation", "anthocyanin", "corolla", "petal")
PHENOTYPE_COMPARATIVE_WORDS = ("ornamental", "allies", "related species", "comparative", "evolutionary", "engineering")
PHENOTYPE_MECHANISTIC_WORDS = ("myb", "bhlh", "wd40", "anthocyanin", "flavonoid", "pigment", "biosynthetic", "regulator")
GENE_TOKEN_RE = re.compile(r"\b(?:[A-Z][a-z]{0,4}[A-Z0-9][A-Za-z0-9'-]{1,15}|[A-Z][A-Z0-9'-]{1,15})\b")
PHENOTYPE_STOPWORDS = {
    "DNA", "RNA", "RNAI", "CRISPR", "TPM", "PCR", "AND", "THE", "FOR", "WITH", "SEQ", "ANALYSES",
    "ANALYSIS", "MODULE", "GENE", "GENES", "TARGET", "TARGETS", "CONTROL", "COLOR", "FLOWER",
    "RNA-SEQ", "DAP-SEQ", "CHIP-SEQ", "ATAC-SEQ",
}
PHENOTYPE_GENERIC_GENE_TERMS = {
    "MYB", "R2R3-MYB", "R3-MYB", "BHLH", "WD40", "DP", "EBG", "LBG", "MBW", "TF", "TFS",
}
PHENOTYPE_DESCRIPTIVE_SUFFIXES = {
    "CENTERED", "MEDIATED", "DEPENDENT", "DEPENDENTLY", "ASSOCIATED", "RELATED", "RESPONSIVE",
    "LIKE", "TYPE", "INDUCED", "MODULE", "CONTROLLED", "TARGETED",
}


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
        if scope == "phenotype":
            rewritten = _rewrite_phenotype_query(query, species)
            meta["rewritten_query"] = rewritten
            return rewritten, meta
        return query, meta
    raise ValueError("insufficient query parameters for requested scope")


def _rewrite_phenotype_query(query: str, species: str | None = None) -> str:
    q = (query or "").strip()
    ql = q.lower()
    species_term = (species or "").strip()
    if "flower color" in ql or ("flower" in ql and "color" in ql) or "pigment" in ql:
        parts = [species_term, "flower color pigmentation anthocyanin regulator gene target"]
        if "petunia" not in ql and species_term:
            parts.append("petunia")
        parts.append("MYB OR bHLH OR WD40 OR DFR OR CHS")
        return " ".join(p for p in parts if p)
    if species_term and species_term.lower() not in ql:
        return f"{species_term} {q}"
    return q


def _classify_phenotype_text(text: str, species: str | None = None) -> tuple[str, float]:
    body = (text or "").lower()
    direct_hits = sum(1 for w in PHENOTYPE_DIRECT_WORDS if w in body)
    comparative_hits = sum(1 for w in PHENOTYPE_COMPARATIVE_WORDS if w in body)
    mechanistic_hits = sum(1 for w in PHENOTYPE_MECHANISTIC_WORDS if w in body)
    species_hits = 1 if species and species.lower() in body else 0
    if direct_hits + species_hits >= 2:
        return "direct_phenotype_evidence", min(0.95, 0.45 + 0.1 * (direct_hits + species_hits))
    if comparative_hits > 0 and mechanistic_hits > 0:
        return "comparative_evidence", min(0.9, 0.42 + 0.08 * (comparative_hits + mechanistic_hits))
    if mechanistic_hits > 0:
        return "mechanistic_background", min(0.85, 0.38 + 0.07 * mechanistic_hits)
    return "low_relevance", 0.25


def _normalize_candidate_token(token: str) -> str | None:
    cleaned = (token or "").strip(".,;:()[]{}\"'")
    if not cleaned:
        return None
    if "-" in cleaned:
        parts = [part for part in cleaned.split("-") if part]
        while len(parts) > 1:
            tail = parts[-1]
            tail_upper = tail.upper()
            tail_has_digit = any(ch.isdigit() for ch in tail)
            tail_has_apostrophe = "'" in tail
            tail_is_descriptive = tail_upper in PHENOTYPE_DESCRIPTIVE_SUFFIXES
            tail_is_gene_like = tail_has_digit or tail_has_apostrophe or tail_upper == tail
            if tail_is_descriptive or not tail_is_gene_like:
                parts.pop()
                continue
            break
        cleaned = "-".join(parts)
        if not cleaned:
            return None
    upper = cleaned.upper()
    if upper in PHENOTYPE_STOPWORDS or upper in PHENOTYPE_GENERIC_GENE_TERMS:
        return None
    if upper.endswith("-SEQ"):
        return None
    if cleaned.endswith("-") or cleaned.startswith("-"):
        return None
    if len(cleaned) < 3:
        return None
    alpha_count = sum(ch.isalpha() for ch in cleaned)
    digit_count = sum(ch.isdigit() for ch in cleaned)
    if alpha_count == 0:
        return None
    if digit_count == 0 and "'" not in cleaned:
        if upper != cleaned:
            return None
        if len(cleaned) > 5 and "-" not in cleaned:
            return None
    if cleaned.count("-") > 1:
        return None
    return cleaned


def _extract_candidate_entities(records: list[dict[str, Any]]) -> dict[str, Any]:
    gene_counts: Counter[str] = Counter()
    mechanism_counts: Counter[str] = Counter()
    mechanism_terms = ("anthocyanin", "flavonoid", "pigment", "myb", "bhlh", "wd40", "dfr", "chs", "regulator")
    for rec in records:
        title = rec.get("title") or ""
        abstract = rec.get("abstractText") or ""
        classification, _ = _classify_phenotype_text(f"{title} {abstract}")
        weight = 3 if classification == "direct_phenotype_evidence" else 2 if classification == "comparative_evidence" else 1
        text = f"{title} {abstract}"
        for token in GENE_TOKEN_RE.findall(text):
            normalized = _normalize_candidate_token(token)
            if not normalized:
                continue
            gene_counts[normalized] += weight
        lower = text.lower()
        for term in mechanism_terms:
            if term in lower:
                mechanism_counts[term] += 1
    return {
        "candidate_genes": [{"name": k, "mentions": v} for k, v in gene_counts.most_common(8)],
        "mechanisms": [{"name": k, "mentions": v} for k, v in mechanism_counts.most_common(8)],
    }


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
            "summary": {"support": 0, "contradict": 0, "mention": 0} if scope != "phenotype" else {
                "direct_phenotype_evidence": 0,
                "comparative_evidence": 0,
                "mechanistic_background": 0,
                "low_relevance": 0,
            },
            "candidate_summary": {"candidate_genes": [], "mechanisms": []} if scope == "phenotype" else None,
            "warnings": [f"literature lookup failed: {e}"],
            **meta,
        }

    out = []
    counts = {"support": 0, "contradict": 0, "mention": 0} if scope != "phenotype" else {
        "direct_phenotype_evidence": 0,
        "comparative_evidence": 0,
        "mechanistic_background": 0,
        "low_relevance": 0,
    }
    for rec in records[:max_results]:
        title = rec.get("title") or ""
        abstract = rec.get("abstractText") or ""
        if scope == "phenotype":
            classification, confidence = _classify_phenotype_text(f"{title} {abstract}", species)
        else:
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
    candidate_summary = _extract_candidate_entities(records[:max_results]) if scope == "phenotype" else None
    return {
        "scope": scope,
        "search_term": term,
        "years_back": years_back,
        "atlas_boundary": "This endpoint retrieves external literature and does not replace atlas-backed evidence.",
        "results": out,
        "summary": counts,
        "candidate_summary": candidate_summary,
        "warnings": warnings,
        **meta,
    }
