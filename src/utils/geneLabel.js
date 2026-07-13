// Pick the friendliest short label for a gene. Human/mouse ids ARE symbols; tomato/
// petunia genes have no native symbol (their `symbol` is the locus id), so fall back to
// the best inferred Arabidopsis-ortholog synonym, flagged as inferred so it is never
// mistaken for a curated symbol.
//
// Prefers the backend-computed `label`/`label_inferred` when present (single source of
// truth); otherwise replicates the same logic client-side.

function rankSynonym(syns) {
  let best = null, bestKey = null;
  for (const raw of syns || []) {
    const s = String(raw).trim();
    if (s.length < 2 || s.length > 10) continue;
    const alpha = [...s].filter((c) => /[a-z]/i.test(c)).length / s.length;
    const key = [Math.round(alpha * 100) / 100, -s.length]; // more alphabetic, then shorter
    if (!bestKey || key[0] > bestKey[0] || (key[0] === bestKey[0] && key[1] > bestKey[1])) {
      best = s; bestKey = key;
    }
  }
  return best;
}

export function geneLabel(gene) {
  if (!gene) return { label: '', inferred: false, id: '' };
  const id = gene.id || gene.symbol || '';
  // trust the backend if it computed a label
  if (gene.label) return { label: gene.label, inferred: !!gene.label_inferred, id };
  if (gene.symbol && gene.symbol !== id) return { label: gene.symbol, inferred: false, id };
  const syns = Array.isArray(gene.synonyms)
    ? gene.synonyms
    : (typeof gene.synonyms === 'string' ? gene.synonyms.split(/;\s*/) : null);
  const best = rankSynonym(syns);
  if (best) return { label: best, inferred: true, id };
  return { label: gene.symbol || id, inferred: false, id };
}
