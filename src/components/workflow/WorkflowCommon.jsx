import React from 'react';
import { geneLabel } from '../../utils/geneLabel';

export function splitTokens(text) {
  return text.split(/[\s,;]+/).map((token) => token.trim()).filter(Boolean);
}

export function parseAssayText(text) {
  return text.split(',').map((token) => token.trim()).filter(Boolean);
}

export function JsonPreview({ title, data, defaultOpen = false }) {
  if (!data) return null;
  return (
    <details className="workflow-json" open={defaultOpen}>
      <summary>{title}</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

export function StatusPill({ tone = 'neutral', children }) {
  return <span className={`workflow-pill workflow-pill-${tone}`}>{children}</span>;
}

export function describeGene(item, labelOverrides = {}) {
  if (!item) return { primary: '', secondary: '', inferred: false };
  if (typeof item === 'string') return { primary: item, secondary: '', inferred: false };
  const id = item.gene_id || item.id || item.symbol || '';
  const override = id ? labelOverrides[id] : null;
  const { label, inferred } = geneLabel({
    ...item,
    id,
    symbol: item.symbol || id,
    label: override?.label || item.label,
    label_inferred: override?.label_inferred ?? item.label_inferred,
  });
  const primary = label || item.symbol || id;
  const secondary = id && id !== primary ? id : '';
  return { primary, secondary, inferred };
}

export function GeneBadge({ item, labelOverrides }) {
  const { primary, secondary, inferred } = describeGene(item, labelOverrides);
  const inferredTitle = inferred
    ? 'Inferred label from orthology or synonym context; not a native curated symbol for this species.'
    : undefined;
  return (
    <span className={`workflow-gene-badge${inferred ? ' workflow-gene-badge-inferred' : ''}`} title={inferredTitle}>
      <strong>{primary}</strong>
      {secondary && <span className="workflow-faint"> · {secondary}</span>}
    </span>
  );
}

export function differentialDirectionText(item, groupA, groupB) {
  const a = groupA?.join(', ') || 'Group A';
  const b = groupB?.join(', ') || 'Group B';
  if ((item?.log2fc ?? 0) < 0) return `higher in ${a}`;
  if ((item?.log2fc ?? 0) > 0) return `higher in ${b}`;
  return 'similar in both groups';
}

export function ResultList({ title, items, renderItem, emptyText = 'No results yet.' }) {
  return (
    <div className="workflow-result-block">
      <div className="workflow-result-title">{title}</div>
      {!items || items.length === 0 ? (
        <div className="workflow-empty-inline">{emptyText}</div>
      ) : (
        <ul className="workflow-list">
          {items.map((item, index) => <li key={index}>{renderItem(item)}</li>)}
        </ul>
      )}
    </div>
  );
}

export function normalizeSuggestedGeneName(name) {
  if (!name) return null;
  return String(name).replace(/-(Centered|Mediated|Dependent|Associated|Related|Responsive|Like|Type|Induced|Module)$/i, '').trim() || null;
}

export function uniqueSuggestedGenes(candidateGenes = []) {
  const seen = new Set();
  const out = [];
  for (const item of candidateGenes) {
    const normalized = normalizeSuggestedGeneName(item?.name);
    if (!normalized) continue;
    const key = normalized.toUpperCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(normalized);
  }
  return out;
}

export function uniqueBy(array, keyFn) {
  const seen = new Set();
  const out = [];
  for (const item of array) {
    const key = keyFn(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

export function dedupePhenotypeCandidates(candidates = []) {
  const byPrimaryLabel = new Map();
  for (const gene of candidates) {
    const primary = String(gene?.label || gene?.symbol || gene?.gene_id || gene?.id || '').toUpperCase();
    if (!primary) continue;
    const existing = byPrimaryLabel.get(primary);
    if (!existing) {
      byPrimaryLabel.set(primary, gene);
      continue;
    }
    const existingReasons = existing.match_reasons || [];
    const nextReasons = gene.match_reasons || [];
    const existingQueries = existing.matched_queries || [];
    const nextQueries = gene.matched_queries || [];
    const existingScore = existing.rescue_score || 0;
    const nextScore = gene.rescue_score || 0;
    byPrimaryLabel.set(primary, {
      ...existing,
      match_reasons: uniqueBy([...existingReasons, ...nextReasons], (item) => item),
      matched_queries: uniqueBy([...existingQueries, ...nextQueries], (item) => String(item).toUpperCase()),
      rescue_score: Math.max(existingScore, nextScore),
    });
  }
  return [...byPrimaryLabel.values()];
}

export function buildPhenotypeRescueQueries(candidateGenes = [], mechanisms = [], phenotypeQuestion = '') {
  const queries = [];
  const add = (...items) => {
    for (const item of items) {
      if (item) queries.push(item);
    }
  };
  const mechanismNames = mechanisms.map((m) => String(m?.name || '').toLowerCase());
  const question = String(phenotypeQuestion || '').toLowerCase();
  const candidateNames = uniqueSuggestedGenes(candidateGenes);

  for (const name of candidateNames) {
    const upper = name.toUpperCase();
    if (/\bAN2\b/.test(upper)) add('AN2');
    if (/\bJAF13\b|\bEGL\d\b|\bGL3\b|\bMYC\d\b/.test(upper)) add('JAF13', 'EGL3');
    if (/\bDFR\b|\bTT3\b/.test(upper)) add('DFR');
    if (/\bCHS\b|\bTT4\b/.test(upper)) add('CHS');
    if (upper.includes('MYB')) add('MYB');
    if (upper.includes('BHLH')) add('bHLH', 'JAF13');
    if (upper.includes('WD40') || upper.includes('TTG1')) add('TTG1', 'WD40');
  }

  const anthocyaninLike = mechanismNames.some((name) => ['anthocyanin', 'flavonoid', 'pigment', 'dfr', 'chs'].includes(name))
    || question.includes('flower color')
    || question.includes('pigment');
  if (anthocyaninLike) add('AN2', 'JAF13', 'DFR', 'CHS');

  return uniqueBy(queries, (item) => item.toUpperCase());
}

export function computeRescueReason(query, gene) {
  const q = String(query || '').toUpperCase();
  const symbol = String(gene?.symbol || '').toUpperCase();
  const synonyms = Array.isArray(gene?.synonyms) ? gene.synonyms.map((s) => String(s).toUpperCase()) : [];
  if (symbol === q || synonyms.includes(q)) return `matched via ${query}`;
  if (q === 'MYB') return 'matched via MYB-family cue from literature';
  if (q === 'BHLH') return 'matched via bHLH-family cue from literature';
  if (q === 'WD40' || q === 'TTG1') return 'matched via WD40/TTG1 regulator cue';
  if (q === 'AN2' || q === 'JAF13' || q === 'DFR' || q === 'CHS' || q === 'EGL3') return `matched via ${query} pathway cue`;
  return `matched via ${query} search`;
}

export function LiteraturePaperItem({ item }) {
  const snippet = item?.snippet?.trim();
  const content = (
    <>
      <strong>{item.year}</strong> · {item.title}
      <span className="workflow-faint"> · {item.classification}</span>
    </>
  );
  return (
    <span className="workflow-paper-item">
      {item?.url ? (
        <a href={item.url} target="_blank" rel="noreferrer" className="workflow-paper-link">
          {content}
        </a>
      ) : content}
      {snippet ? (
        <span className="workflow-paper-tooltip" role="note">
          <strong>Abstract</strong>
          <span>{snippet}</span>
        </span>
      ) : null}
    </span>
  );
}
