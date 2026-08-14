import React from 'react';
import {
  GeneBadge,
  LiteraturePaperItem,
  ResultList,
  StatusPill,
} from './WorkflowCommon';

export function ContextSection({
  intent,
  setIntent,
  species,
  handleSpeciesInputChange,
  selectedGene,
  selectedLabel,
  networkStats,
  networkData,
  filters,
  onNavigate,
  onOpenDsRna,
  dsRnaSeedTarget,
  dsRnaCompareTarget,
  dsRnaSeedSet,
  intentOptions,
}) {
  return (
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
          <strong>{intentOptions.find((opt) => opt.value === intent)?.label}</strong>
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
            {intentOptions.map((option) => (
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
            <button onClick={() => onNavigate?.('advanced:network')}>Network</button>
            <button onClick={() => onNavigate?.('advanced:pathways')}>Paths</button>
            <button onClick={() => onNavigate?.('advanced:comparison')}>Orthology</button>
            <button onClick={() => onOpenDsRna?.({ target: dsRnaSeedTarget, compareTarget: dsRnaCompareTarget, geneSet: dsRnaSeedSet })}>dsRNA</button>
          </div>
        </div>
      )}
    </section>
  );
}

export function PhenotypeSection({
  handlePhenotypeLiterature,
  loading,
  phenotypeQuestion,
  setPhenotypeQuestion,
  phenotypeLiterature,
  species,
  phenotypeAtlasMappedGenes,
  labelOverrides,
  phenotypeDisplayCandidates,
  phenotypeAtlasUnmappedRows,
  handleLoadPhenotypeSuggestions,
  phenotypeCombinedCandidates,
  phenotypeRescueCandidates,
  phenotypeSuggestedGenes,
}) {
  return (
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
  );
}

export function ImportSection({
  handleImport,
  loading,
  onOpenGeneSetAnalysis,
  geneSetText,
  setGeneSetText,
  geneCount,
  datasetImport,
  labelOverrides,
}) {
  return (
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
  );
}

export function PlanningSection({
  handleStudyPlanning,
  loading,
  budgetLevel,
  setBudgetLevel,
  timelineDays,
  setTimelineDays,
  selectedAssays,
  assayOptions,
  handleAssayToggle,
  researchBrief,
  validationPlan,
  experimentPlan,
  studyReport,
  labelOverrides,
}) {
  return (
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
            {assayOptions.map((option) => (
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
  );
}
