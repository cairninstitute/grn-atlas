import React, { useEffect, useMemo, useState } from 'react';
import { workflowAPI } from '../services/apiService';
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

function splitTokens(text) {
  return text.split(/[\s,;]+/).map((token) => token.trim()).filter(Boolean);
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

export default function WorkflowWorkspace({
  selectedGene,
  networkData,
  filters,
  onNavigate,
  onOpenGeneSetAnalysis,
  onOpenDsRna,
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
  const [literature, setLiterature] = useState(null);
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
  const [groupAText, setGroupAText] = useState('root');
  const [groupBText, setGroupBText] = useState('inflorescence');
  const [variantPosition, setVariantPosition] = useState('');
  const [variantRef, setVariantRef] = useState('');
  const [variantAlt, setVariantAlt] = useState('');
  const [sequenceText, setSequenceText] = useState('');
  const [advancedSpecies, setAdvancedSpecies] = useState(selectedGene?.species || filters?.species?.[0] || 'human');
  const [onboardingSpeciesName, setOnboardingSpeciesName] = useState('wheat');

  const seededGeneIds = useMemo(() => {
    if (!selectedGene) return [];
    const ids = new Set([selectedGene.id]);
    (networkData?.regulators || []).slice(0, 5).forEach((gene) => ids.add(gene.id));
    (networkData?.targets || []).slice(0, 5).forEach((gene) => ids.add(gene.id));
    return [...ids];
  }, [selectedGene, networkData]);

  useEffect(() => {
    if (selectedGene?.species) {
      setSpecies(selectedGene.species);
      setAdvancedSpecies(selectedGene.species);
    }
  }, [selectedGene]);

  useEffect(() => {
    if (!geneSetText && seededGeneIds.length > 0) {
      setGeneSetText(seededGeneIds.join('\n'));
    }
  }, [seededGeneIds, geneSetText]);

  const mappedGeneIds = datasetImport?.mapped_gene_ids || geneSetAnalysis?.import_summary?.mapped_gene_ids || [];
  const geneCount = splitTokens(geneSetText).length;

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
        top: 20,
      });
      if (result?.detail) throw new Error(result.detail);
      setDifferential(result);
      return result;
    });
  };

  const handleLiterature = async () => {
    if (!selectedGene?.id) {
      setError('Select a focus gene first to review external literature.');
      return;
    }
    await runStep('literature', async () => {
      const result = await workflowAPI.literatureReview({
        scope: 'gene',
        geneId: selectedGene.id,
        yearsBack: 5,
        maxResults: 8,
      });
      if (result?.detail) throw new Error(result.detail);
      setLiterature(result);
      return result;
    });
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
  const networkStats = networkData?.stats || {};

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
              <input value={species} onChange={(e) => setSpecies(e.target.value)} placeholder="human" />
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
                <button onClick={() => onOpenDsRna?.()}>dsRNA</button>
              </div>
            </div>
          )}
        </section>

        <section className="workflow-card workflow-card-input">
          <div className="workflow-card-header">
            <div>
              <h2>2. Import a hit list</h2>
              <p>Paste gene symbols or IDs and normalize them before downstream analysis.</p>
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
            placeholder="TP53&#10;BAX&#10;MDM2"
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
                items={datasetImport.mapped_gene_ids?.slice(0, 8)}
                renderItem={(item) => <code>{item}</code>}
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
              <h2>3. First-pass interpretation</h2>
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
                    <strong>{item.symbol || item.gene_id}</strong>
                    {item.priority_score != null && <span className="workflow-faint"> · score {item.priority_score.toFixed(3)}</span>}
                  </span>
                )}
              />
              <ResultList
                title="Top upstream regulators"
                items={geneSetAnalysis.upstream_regulators?.regulators?.slice(0, 5)}
                renderItem={(item) => (
                  <span>
                    <strong>{item.symbol || item.gene_id}</strong>
                    {item.overlap != null && <span className="workflow-faint"> · overlap {item.overlap}</span>}
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
                    <strong>{item.symbol || item.gene_id}</strong>
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
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </label>
            <label className="workflow-field">
              <span>Timeline (days)</span>
              <input type="number" min="1" value={timelineDays} onChange={(e) => setTimelineDays(e.target.value)} />
            </label>
            <label className="workflow-field workflow-field-span-2">
              <span>Allowed assays</span>
              <input value={allowedAssays} onChange={(e) => setAllowedAssays(e.target.value)} placeholder="in_silico,expression,comparative" />
            </label>
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
                    <strong>{item.symbol || item.gene_id}</strong>
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
            </label>
            <label className="workflow-field">
              <span>Group B</span>
              <input value={groupBText} onChange={(e) => setGroupBText(e.target.value)} placeholder="inflorescence" />
            </label>
          </div>

          {differential && (
            <>
              <div className="workflow-summary-box">
                Compared <strong>{differential.group_a?.join(', ')}</strong> vs{' '}
                <strong>{differential.group_b?.join(', ')}</strong> in <strong>{differential.species}</strong>.
              </div>
              <ResultList
                title="Top shifted genes"
                items={differential.results?.slice(0, 8)}
                renderItem={(item) => (
                  <span>
                    <strong>{item.symbol || item.gene_id}</strong>
                    <span className="workflow-faint"> · log2FC {item.log2fc?.toFixed?.(2) ?? item.log2fc}</span>
                  </span>
                )}
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
            <button onClick={handleLiterature} disabled={loading.literature || !selectedGene}>
              {loading.literature ? 'Reviewing…' : 'Review literature'}
            </button>
          </div>

          {selectedGene ? (
            <div className="workflow-summary-box">
              Current literature query target: <strong>{selectedLabel}</strong> ({selectedGene.id})
            </div>
          ) : (
            <div className="workflow-empty-inline">Select a focus gene to review recent literature.</div>
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
              <input value={advancedSpecies} onChange={(e) => setAdvancedSpecies(e.target.value)} placeholder="human" />
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
