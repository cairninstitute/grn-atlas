"""Pure gene-label logic (no FastAPI / no DB) so it is unit-testable in isolation.

A gene's display label is its native symbol when it has one; otherwise the best-ranked
inferred ortholog synonym (flagged inferred), preferring short, mostly-alphabetic tokens
(so 'DFR' beats 'BEN1'/'M318'); otherwise the locus id. Never invents a symbol.
"""
from typing import List, Optional, Tuple


def rank_synonym(syns: Optional[List[str]]) -> Optional[str]:
    """Most symbol-like synonym: prefer short, mostly-alphabetic tokens. None if unusable."""
    best, best_key = None, None
    for s in syns or []:
        s = (s or "").strip()
        if not (2 <= len(s) <= 10):
            continue
        alpha = sum(c.isalpha() for c in s) / len(s)
        key = (round(alpha, 2), -len(s))          # more alphabetic, then shorter
        if best_key is None or key > best_key:
            best, best_key = s, key
    return best


def friendly_label(symbol: Optional[str], gene_id: str,
                   synonyms: Optional[List[str]]) -> Tuple[str, bool]:
    """(label, inferred). Native symbol if present; else the best inferred synonym
    (flagged); else the locus id."""
    if symbol and symbol != gene_id:
        return symbol, False
    best = rank_synonym(synonyms)
    if best:
        return best, True
    return symbol or gene_id, False
