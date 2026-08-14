import React, { useEffect, useMemo, useState } from 'react';
import { geneAPI, workflowAPI } from '../services/apiService';
import { geneLabel } from '../utils/geneLabel';
import NetworkVisualization from './NetworkVisualization';
import {
  GeneBadge,
  JsonPreview,
  ResultList,
  StatusPill,
  buildPhenotypeRescueQueries,
  dedupePhenotypeCandidates,
  describeGene,
  differentialDirectionText,
  parseAssayText,
  splitTokens,
  uniqueBy,
  uniqueSuggestedGenes,
} from './workflow/WorkflowCommon';
import {
  ContextSection,
  ImportSection,
  PhenotypeSection,
  PlanningSection,
} from './workflow/WorkflowSections';
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
  onNetworkDepthChange,
  onSessionSync,
  visibleSections = ['context', 'phenotype', 'import', 'analysis', 'consensus', 'planning', 'differential', 'literature', 'design', 'advanced'],
  kicker = 'Workflow-first workspace',
  title = 'Run the atlas like a study, not a demo.',
  subtitle = 'Start from a focus gene, hit list, or condition contrast. Move from interpretation to ranking, validation, and assay design without switching mental models.',
  showHero = true,
  showExamples = true,
}) {
  const stepNumberFor = useMemo(() => {
    const stepMap = new Map();
    visibleSections.forEach((section, index) => {
      stepMap.set(section, index + 1);
    });
    return (section) => stepMap.get(section) || '?';
  }, [visibleSections]);

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

  const workflowCandidateSet = useMemo(
    () => uniqueBy([
      ...(consensus?.ranked_candidates || []),
      ...(geneSetAnalysis?.candidate_triage?.ranked_candidates || []),
      ...(datasetImport?.mapped_genes || []),
      ...phenotypeCombinedCandidates,
      ...(selectedGene ? [selectedGene] : []),
    ], (gene) => gene?.gene_id || gene?.id),
    [consensus, geneSetAnalysis, datasetImport, phenotypeCombinedCandidates, selectedGene],
  );

  useEffect(() => {
    onSessionSync?.({
      species,
      intent,
      focusGene: dsRnaSeedTarget || selectedGene || null,
      candidateSet: workflowCandidateSet,
      mappedGeneIds,
      phenotypeQuestion,
      comparison: {
        groupA: splitTokens(groupAText),
        groupB: splitTokens(groupBText),
      },
      artifacts: {
        firstPass: geneSetAnalysis ? {
          summary: `${geneSetAnalysis.analyzed_gene_count || mappedGeneIds.length || 0} genes analyzed in ${geneSetAnalysis.species || species || 'selected species'}.`,
          detail: JSON.stringify({
            topCandidates: (geneSetAnalysis.candidate_triage?.ranked_candidates || []).slice(0, 3).map((g) => g.label || g.symbol || g.gene_id),
            topRegulators: (geneSetAnalysis.upstream_regulators?.regulators || []).slice(0, 3).map((g) => g.label || g.symbol || g.gene_id),
          }, null, 2),
        } : null,
        consensus: consensus ? {
          summary: `Top candidate: ${consensus.ranked_candidates?.[0]?.label || consensus.ranked_candidates?.[0]?.symbol || consensus.ranked_candidates?.[0]?.gene_id || 'unknown'}.`,
          detail: JSON.stringify({
            rankedCandidates: (consensus.ranked_candidates || []).slice(0, 5).map((g) => ({
              gene: g.label || g.symbol || g.gene_id,
              score: g.consensus_score,
            })),
            overturn: (counterfactual?.overturn_conditions || []).slice(0, 2).map((item) => item.summary || item.reason || item),
          }, null, 2),
        } : null,
        plan: (researchBrief || validationPlan || experimentPlan) ? {
          summary: researchBrief?.executive_summary || `${experimentPlan?.ranked_experiments?.length || 0} optimized experiments available.`,
          detail: JSON.stringify({
            workflowPlan: (researchBrief?.workflow_plan || []).slice(0, 4).map((x) => x.title || x.step || x),
            checklist: (validationPlan?.execution_checklist || []).slice(0, 4).map((x) => x.title || x.step || x),
            experiments: (experimentPlan?.ranked_experiments || []).slice(0, 3).map((x) => ({
              gene: x.label || x.symbol || x.gene_id,
              experiment: x.experiment,
              score: x.optimized_priority_score,
            })),
          }, null, 2),
        } : null,
        report: studyReport?.markdown ? {
          summary: 'Collaborator-facing report generated.',
          detail: studyReport.markdown.slice(0, 800),
        } : null,
      },
    });
  }, [
    onSessionSync,
    species,
    intent,
    dsRnaSeedTarget,
    selectedGene,
    workflowCandidateSet,
    mappedGeneIds,
    phenotypeQuestion,
    groupAText,
    groupBText,
    geneSetAnalysis,
    consensus,
    counterfactual,
    researchBrief,
    validationPlan,
    experimentPlan,
    studyReport,
  ]);

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

  const showSection = (id) => visibleSections.includes(id);

  return (
    <div className="workflow-workspace">
      {showHero && (
        <div className="workflow-hero">
          <div>
            <p className="workflow-kicker">{kicker}</p>
            <h1>{title}</h1>
            <p className="workflow-subtitle">{subtitle}</p>
          </div>
          <div className="workflow-hero-actions">
            <button onClick={() => onNavigate?.('advanced:network')}>Open explorer</button>
            <button onClick={() => onNavigate?.('advanced:organism')}>Browse organisms</button>
            <button onClick={() => onNavigate?.('advanced:analysis')}>Open analysis lab</button>
          </div>
        </div>
      )}

      {error && <div className="workflow-error">{error}</div>}

      {showExamples && (
        <div className="workflow-example-grid">
          {EXAMPLE_WORKFLOWS.map((example) => (
            <div key={example.title} className="workflow-example-card">
              <div className="workflow-example-title">{example.title}</div>
              <p>{example.description}</p>
              <StatusPill>{example.action}</StatusPill>
            </div>
          ))}
        </div>
      )}

      {(showSection('context') || showSection('phenotype')) && <div className="workflow-grid workflow-grid-top">
        {showSection('context') && (
          <ContextSection
            stepNumber={stepNumberFor('context')}
            intent={intent}
            setIntent={setIntent}
            species={species}
            handleSpeciesInputChange={handleSpeciesInputChange}
            selectedGene={selectedGene}
            selectedLabel={selectedLabel}
            networkStats={networkStats}
            networkData={networkData}
            filters={filters}
            onNavigate={onNavigate}
            onOpenDsRna={onOpenDsRna}
            dsRnaSeedTarget={dsRnaSeedTarget}
            dsRnaCompareTarget={dsRnaCompareTarget}
            dsRnaSeedSet={dsRnaSeedSet}
            intentOptions={INTENT_OPTIONS}
          />
        )}

        {showSection('phenotype') && (
          <PhenotypeSection
            stepNumber={stepNumberFor('phenotype')}
            handlePhenotypeLiterature={handlePhenotypeLiterature}
            loading={loading}
            phenotypeQuestion={phenotypeQuestion}
            setPhenotypeQuestion={setPhenotypeQuestion}
            phenotypeLiterature={phenotypeLiterature}
            species={species}
            phenotypeAtlasMappedGenes={phenotypeAtlasMappedGenes}
            labelOverrides={labelOverrides}
            phenotypeDisplayCandidates={phenotypeDisplayCandidates}
            phenotypeAtlasUnmappedRows={phenotypeAtlasUnmappedRows}
            handleLoadPhenotypeSuggestions={handleLoadPhenotypeSuggestions}
            phenotypeCombinedCandidates={phenotypeCombinedCandidates}
            phenotypeRescueCandidates={phenotypeRescueCandidates}
            phenotypeSuggestedGenes={phenotypeSuggestedGenes}
          />
        )}
      </div>}

      {showSection('import') && <div className="workflow-grid">
        <ImportSection
          stepNumber={stepNumberFor('import')}
          handleImport={handleImport}
          loading={loading}
          onOpenGeneSetAnalysis={onOpenGeneSetAnalysis}
          geneSetText={geneSetText}
          setGeneSetText={setGeneSetText}
          geneCount={geneCount}
          datasetImport={datasetImport}
          labelOverrides={labelOverrides}
        />
      </div>}

      {(showSection('analysis') || showSection('consensus')) && <div className="workflow-grid">
        {showSection('analysis') && <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>{stepNumberFor('analysis')}. First-pass interpretation</h2>
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
              {selectedGene && networkData ? (
                <div className="workflow-result-block">
                  <div className="workflow-result-title">Current neighborhood graph</div>
                  <div className="workflow-help-text" style={{ marginTop: '0.35rem', marginBottom: '0.75rem' }}>
                    Use 1-, 2-, or 3-hop expansion to reconcile the first-pass interpretation and dsRNA downstream predictions with the network view.
                  </div>
                  <div style={{ minHeight: 520, borderRadius: 14, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <NetworkVisualization
                      gene={selectedGene}
                      data={networkData}
                      filters={filters}
                      onDepthChange={onNetworkDepthChange}
                    />
                  </div>
                </div>
              ) : null}
              <JsonPreview title="Full first-pass payload" data={geneSetAnalysis} />
            </>
          ) : (
            <div className="workflow-empty-inline">No first-pass analysis has been run yet.</div>
          )}
        </section>}

        {showSection('consensus') && <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>{stepNumberFor('consensus')}. Rank candidates and ask what would change the conclusion</h2>
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
        </section>}
      </div>}

      {(showSection('planning') || showSection('differential')) && <div className="workflow-grid">
        {showSection('planning') && (
          <PlanningSection
            stepNumber={stepNumberFor('planning')}
            handleStudyPlanning={handleStudyPlanning}
            loading={loading}
            budgetLevel={budgetLevel}
            setBudgetLevel={setBudgetLevel}
            timelineDays={timelineDays}
            setTimelineDays={setTimelineDays}
            selectedAssays={selectedAssays}
            assayOptions={ASSAY_OPTIONS}
            handleAssayToggle={handleAssayToggle}
            researchBrief={researchBrief}
            validationPlan={validationPlan}
            experimentPlan={experimentPlan}
            studyReport={studyReport}
            labelOverrides={labelOverrides}
          />
        )}

        {showSection('differential') && <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>{stepNumberFor('differential')}. Differential expression to follow-up queue</h2>
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
        </section>}
      </div>}

      {(showSection('literature') || showSection('design')) && <div className="workflow-grid">
        {showSection('literature') && <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>{stepNumberFor('literature')}. Check current external literature</h2>
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
        </section>}

        {showSection('design') && <section className="workflow-card">
          <div className="workflow-card-header">
            <div>
              <h2>{stepNumberFor('design')}. Promoter editing and assay setup</h2>
              <p>Check promoter-site overlap, prioritize edit sites, and generate lightweight CRISPR guide and primer suggestions.</p>
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
        </section>}
      </div>}

      {showSection('advanced') && <div className="workflow-grid">
        <section className="workflow-card workflow-card-advanced">
          <div className="workflow-card-header">
            <div>
              <h2>{stepNumberFor('advanced')}. Advanced and future-state workflows</h2>
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
      </div>}
    </div>
  );
}
