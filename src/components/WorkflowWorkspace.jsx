import React, { useEffect, useMemo, useState } from 'react';
import { geneAPI, workflowAPI } from '../services/apiService';
import { geneLabel } from '../utils/geneLabel';
import '../styles/WorkflowWorkspace.css';

const INTENT_OPTIONS = [
  { value: 'experiment', label: 'Experiment follow-up' },
  { value: 'network', label: 'Network interpretation' },
  { value: 'rnai', label: 'RNAi planning' },
  { value: 'transfer', label: 'Cross-species transfer' },
];

const EXAMPLE_WORKFLOWS = [
  {
    title: 'Start from a hit list',
    description: 'Import genes, map them onto the atlas, and identify top candidates plus upstream regulators.',
    action: 'First-pass analysis',
  },
  {
    title: 'Compare conditions',
    description: 'Use a tissue or condition contrast, then escalate into regulator and candidate follow-up.',
    action: 'Differential expression',
  },
  {
    title: 'Turn evidence into a plan',
    description: 'Generate a research brief, validation plan, optimization constraints, and collaborator-facing report.',
    action: 'Study planning',
  },
];

const ASSAY_OPTIONS = [
  { value: 'in_silico', label: 'Computational only', description: 'Network scoring, prioritization, and in-silico follow-up.' },
  { value: 'expression', label: 'Expression evidence', description: 'Use RNA-seq or expression context to support decisions.' },
  { value: 'rnai', label: 'RNAi / dsRNA design', description: 'Allow dsRNA design and RNAi-specific planning.' },
  { value: 'comparative', label: 'Cross-species comparison', description: 'Use orthology and transferability checks.' },
  { value: 'motif', label: 'Promoter / motif analysis', description: 'Allow promoter binding and motif-oriented follow-up.' },
  { value: 'trait', label: 'Trait / phenotype evidence', description: 'Use loaded phenotype or trait associations.' },
];

function splitTokens(text) {
  return text.split(/[\s,;]+/).map((token) => token.trim()).filter(Boolean);
}

function parseAssayText(text) {
  return text.split(',').map((token) => token.trim()).filter(Boolean);
}

function JsonPreview({ title, data, defaultOpen = false }) {
  if (!data) return null;
  return (
    <details className="workflow-json" open={defaultOpen}>
      <summary>{title}</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

function StatusPill({ tone = 'neutral', children }) {
  return <span className={`workflow-pill workflow-pill-${tone}`}>{children}</span>;
}

function describeGene(item, labelOverrides = {}) {
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

function GeneBadge({ item, labelOverrides }) {
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

function differentialDirectionText(item, groupA, groupB) {
  const a = groupA?.join(', ') || 'Group A';
  const b = groupB?.join(', ') || 'Group B';
  if ((item?.log2fc ?? 0) < 0) return `higher in ${a}`;
  if ((item?.log2fc ?? 0) > 0) return `higher in ${b}`;
  return 'similar in both groups';
}

function ResultList({ title, items, renderItem, emptyText = 'No results yet.' }) {
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

function normalizeSuggestedGeneName(name) {
  if (!name) return null;
  return String(name).replace(/-(Centered|Mediated|Dependent|Associated|Related|Responsive|Like|Type|Induced|Module)$/i, '').trim() || null;
}

function uniqueSuggestedGenes(candidateGenes = []) {
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

function uniqueBy(array, keyFn) {
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

function dedupePhenotypeCandidates(candidates = []) {
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

function buildPhenotypeRescueQueries(candidateGenes = [], mechanisms = [], phenotypeQuestion = '') {
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
  if (anthocyaninLike) {
    add('AN2', 'JAF13', 'DFR', 'CHS');
  }

  return uniqueBy(queries, (item) => item.toUpperCase());
}

function computeRescueReason(query, gene) {
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

async function resolvePhenotypeRescueCandidates({ candidateGenes = [], mechanisms = [], phenotypeQuestion = '', species }) {
  const rescueQueries = buildPhenotypeRescueQueries(candidateGenes, mechanisms, phenotypeQuestion);
  if (!rescueQueries.length || !species) return [];

  const searchResults = await Promise.all(
    rescueQueries.map(async (query) => ({
      query,
      results: await geneAPI.search(query, 8, species),
    })),
  );

  const ranked = new Map();
  for (const { query, results } of searchResults) {
    for (const gene of results?.results || []) {
      if (!gene?.id || gene.species !== species) continue;
      const existing = ranked.get(gene.id) || {
        ...gene,
        gene_id: gene.id,
        matched_queries: [],
        match_reasons: [],
        rescue_score: 0,
      };
      existing.matched_queries = uniqueBy([...existing.matched_queries, query], (item) => item.toUpperCase());
      existing.match_reasons = uniqueBy([...existing.match_reasons, computeRescueReason(query, gene)], (item) => item);
      const synonyms = Array.isArray(gene.synonyms) ? gene.synonyms.map((s) => String(s).toUpperCase()) : [];
      const upperQuery = query.toUpperCase();
      const exact = String(gene.symbol || '').toUpperCase() === upperQuery || synonyms.includes(upperQuery);
      existing.rescue_score += exact ? 5 : 2;
      ranked.set(gene.id, existing);
    }
  }

  return [...ranked.values()]
    .sort((a, b) => (
      (b.rescue_score - a.rescue_score)
      || (b.matched_queries.length - a.matched_queries.length)
      || String(a.symbol || a.gene_id).localeCompare(String(b.symbol || b.gene_id))
    ))
    .slice(0, 8);
}

function LiteraturePaperItem({ item }) {
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

export default function WorkflowWorkspace({
  selectedGene,
  networkData,
  filters,
  onNavigate,
  onSpeciesChange,
  onFocusGeneChange,
  onOpenGeneSetAnalysis,
  onOpenDsRna,
  onDsRnaSeedChange,
}) {
  const [intent, setIntent] = useState('experiment');
  const [species, setSpecies] = useState(selectedGene?.species || filters?.species?.[0] || 'human');
  const [geneSetText, setGeneSetText] = useState('');
  const [datasetImport, setDatasetImport] = useState(null);
  const [importSignature, setImportSignature] = useState('');
  const [geneSetAnalysis, setGeneSetAnalysis] = useState(null);
  const [consensus, setConsensus] = useState(null);
  const [counterfactual, setCounterfactual] = useState(null);
  const [researchBrief, setResearchBrief] = useState(null);
  const [validationPlan, setValidationPlan] = useState(null);
  const [studyReport, setStudyReport] = useState(null);
  const [experimentPlan, setExperimentPlan] = useState(null);
  const [differential, setDifferential] = useState(null);
  const [availableTissues, setAvailableTissues] = useState([]);
  const [showCandidateOnlyInDifferential, setShowCandidateOnlyInDifferential] = useState(false);
  const [literature, setLiterature] = useState(null);
  const [literatureTargetId, setLiteratureTargetId] = useState('');
  const [phenotypeQuestion, setPhenotypeQuestion] = useState('');
  const [phenotypeLiterature, setPhenotypeLiterature] = useState(null);
  const [phenotypeAtlasImport, setPhenotypeAtlasImport] = useState(null);
  const [phenotypeRescueCandidates, setPhenotypeRescueCandidates] = useState([]);
  const [variantEffect, setVariantEffect] = useState(null);
  const [promoterPlan, setPromoterPlan] = useState(null);
  const [crisprGuides, setCrisprGuides] = useState(null);
  const [primerPairs, setPrimerPairs] = useState(null);
  const [celltypeReadiness, setCelltypeReadiness] = useState(null);
  const [trajectoryReadiness, setTrajectoryReadiness] = useState(null);
  const [combinatorialPlan, setCombinatorialPlan] = useState(null);
  const [onboardingPlan, setOnboardingPlan] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState({});

  const [budgetLevel, setBudgetLevel] = useState('medium');
  const [timelineDays, setTimelineDays] = useState(14);
  const [allowedAssays, setAllowedAssays] = useState('in_silico,expression,comparative');
  const [groupAText, setGroupAText] = useState('');
  const [groupBText, setGroupBText] = useState('');
  const [variantPosition, setVariantPosition] = useState('');
  const [variantRef, setVariantRef] = useState('');
  const [variantAlt, setVariantAlt] = useState('');
  const [sequenceText, setSequenceText] = useState('');
  const [advancedSpecies, setAdvancedSpecies] = useState(selectedGene?.species || filters?.species?.[0] || 'human');
  const [onboardingSpeciesName, setOnboardingSpeciesName] = useState('wheat');
  const [speciesLockedByUser, setSpeciesLockedByUser] = useState(false);
  const [advancedSpeciesLockedByUser, setAdvancedSpeciesLockedByUser] = useState(false);

  const seededGeneIds = useMemo(() => {
    if (!selectedGene) return [];
    const ids = new Set([selectedGene.id]);
    (networkData?.regulators || []).slice(0, 5).forEach((gene) => ids.add(gene.id));
    (networkData?.targets || []).slice(0, 5).forEach((gene) => ids.add(gene.id));
    return [...ids];
  }, [selectedGene, networkData]);

  useEffect(() => {
    if (selectedGene?.species && !speciesLockedByUser) {
      setSpecies(selectedGene.species);
    }
    if (selectedGene?.species && !advancedSpeciesLockedByUser) {
      setAdvancedSpecies(selectedGene.species);
    }
  }, [selectedGene, speciesLockedByUser, advancedSpeciesLockedByUser]);

  useEffect(() => {
    const filterSpecies = filters?.species?.[0];
    if (filterSpecies && !speciesLockedByUser) {
      setSpecies(filterSpecies);
    }
    if (filterSpecies && !advancedSpeciesLockedByUser) {
      setAdvancedSpecies(filterSpecies);
    }
  }, [filters, speciesLockedByUser, advancedSpeciesLockedByUser]);

  useEffect(() => {
    if (!geneSetText && seededGeneIds.length > 0) {
      setGeneSetText(seededGeneIds.join('\n'));
    }
  }, [seededGeneIds, geneSetText]);

  const mappedGeneIds = datasetImport?.mapped_gene_ids || geneSetAnalysis?.import_summary?.mapped_gene_ids || [];
  const geneCount = splitTokens(geneSetText).length;
  const selectedAssays = useMemo(() => parseAssayText(allowedAssays), [allowedAssays]);
  const labelOverrides = useMemo(() => {
    const merged = {};
    const sources = [
      ...(datasetImport?.mapped_genes || []),
      ...(geneSetAnalysis?.import_summary?.mapped_genes || []),
    ];
    for (const gene of sources) {
      if (!gene?.gene_id) continue;
      merged[gene.gene_id] = {
        label: gene.label || gene.symbol || gene.gene_id,
        label_inferred: !!gene.label_inferred,
      };
    }
    return merged;
  }, [datasetImport, geneSetAnalysis]);
  const candidateGeneIdSet = useMemo(() => new Set(Object.keys(labelOverrides)), [labelOverrides]);
  const literatureTargetOptions = useMemo(() => {
    const seen = new Set();
    const out = [];
    const addGene = (geneLike) => {
      if (!geneLike) return;
      const id = geneLike.gene_id || geneLike.id;
      if (!id || seen.has(id)) return;
      seen.add(id);
      const symbol = geneLike.symbol || id;
      const label = geneLike.label || labelOverrides[id]?.label || symbol || id;
      out.push({
        id,
        symbol,
        label,
        label_inferred: geneLike.label_inferred ?? labelOverrides[id]?.label_inferred ?? false,
      });
    };
    addGene(selectedGene);
    (datasetImport?.mapped_genes || []).forEach(addGene);
    (geneSetAnalysis?.import_summary?.mapped_genes || []).forEach(addGene);
    (geneSetAnalysis?.candidate_triage?.ranked_candidates || []).forEach(addGene);
    return out;
  }, [selectedGene, datasetImport, geneSetAnalysis, labelOverrides]);
  const differentialCandidateRows = useMemo(
    () => (differential?.forced_results || differential?.results || []).filter((row) => candidateGeneIdSet.has(row.gene_id)),
    [differential, candidateGeneIdSet],
  );
  const displayedDifferentialRows = useMemo(() => (
    showCandidateOnlyInDifferential ? differentialCandidateRows : (differential?.results || []).slice(0, 8)
  ), [showCandidateOnlyInDifferential, differentialCandidateRows, differential]);
  const phenotypeSuggestedGenes = useMemo(
    () => uniqueSuggestedGenes(phenotypeLiterature?.candidate_summary?.candidate_genes || []),
    [phenotypeLiterature],
  );
  const phenotypeAtlasMappedGenes = useMemo(
    () => phenotypeAtlasImport?.mapped_genes || [],
    [phenotypeAtlasImport],
  );
  const phenotypeAtlasUnmappedRows = useMemo(
    () => phenotypeAtlasImport?.unmapped_rows || [],
    [phenotypeAtlasImport],
  );
  const phenotypeCombinedCandidates = useMemo(
    () => uniqueBy([
      ...phenotypeAtlasMappedGenes.map((gene) => ({ ...gene, source_kind: 'exact_map' })),
      ...phenotypeRescueCandidates.map((gene) => ({ ...gene, source_kind: 'rescue' })),
    ], (gene) => gene.gene_id || gene.id),
    [phenotypeAtlasMappedGenes, phenotypeRescueCandidates],
  );
  const phenotypeDisplayCandidates = useMemo(
    () => dedupePhenotypeCandidates(phenotypeRescueCandidates),
    [phenotypeRescueCandidates],
  );
  const dsRnaSeedSet = useMemo(() => {
    const consensusRanked = consensus?.ranked_candidates || [];
    const ranked = geneSetAnalysis?.candidate_triage?.ranked_candidates || [];
    const mapped = datasetImport?.mapped_genes || geneSetAnalysis?.import_summary?.mapped_genes || [];
    const combined = [...consensusRanked, ...ranked, ...mapped];
    return uniqueBy(combined, (gene) => gene?.gene_id || gene?.id)
      .map((gene) => describeGene(gene, labelOverrides).primary || gene?.gene_id || gene?.id)
      .filter(Boolean)
      .slice(0, 15);
  }, [consensus, geneSetAnalysis, datasetImport, labelOverrides]);
  const dsRnaSeedTarget = useMemo(() => {
    const topConsensus = consensus?.ranked_candidates?.[0];
    const topCandidate = geneSetAnalysis?.candidate_triage?.ranked_candidates?.[0];
    return topConsensus || topCandidate || selectedGene || null;
  }, [consensus, geneSetAnalysis, selectedGene]);
  const dsRnaCompareTarget = useMemo(() => {
    const secondConsensus = consensus?.ranked_candidates?.[1];
    if (secondConsensus) return secondConsensus;
    const ranked = geneSetAnalysis?.candidate_triage?.ranked_candidates || [];
    const first = dsRnaSeedTarget?.gene_id || dsRnaSeedTarget?.id;
    return ranked.find((gene) => (gene?.gene_id || gene?.id) !== first) || null;
  }, [consensus, geneSetAnalysis, dsRnaSeedTarget]);

  useEffect(() => {
    onDsRnaSeedChange?.({
      target: dsRnaSeedTarget,
      compareTarget: dsRnaCompareTarget,
      geneSet: dsRnaSeedSet,
      species,
    });
  }, [onDsRnaSeedChange, dsRnaSeedTarget, dsRnaCompareTarget, dsRnaSeedSet, species]);

  useEffect(() => {
    if (literatureTargetId && literatureTargetOptions.some((g) => g.id === literatureTargetId)) return;
    if (selectedGene?.id) {
      setLiteratureTargetId(selectedGene.id);
    } else if (literatureTargetOptions.length > 0) {
      setLiteratureTargetId(literatureTargetOptions[0].id);
    } else {
      setLiteratureTargetId('');
    }
  }, [selectedGene, literatureTargetOptions, literatureTargetId]);

  const runStep = async (key, fn) => {
    setLoading((prev) => ({ ...prev, [key]: true }));
    setError(null);
    try {
      return await fn();
    } catch (err) {
      setError(err?.detail || err?.message || 'Request failed');
      return null;
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  const ensureImported = async () => {
    const currentSignature = splitTokens(geneSetText).join('\n');
    if (datasetImport && importSignature === currentSignature) {
      return datasetImport;
    }
    const result = await workflowAPI.importDataset({ content: geneSetText, species });
    if (result?.detail) throw new Error(result.detail);
    setDatasetImport(result);
    setImportSignature(currentSignature);
    return result;
  };

  const ensureMappedGeneIds = async () => {
    const imported = await ensureImported();
    if (!imported?.mapped_gene_ids?.length) {
      throw new Error('No atlas genes could be mapped from the current gene set.');
    }
    return imported.mapped_gene_ids;
  };

  const handleImport = async () => {
    await runStep('import', async () => {
      const result = await workflowAPI.importDataset({ content: geneSetText, species });
      if (result?.detail) throw new Error(result.detail);
      setDatasetImport(result);
      setImportSignature(splitTokens(geneSetText).join('\n'));
      return result;
    });
  };

  const handleFirstPassAnalysis = async () => {
    await runStep('analysis', async () => {
      const result = await workflowAPI.analyzeGeneSet({ content: geneSetText, species, intent });
      if (result?.detail) throw new Error(result.detail);
      setGeneSetAnalysis(result);
      setDatasetImport(result.import_summary || null);
      setImportSignature(splitTokens(geneSetText).join('\n'));
      const topCandidate = result?.candidate_triage?.ranked_candidates?.[0];
      if (topCandidate) {
        onFocusGeneChange?.(topCandidate);
      }
      return result;
    });
  };

  const handleConsensus = async () => {
    await runStep('consensus', async () => {
      const geneIds = await ensureMappedGeneIds();
      const [ranking, flips] = await Promise.all([
        workflowAPI.consensusRanking({ geneIds, species, intent, includeExternal: true, topN: 8 }),
        workflowAPI.counterfactualAnalysis({ geneIds, species, intent, includeExternal: true }),
      ]);
      if (ranking?.detail) throw new Error(ranking.detail);
      if (flips?.detail) throw new Error(flips.detail);
      setConsensus(ranking);
      setCounterfactual(flips);
      const topConsensus = ranking?.ranked_candidates?.[0];
      if (topConsensus) {
        onFocusGeneChange?.(topConsensus);
      }
      return ranking;
    });
  };

  const handleStudyPlanning = async () => {
    await runStep('planning', async () => {
      const geneIds = await ensureMappedGeneIds();
      const [brief, validation, report, optimized] = await Promise.all([
        workflowAPI.researchBrief({ geneIds, species, intent }),
        workflowAPI.validationPlan({ geneIds, species, intent }),
        workflowAPI.studyReport({ geneIds, species, intent }),
        workflowAPI.experimentOptimize({
          geneIds,
          species,
          intent,
          budgetLevel,
          timelineDays: Number(timelineDays),
          allowedAssays: splitTokens(allowedAssays),
        }),
      ]);
      if (brief?.detail) throw new Error(brief.detail);
      if (validation?.detail) throw new Error(validation.detail);
      if (report?.detail) throw new Error(report.detail);
      if (optimized?.detail) throw new Error(optimized.detail);
      setResearchBrief(brief);
      setValidationPlan(validation);
      setStudyReport(report);
      setExperimentPlan(optimized);
      return brief;
    });
  };

  const handleDifferential = async () => {
    await runStep('differential', async () => {
      const result = await workflowAPI.differentialExpression({
        species,
        groupA: splitTokens(groupAText),
        groupB: splitTokens(groupBText),
        geneIds: Array.from(candidateGeneIdSet),
        top: 20,
      });
      if (result?.detail) throw new Error(result.detail);
      setDifferential(result);
      setShowCandidateOnlyInDifferential(false);
      return result;
    });
  };

  const handleLiterature = async () => {
    if (!literatureTargetId) {
      setError('Select a literature target first.');
      return;
    }
    await runStep('literature', async () => {
      const result = await workflowAPI.literatureReview({
        scope: 'gene',
        geneId: literatureTargetId,
        yearsBack: 5,
        maxResults: 8,
      });
      if (result?.detail) throw new Error(result.detail);
      setLiterature(result);
      return result;
    });
  };

  const handlePhenotypeLiterature = async () => {
    const query = phenotypeQuestion.trim();
    if (!query) {
      setError('Enter a phenotype or research question first.');
      return;
    }
    await runStep('phenotypeLiterature', async () => {
      const result = await workflowAPI.literatureReview({
        scope: 'phenotype',
        query: `${species} ${query}`.trim(),
        species,
        yearsBack: 5,
        maxResults: 8,
      });
      if (result?.detail) throw new Error(result.detail);
      setPhenotypeLiterature(result);
      const suggestedGenes = uniqueSuggestedGenes(result?.candidate_summary?.candidate_genes || []);
      if (suggestedGenes.length > 0) {
        const importResult = await workflowAPI.importDataset({
          content: suggestedGenes.join('\n'),
          species,
          filename: 'phenotype-literature-suggestions.txt',
        });
        if (importResult?.detail) throw new Error(importResult.detail);
        setPhenotypeAtlasImport(importResult);
      } else {
        setPhenotypeAtlasImport(null);
      }
      const rescueCandidates = await resolvePhenotypeRescueCandidates({
        candidateGenes: result?.candidate_summary?.candidate_genes || [],
        mechanisms: result?.candidate_summary?.mechanisms || [],
        phenotypeQuestion: query,
        species,
      });
      setPhenotypeRescueCandidates(rescueCandidates);
      return result;
    });
  };

  const handleLoadPhenotypeSuggestions = (mode = 'atlas') => {
    const genesToLoad = mode === 'literature'
      ? phenotypeSuggestedGenes
      : (mode === 'combined'
        ? phenotypeCombinedCandidates.map((gene) => gene.symbol || gene.gene_id).filter(Boolean)
        : phenotypeAtlasMappedGenes.map((gene) => gene.symbol || gene.gene_id).filter(Boolean));
    if (!genesToLoad.length) {
      setError(mode === 'literature'
        ? 'No literature-suggested genes are available to load.'
        : mode === 'combined'
          ? `No ${species || 'selected species'} candidate genes are available to load.`
          : `No ${species || 'selected species'} atlas-mappable genes are available to load.`);
      return;
    }
    setGeneSetText(genesToLoad.join('\n'));
    setDatasetImport(null);
    setImportSignature('');
    setGeneSetAnalysis(null);
    setConsensus(null);
    setCounterfactual(null);
    setResearchBrief(null);
    setValidationPlan(null);
    setStudyReport(null);
    setExperimentPlan(null);
    setDifferential(null);
  };

  const handleVariantDesign = async () => {
    if (!selectedGene?.id || !variantPosition) {
      setError('Select a focus gene and enter a genomic position first.');
      return;
    }
    await runStep('design', async () => {
      const [effect, promoter, crispr, primers] = await Promise.all([
        workflowAPI.variantEffect({
          geneId: selectedGene.id,
          position: Number(variantPosition),
          ref: variantRef || null,
          alt: variantAlt || null,
        }),
        workflowAPI.promoterEditPrioritize({ geneId: selectedGene.id, top: 8 }),
        workflowAPI.crisprDesign({
          geneId: selectedGene.id,
          sequence: sequenceText || null,
          top: 8,
        }),
        workflowAPI.primerDesign({
          geneId: selectedGene.id,
          sequence: sequenceText || null,
          top: 6,
        }),
      ]);
      if (effect?.detail) throw new Error(effect.detail);
      if (promoter?.detail) throw new Error(promoter.detail);
      if (crispr?.detail) throw new Error(crispr.detail);
      if (primers?.detail) throw new Error(primers.detail);
      setVariantEffect(effect);
      setPromoterPlan(promoter);
      setCrisprGuides(crispr);
      setPrimerPairs(primers);
      return effect;
    });
  };

  const handleAdvanced = async () => {
    await runStep('advanced', async () => {
      const geneIds = mappedGeneIds.length > 0 ? mappedGeneIds : seededGeneIds;
      const [celltype, trajectory, combinatorial, onboarding] = await Promise.all([
        workflowAPI.celltypeRegulation({ species: advancedSpecies, geneIds }),
        workflowAPI.trajectoryRegulation({ species: advancedSpecies, geneIds }),
        geneIds.length >= 2
          ? workflowAPI.combinatorialPerturbation({ species: advancedSpecies, geneIds, comboSize: 2, top: 6 })
          : Promise.resolve(null),
        workflowAPI.speciesOnboardingPlan({
          speciesName: onboardingSpeciesName,
          intendedCapabilities: ['network', 'expression', 'motif', 'orthology', 'rnai'],
        }),
      ]);
      if (celltype?.detail) throw new Error(celltype.detail);
      if (trajectory?.detail) throw new Error(trajectory.detail);
      if (combinatorial?.detail) throw new Error(combinatorial.detail);
      if (onboarding?.detail) throw new Error(onboarding.detail);
      setCelltypeReadiness(celltype);
      setTrajectoryReadiness(trajectory);
      setCombinatorialPlan(combinatorial);
      setOnboardingPlan(onboarding);
      return celltype;
    });
  };

  const selectedLabel = selectedGene ? geneLabel(selectedGene).label : null;
  const selectedLiteratureTarget = literatureTargetOptions.find((g) => g.id === literatureTargetId) || null;
  const networkStats = networkData?.stats || {};

  const handleSpeciesInputChange = (value) => {
    setSpecies(value);
    setSpeciesLockedByUser(true);
    onSpeciesChange?.(value);
  };

  const handleAdvancedSpeciesInputChange = (value) => {
    setAdvancedSpecies(value);
    setAdvancedSpeciesLockedByUser(true);
    onSpeciesChange?.(value);
  };

  const handleAssayToggle = (assay) => {
    const next = selectedAssays.includes(assay)
      ? selectedAssays.filter((item) => item !== assay)
      : [...selectedAssays, assay];
    setAllowedAssays(next.join(','));
  };

  useEffect(() => {
    let cancelled = false;
    const loadAvailableTissues = async () => {
      if (!species) {
        if (!cancelled) setAvailableTissues([]);
        return;
      }
      try {
        const result = await workflowAPI.differentialExpression({
          species,
          groupA: [],
          groupB: [],
          top: 1,
        });
        if (!cancelled) {
          setAvailableTissues(result?.available_tissues || []);
        }
      } catch {
        if (!cancelled) setAvailableTissues([]);
      }
    };
    loadAvailableTissues();
    return () => { cancelled = true; };
  }, [species]);

  const toggleGroupToken = (setter, currentText, token) => {
    const current = splitTokens(currentText);
    const next = current.includes(token)
      ? current.filter((item) => item !== token)
      : [...current, token];
    setter(next.join(', '));
  };

  return (
    <div className="workflow-workspace">
      <div className="workflow-hero">
        <div>
          <p className="workflow-kicker">Workflow-first workspace</p>
          <h1>Run the atlas like a study, not a demo.</h1>
          <p className="workflow-subtitle">
            Start from a focus gene, hit list, or condition contrast. Move from interpretation
            to ranking, validation, and assay design without switching mental models.
          </p>
        </div>
        <div className="workflow-hero-actions">
          <button onClick={() => onNavigate?.('network')}>Open explorer</button>
          <button onClick={() => onNavigate?.('organism')}>Browse organisms</button>
          <button onClick={() => onNavigate?.('analysis')}>Open analysis lab</button>
        </div>
      </div>

      {error && <div className="workflow-error">{error}</div>}

      <div className="workflow-example-grid">
        {EXAMPLE_WORKFLOWS.map((example) => (
          <div key={example.title} className="workflow-example-card">
            <div className="workflow-example-title">{example.title}</div>
            <p>{example.description}</p>
            <StatusPill>{example.action}</StatusPill>
          </div>
        ))}
      </div>

      <div className="workflow-grid workflow-grid-top">
        <section className="workflow-card workflow-card-context">
          <div className="workflow-card-header">
            <div>
              <h2>1. Research context</h2>
              <p>Keep the focus gene, species, and intent aligned across steps.</p>
            </div>
          </div>

          <div className="workflow-context-summary">
            <div className="workflow-metric">
              <span className="workflow-metric-label">Focus gene</span>
              <strong>{selectedLabel || 'None selected yet'}</strong>
            </div>
            <div className="workflow-metric">
              <span className="workflow-metric-label">Species</span>
              <strong>{species || 'auto'}</strong>
            </div>
            <div className="workflow-metric">
              <span className="workflow-metric-label">Intent</span>
              <strong>{INTENT_OPTIONS.find((opt) => opt.value === intent)?.label}</strong>
            </div>
            <div className="workflow-metric">
              <span className="workflow-metric-label">Evidence setting</span>
              <strong>{filters?.includeInferred === false ? 'Measured only' : 'Measured + inferred'}</strong>
            </div>
          </div>

          <div className="workflow-form-grid">
            <label className="workflow-field">
              <span>Intent</span>
              <select value={intent} onChange={(e) => setIntent(e.target.value)}>
                {INTENT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label className="workflow-field">
              <span>Species</span>
              <input value={species} onChange={(e) => handleSpeciesInputChange(e.target.value)} placeholder="human" />
            </label>
          </div>

          {selectedGene && (
            <div className="workflow-focus-gene">
              <div>
                <div className="workflow-result-title">Current focus gene</div>
                <div className="workflow-focus-symbol">{selectedLabel}</div>
                <div className="workflow-focus-meta">{selectedGene.name} · {selectedGene.species}</div>
                <div className="workflow-focus-stats">
                  <span>{networkStats.regulators?.length || networkData?.regulators?.length || 0} regulators</span>
                  <span>{networkStats.targets?.length || networkData?.targets?.length || 0} targets</span>
                </div>
              </div>
              <div className="workflow-inline-actions">
                <button onClick={() => onNavigate?.('network')}>Network</button>
                <button onClick={() => onNavigate?.('pathways')}>Paths</button>
                <button onClick={() => onNavigate?.('comparison')}>Orthology</button>
                <button onClick={() => onOpenDsRna?.({ target: dsRnaSeedTarget, compareTarget: dsRnaCompareTarget, geneSet: dsRnaSeedSet })}>dsRNA</button>
              </div>
            </div>
          )}
        </section>

        <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>2. Start from a phenotype question</h2>
              <p>Ask the literature about a phenotype or intervention goal before you already know which genes to test.</p>
            </div>
            <button onClick={handlePhenotypeLiterature} disabled={loading.phenotypeLiterature}>
              {loading.phenotypeLiterature ? 'Searching…' : 'Search literature first'}
            </button>
          </div>

          <label className="workflow-field">
            <span>Phenotype question</span>
            <textarea
              rows={3}
              value={phenotypeQuestion}
              onChange={(e) => setPhenotypeQuestion(e.target.value)}
              placeholder="Which genes are the best targets for changing flower color in this species?"
            />
            <small className="workflow-help-text">This uses external literature for broad ideation before you commit to a hit list.</small>
          </label>

          {phenotypeLiterature ? (
            <>
              <div className="workflow-summary-box">
                Search term used: <strong>{phenotypeLiterature.search_term}</strong>
              </div>
              <ResultList
                title="Likely candidate genes mentioned in the literature"
                items={phenotypeLiterature.candidate_summary?.candidate_genes?.slice(0, 8)}
                renderItem={(item) => <span><strong>{item.name}</strong><span className="workflow-faint"> · mentioned in {item.mentions} paper(s)</span></span>}
                emptyText="No candidate-like gene names were extracted from the returned papers."
              />
              <ResultList
                title={`Atlas-mappable genes for ${species || 'the selected species'}`}
                items={phenotypeAtlasMappedGenes.slice(0, 8)}
                renderItem={(item) => <GeneBadge item={item} labelOverrides={labelOverrides} />}
                emptyText={`None of the current literature suggestions mapped cleanly into ${species || 'the selected species'} yet.`}
              />
              <ResultList
                title={`${species || 'Selected species'} homolog / family candidates inferred from the literature`}
                items={phenotypeDisplayCandidates.slice(0, 8)}
                renderItem={(item) => (
                  <span>
                    <GeneBadge item={item} labelOverrides={labelOverrides} />
                    {item.match_reasons?.length ? <span className="workflow-faint"> · {item.match_reasons.join(' · ')}</span> : null}
                  </span>
                )}
                emptyText={`No homolog or family-level rescue candidates were found for ${species || 'the selected species'}.`}
              />
              {!!phenotypeAtlasUnmappedRows.length && (
                <ResultList
                  title="Literature suggestions not mapped into the selected species"
                  items={phenotypeAtlasUnmappedRows.slice(0, 8)}
                  renderItem={(item) => <span>{item.input || item.gene_token || item}</span>}
                  emptyText=""
                />
              )}
              <div className="workflow-inline-actions">
                <button onClick={() => handleLoadPhenotypeSuggestions('atlas')} disabled={!phenotypeAtlasMappedGenes.length}>
                  Load atlas-mappable genes into hit list
                </button>
                <button onClick={() => handleLoadPhenotypeSuggestions('combined')} disabled={!phenotypeCombinedCandidates.length}>
                  Load atlas candidate genes
                </button>
                <button onClick={() => handleLoadPhenotypeSuggestions('literature')} disabled={!phenotypeSuggestedGenes.length}>
                  Load raw literature suggestions
                </button>
                {phenotypeAtlasMappedGenes.length > 0 && (
                  <span className="workflow-faint">
                    {phenotypeAtlasMappedGenes.length} atlas-mappable gene{phenotypeAtlasMappedGenes.length === 1 ? '' : 's'} ready for panel 3
                  </span>
                )}
                {!phenotypeAtlasMappedGenes.length && phenotypeRescueCandidates.length > 0 && (
                  <span className="workflow-faint">
                    {phenotypeRescueCandidates.length} species-grounded candidate gene{phenotypeRescueCandidates.length === 1 ? '' : 's'} inferred from homolog/family cues
                  </span>
                )}
                {phenotypeSuggestedGenes.length > 0 && phenotypeAtlasMappedGenes.length === 0 && (
                  <span className="workflow-faint">
                    {phenotypeSuggestedGenes.length} literature suggestion{phenotypeSuggestedGenes.length === 1 ? '' : 's'} found, but none matched by exact symbol in {species || 'the selected species'}
                  </span>
                )}
              </div>
              <ResultList
                title="Mechanisms and pathways mentioned"
                items={phenotypeLiterature.candidate_summary?.mechanisms?.slice(0, 8)}
                renderItem={(item) => <span><strong>{item.name}</strong><span className="workflow-faint"> · mentioned in {item.mentions} paper(s)</span></span>}
                emptyText="No mechanism summary was extracted from the returned papers."
              />
              <ResultList
                title="Recent papers"
                items={phenotypeLiterature.results?.slice(0, 6)}
                renderItem={(item) => <LiteraturePaperItem item={item} />}
                emptyText="No external literature results returned for this question yet."
              />
              <div className="workflow-inline-actions">
                <StatusPill tone="success">direct {phenotypeLiterature.summary?.direct_phenotype_evidence ?? 0}</StatusPill>
                <StatusPill tone="neutral">comparative {phenotypeLiterature.summary?.comparative_evidence ?? 0}</StatusPill>
                <StatusPill tone="neutral">mechanistic {phenotypeLiterature.summary?.mechanistic_background ?? 0}</StatusPill>
                <StatusPill tone="danger">low relevance {phenotypeLiterature.summary?.low_relevance ?? 0}</StatusPill>
              </div>
            </>
          ) : (
            <div className="workflow-empty-inline">No phenotype-first literature search has been run yet.</div>
          )}
        </section>
      </div>

      <div className="workflow-grid">
        <section className="workflow-card workflow-card-input">
          <div className="workflow-card-header">
            <div>
              <h2>3. Import a hit list</h2>
              <p>Paste gene symbols or IDs, one per line or separated by commas/semicolons, and normalize them before downstream analysis.</p>
            </div>
            <div className="workflow-inline-actions">
              <button onClick={handleImport} disabled={loading.import}>
                {loading.import ? 'Importing…' : 'Map genes'}
              </button>
              <button onClick={() => onOpenGeneSetAnalysis?.()}>Legacy gene-set modal</button>
            </div>
          </div>

          <textarea
            className="workflow-textarea"
            rows={8}
            value={geneSetText}
            onChange={(e) => setGeneSetText(e.target.value)}
            placeholder="TP53&#10;BAX&#10;MDM2&#10;&#10;or: TP53, BAX, MDM2"
          />

          <div className="workflow-context-summary">
            <div className="workflow-metric">
              <span className="workflow-metric-label">Input tokens</span>
              <strong>{geneCount}</strong>
            </div>
            <div className="workflow-metric">
              <span className="workflow-metric-label">Mapped genes</span>
              <strong>{datasetImport?.mapped_gene_ids?.length || 0}</strong>
            </div>
            <div className="workflow-metric">
              <span className="workflow-metric-label">Unmapped</span>
              <strong>{datasetImport?.unmapped_count || 0}</strong>
            </div>
          </div>

          {datasetImport && (
            <>
              <ResultList
                title="Mapped gene IDs"
                items={(datasetImport.mapped_genes?.length ? datasetImport.mapped_genes : datasetImport.mapped_gene_ids)?.slice(0, 8)}
                renderItem={(item) => <GeneBadge item={item} labelOverrides={labelOverrides} />}
              />
              <ResultList
                title="Ambiguous or unmapped rows"
                items={datasetImport.unmapped_rows?.slice(0, 5)}
                renderItem={(item) => <span>{item.input || item}</span>}
                emptyText="No unmapped rows."
              />
            </>
          )}
        </section>
      </div>

      <div className="workflow-grid">
        <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>4. First-pass interpretation</h2>
              <p>Turn a mapped hit list into upstream regulators, candidate ranking, and an interpretable subgraph.</p>
            </div>
            <button onClick={handleFirstPassAnalysis} disabled={loading.analysis}>
              {loading.analysis ? 'Running…' : 'Run first-pass analysis'}
            </button>
          </div>

          {geneSetAnalysis ? (
            <>
              <div className="workflow-summary-box">
                <strong>{geneSetAnalysis.analyzed_gene_count}</strong> genes analyzed in{' '}
                <strong>{geneSetAnalysis.species}</strong> for <strong>{geneSetAnalysis.intent}</strong>.
              </div>
              <ResultList
                title="Top candidates"
                items={geneSetAnalysis.candidate_triage?.ranked_candidates?.slice(0, 5)}
                renderItem={(item) => (
                  <span>
                    <GeneBadge item={item} labelOverrides={labelOverrides} />
                    {item.priority_score != null && <span className="workflow-faint"> · score {item.priority_score.toFixed(3)}</span>}
                  </span>
                )}
              />
              <ResultList
                title="Top upstream regulators"
                items={geneSetAnalysis.upstream_regulators?.regulators?.slice(0, 5)}
                renderItem={(item) => (
                  <span>
                    <GeneBadge item={item} labelOverrides={labelOverrides} />
                    {item.overlap_count != null && <span className="workflow-faint"> · overlap {item.overlap_count}</span>}
                  </span>
                )}
              />
              <ResultList
                title="Representative enrichment terms"
                items={(geneSetAnalysis.enrichment?.results || geneSetAnalysis.enrichment?.enriched_terms || []).slice(0, 5)}
                renderItem={(item) => (
                  <span>
                    <strong>{item.term || item.name}</strong>
                    {item.p_adj != null && <span className="workflow-faint"> · FDR {item.p_adj}</span>}
                  </span>
                )}
              />
              <JsonPreview title="Full first-pass payload" data={geneSetAnalysis} />
            </>
          ) : (
            <div className="workflow-empty-inline">No first-pass analysis has been run yet.</div>
          )}
        </section>

        <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>4. Rank candidates and ask what would change the conclusion</h2>
              <p>Use the consensus layer for a robust winner, then inspect what evidence would overturn it.</p>
            </div>
            <button onClick={handleConsensus} disabled={loading.consensus}>
              {loading.consensus ? 'Ranking…' : 'Run consensus ranking'}
            </button>
          </div>

          {consensus ? (
            <>
              <ResultList
                title="Consensus ranking"
                items={consensus.ranked_candidates?.slice(0, 5)}
                renderItem={(item) => (
                  <span>
                    <GeneBadge item={item} labelOverrides={labelOverrides} />
                    <span className="workflow-faint"> · consensus {item.consensus_score?.toFixed?.(3) ?? item.consensus_score}</span>
                  </span>
                )}
              />
              <ResultList
                title="Overturn conditions"
                items={counterfactual?.overturn_conditions?.slice(0, 5)}
                renderItem={(item) => <span>{item.summary || item.reason || JSON.stringify(item)}</span>}
                emptyText="No overturn analysis yet."
              />
              <JsonPreview title="Full ranking payload" data={consensus} />
            </>
          ) : (
            <div className="workflow-empty-inline">Consensus ranking has not been run yet.</div>
          )}
        </section>
      </div>

      <div className="workflow-grid">
        <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>5. Convert evidence into an execution plan</h2>
              <p>Generate a research brief, validation plan, collaborator report, and constraint-aware experiment recommendations.</p>
            </div>
            <button onClick={handleStudyPlanning} disabled={loading.planning}>
              {loading.planning ? 'Planning…' : 'Build study plan'}
            </button>
          </div>

          <div className="workflow-form-grid">
            <label className="workflow-field">
              <span>Budget level</span>
              <select value={budgetLevel} onChange={(e) => setBudgetLevel(e.target.value)}>
                <option value="low">Low — cheapest, lightest follow-up</option>
                <option value="medium">Medium — balanced default</option>
                <option value="high">High — allow broader or costlier follow-up</option>
              </select>
              <small className="workflow-help-text">Controls how aggressively the planner favors more involved follow-up steps.</small>
            </label>
            <label className="workflow-field">
              <span>Timeline to a usable next step (days)</span>
              <input type="number" min="1" value={timelineDays} onChange={(e) => setTimelineDays(e.target.value)} />
              <small className="workflow-help-text">Shorter timelines favor quicker analyses; longer timelines allow more involved follow-up.</small>
            </label>
            <div className="workflow-field workflow-field-span-2">
              <span>Allowed follow-up types</span>
              <small className="workflow-help-text">Choose the kinds of evidence or assay work you are willing to consider in the plan.</small>
              <div className="workflow-checkbox-grid">
                {ASSAY_OPTIONS.map((option) => (
                  <label key={option.value} className="workflow-checkbox-card">
                    <input
                      type="checkbox"
                      checked={selectedAssays.includes(option.value)}
                      onChange={() => handleAssayToggle(option.value)}
                    />
                    <div>
                      <div className="workflow-checkbox-title">{option.label}</div>
                      <div className="workflow-checkbox-description">{option.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>

          {researchBrief && (
            <>
              <div className="workflow-summary-box">
                {researchBrief.executive_summary || 'Research brief generated.'}
              </div>
              <ResultList
                title="Workflow plan"
                items={researchBrief.workflow_plan || []}
                renderItem={(item) => <span>{item.title || item.step || JSON.stringify(item)}</span>}
              />
              <ResultList
                title="Execution checklist"
                items={validationPlan?.execution_checklist || []}
                renderItem={(item) => <span>{item.title || item.step || JSON.stringify(item)}</span>}
                emptyText="No validation plan yet."
              />
              <ResultList
                title="Optimized experiments"
                items={experimentPlan?.ranked_experiments?.slice(0, 5)}
                renderItem={(item) => (
                  <span>
                    <GeneBadge item={item} labelOverrides={labelOverrides} />
                    <span className="workflow-faint"> · {item.experiment} · score {item.optimized_priority_score?.toFixed?.(2) ?? item.optimized_priority_score}</span>
                  </span>
                )}
                emptyText="No optimized experiment plan yet."
              />
              {studyReport?.markdown && (
                <details className="workflow-markdown">
                  <summary>Collaborator-facing report</summary>
                  <pre>{studyReport.markdown}</pre>
                </details>
              )}
            </>
          )}
        </section>

        <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>6. Differential expression to follow-up queue</h2>
              <p>Compare tissues or conditions, then feed the strongest hits into prioritization.</p>
            </div>
            <button onClick={handleDifferential} disabled={loading.differential}>
              {loading.differential ? 'Comparing…' : 'Run contrast'}
            </button>
          </div>

          <div className="workflow-form-grid">
            <label className="workflow-field">
              <span>Group A</span>
              <input value={groupAText} onChange={(e) => setGroupAText(e.target.value)} placeholder="root,seedling" />
              <small className="workflow-help-text">Samples or tissues to compare as the reference group.</small>
            </label>
            <label className="workflow-field">
              <span>Group B</span>
              <input value={groupBText} onChange={(e) => setGroupBText(e.target.value)} placeholder="inflorescence" />
              <small className="workflow-help-text">Samples or tissues to compare against Group A.</small>
            </label>
          </div>

          <div className="workflow-result-block">
            <div className="workflow-result-title">Available tissue labels for {species}</div>
            <div className="workflow-help-text">Click labels to add or remove them from Group A or Group B.</div>
            {availableTissues.length > 0 ? (
              <div className="workflow-tissue-grid">
                {availableTissues.map((tissue) => {
                  const inA = splitTokens(groupAText).includes(tissue);
                  const inB = splitTokens(groupBText).includes(tissue);
                  return (
                    <div key={tissue} className="workflow-tissue-card">
                      <div className="workflow-tissue-name">{tissue}</div>
                      <div className="workflow-inline-actions">
                        <button
                          type="button"
                          className={`workflow-chip-btn${inA ? ' workflow-chip-btn-active' : ''}`}
                          onClick={() => toggleGroupToken(setGroupAText, groupAText, tissue)}
                        >
                          {inA ? 'Remove from A' : 'Add to A'}
                        </button>
                        <button
                          type="button"
                          className={`workflow-chip-btn${inB ? ' workflow-chip-btn-active-b' : ''}`}
                          onClick={() => toggleGroupToken(setGroupBText, groupBText, tissue)}
                        >
                          {inB ? 'Remove from B' : 'Add to B'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="workflow-empty-inline">No tissue labels loaded for this species yet.</div>
            )}
          </div>

          {differential && (
            <>
              <div className="workflow-summary-box">
                Compared <strong>{differential.group_a?.join(', ')}</strong> vs{' '}
                <strong>{differential.group_b?.join(', ')}</strong> in <strong>{differential.species}</strong>.
                <div className="workflow-help-text" style={{ marginTop: 8 }}>
                  Negative log2FC means higher in <strong>{differential.group_a?.join(', ') || 'Group A'}</strong>.
                  Positive log2FC means higher in <strong>{differential.group_b?.join(', ') || 'Group B'}</strong>.
                </div>
              </div>
              <ResultList
                title="Current candidate genes in this contrast"
                items={differentialCandidateRows.slice(0, 8)}
                renderItem={(item) => (
                  <span>
                    <GeneBadge item={item} labelOverrides={labelOverrides} />
                    <span className="workflow-faint"> · {differentialDirectionText(item, differential.group_a, differential.group_b)} · log2FC {item.log2fc?.toFixed?.(2) ?? item.log2fc}</span>
                  </span>
                )}
                emptyText="None of the current hit-list candidates are among the returned shifted genes for this contrast."
              />
              <label className="workflow-toggle-inline">
                <input
                  type="checkbox"
                  checked={showCandidateOnlyInDifferential}
                  onChange={() => setShowCandidateOnlyInDifferential((v) => !v)}
                />
                <span>Show only current candidate genes</span>
              </label>
              <ResultList
                title={showCandidateOnlyInDifferential ? 'Candidate-focused shifted genes' : 'Top shifted genes'}
                items={displayedDifferentialRows}
                renderItem={(item) => (
                  <span>
                    <GeneBadge item={item} labelOverrides={labelOverrides} />
                    <span className="workflow-faint"> · {differentialDirectionText(item, differential.group_a, differential.group_b)} · log2FC {item.log2fc?.toFixed?.(2) ?? item.log2fc}</span>
                  </span>
                )}
                emptyText={showCandidateOnlyInDifferential ? 'No current candidate genes are shown in this contrast.' : 'No shifted genes returned for this contrast.'}
              />
              <JsonPreview title="Full differential payload" data={differential} />
            </>
          )}
        </section>
      </div>

      <div className="workflow-grid">
        <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>7. Check current external literature</h2>
              <p>Use external evidence only after the atlas-backed interpretation is clear.</p>
            </div>
            <button onClick={handleLiterature} disabled={loading.literature || !literatureTargetId}>
              {loading.literature ? 'Reviewing…' : 'Review literature'}
            </button>
          </div>

          <div className="workflow-form-grid">
            <label className="workflow-field">
              <span>Literature target</span>
              <select value={literatureTargetId} onChange={(e) => setLiteratureTargetId(e.target.value)}>
                {literatureTargetOptions.map((gene) => (
                  <option key={gene.id} value={gene.id}>
                    {gene.label}{gene.id !== gene.label ? ` · ${gene.id}` : ''}
                  </option>
                ))}
              </select>
              <small className="workflow-help-text">Choose which mapped or candidate gene to query in the external literature review.</small>
            </label>
          </div>

          {selectedLiteratureTarget ? (
            <div className="workflow-summary-box">
              Current literature query target: <strong>{selectedLiteratureTarget.label}</strong> ({selectedLiteratureTarget.id})
            </div>
          ) : (
            <div className="workflow-empty-inline">Map a hit list or select a focus gene to populate literature targets.</div>
          )}

          {literature && (
            <>
              <ResultList
                title="Recent papers"
                items={literature.results?.slice(0, 6)}
                renderItem={(item) => (
                  <span>
                    <strong>{item.year}</strong> · {item.title}
                    <span className="workflow-faint"> · {item.classification}</span>
                  </span>
                )}
              />
              <div className="workflow-inline-actions">
                <StatusPill tone="success">support {literature.summary?.support ?? 0}</StatusPill>
                <StatusPill tone="danger">contradict {literature.summary?.contradict ?? 0}</StatusPill>
                <StatusPill tone="neutral">mention {literature.summary?.mention ?? 0}</StatusPill>
              </div>
              <JsonPreview title="Full literature payload" data={literature} />
            </>
          )}
        </section>

        <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>8. Move from regulatory site to assay design</h2>
              <p>Variant overlap, promoter-site prioritization, and lightweight guide/primer suggestions in one place.</p>
            </div>
            <button onClick={handleVariantDesign} disabled={loading.design || !selectedGene}>
              {loading.design ? 'Designing…' : 'Run design workflow'}
            </button>
          </div>

          <div className="workflow-form-grid">
            <label className="workflow-field">
              <span>Variant position</span>
              <input value={variantPosition} onChange={(e) => setVariantPosition(e.target.value)} placeholder="1900" />
            </label>
            <label className="workflow-field">
              <span>Ref / Alt</span>
              <div className="workflow-split-field">
                <input value={variantRef} onChange={(e) => setVariantRef(e.target.value)} placeholder="A" />
                <input value={variantAlt} onChange={(e) => setVariantAlt(e.target.value)} placeholder="G" />
              </div>
            </label>
            <label className="workflow-field workflow-field-span-2">
              <span>Optional sequence override</span>
              <textarea
                rows={3}
                value={sequenceText}
                onChange={(e) => setSequenceText(e.target.value)}
                placeholder="Paste genomic or amplicon sequence if you want sequence-driven guide/primer suggestions."
              />
            </label>
          </div>

          {variantEffect && (
            <>
              <ResultList
                title="Variant overlap"
                items={variantEffect.results || []}
                renderItem={(item) => <span>{item.tf_symbol || item.tf_gene_id} · {item.site_start}-{item.site_end}</span>}
                emptyText={variantEffect.warnings?.[0] || 'No overlapping motif-supported sites.'}
              />
              <ResultList
                title="Promoter edit priorities"
                items={promoterPlan?.results?.slice(0, 5) || promoterPlan?.prioritized_sites?.slice(0, 5)}
                renderItem={(item) => <span>{item.tf_symbol || item.tf_gene_id || item.window_label || JSON.stringify(item)}</span>}
                emptyText="No promoter prioritization yet."
              />
              <ResultList
                title="CRISPR guides"
                items={crisprGuides?.guides?.slice(0, 5)}
                renderItem={(item) => <code>{item.sequence || item.guide || JSON.stringify(item)}</code>}
                emptyText="No guide suggestions yet."
              />
              <ResultList
                title="Primer pairs"
                items={primerPairs?.primers?.slice(0, 4) || primerPairs?.pairs?.slice(0, 4)}
                renderItem={(item) => <code>{item.forward || item.left_primer} / {item.reverse || item.right_primer}</code>}
                emptyText="No primer suggestions yet."
              />
            </>
          )}
        </section>
      </div>

      <div className="workflow-grid">
        <section className="workflow-card workflow-card-advanced">
          <div className="workflow-card-header">
            <div>
              <h2>9. Advanced and future-state workflows</h2>
              <p>Surface readiness honestly when the atlas does not yet support the requested biology directly.</p>
            </div>
            <button onClick={handleAdvanced} disabled={loading.advanced}>
              {loading.advanced ? 'Checking…' : 'Run readiness checks'}
            </button>
          </div>

          <div className="workflow-form-grid">
            <label className="workflow-field">
              <span>Readiness species</span>
              <input value={advancedSpecies} onChange={(e) => handleAdvancedSpeciesInputChange(e.target.value)} placeholder="human" />
            </label>
            <label className="workflow-field">
              <span>Future species onboarding</span>
              <input value={onboardingSpeciesName} onChange={(e) => setOnboardingSpeciesName(e.target.value)} placeholder="wheat" />
            </label>
          </div>

          {(celltypeReadiness || trajectoryReadiness || combinatorialPlan || onboardingPlan) && (
            <>
              <div className="workflow-advanced-grid">
                <div className="workflow-summary-box">
                  <div className="workflow-result-title">Cell-type readiness</div>
                  <p>{celltypeReadiness?.reason || 'Not run yet.'}</p>
                </div>
                <div className="workflow-summary-box">
                  <div className="workflow-result-title">Trajectory readiness</div>
                  <p>{trajectoryReadiness?.reason || 'Not run yet.'}</p>
                </div>
                <div className="workflow-summary-box">
                  <div className="workflow-result-title">Combinatorial perturbations</div>
                  <p>
                    {combinatorialPlan?.ranked_combinations?.length
                      ? `${combinatorialPlan.ranked_combinations.length} combinations ranked.`
                      : 'No combination ranking run.'}
                  </p>
                </div>
                <div className="workflow-summary-box">
                  <div className="workflow-result-title">Species onboarding</div>
                  <p>{onboardingPlan?.note || 'No onboarding plan yet.'}</p>
                </div>
              </div>
              <JsonPreview title="Advanced readiness payloads" data={{
                celltypeReadiness,
                trajectoryReadiness,
                combinatorialPlan,
                onboardingPlan,
              }} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}
