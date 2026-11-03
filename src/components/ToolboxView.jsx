import React, { useState, useCallback, useMemo } from 'react';
import RegulonPanel from './RegulonPanel';
import RegulonComparePanel from './RegulonComparePanel';
import UpstreamPanel from './UpstreamPanel';
import RegulonEnrichmentPanel from './RegulonEnrichmentPanel';
import TFActivityPanel from './TFActivityPanel';
import NetworkPatternsPanel from './NetworkPatternsPanel';
import CentralityPanel from './CentralityPanel';
import InferredEdgesPanel from './InferredEdgesPanel';
import ModulePanel from './ModulePanel';
import MotifQueryPanel from './MotifQueryPanel';
import DiffRegulationPanel from './DiffRegulationPanel';
import ValidationDashboard from './ValidationDashboard';
import OmicsImportPanel from './OmicsImportPanel';
import ExportPanel from './ExportPanel';
import InferredEnrichmentWorkflow from './InferredEnrichmentWorkflow';
import ModuleMotifWorkflow from './ModuleMotifWorkflow';
import RegulonDiffWorkflow from './RegulonDiffWorkflow';
import InferredValidationWorkflow from './InferredValidationWorkflow';
import MultiomeAuditPanel from './MultiomeAuditPanel';
import CrisprVsDsrnaPanel from './CrisprVsDsrnaPanel';
import EditConsequencePanel from './EditConsequencePanel';
import InterventionRankerPanel from './InterventionRankerPanel';
import LiteratureGroundingPanel from './LiteratureGroundingPanel';
import TransitionDriversPanel from './TransitionDriversPanel';
import '../styles/ToolboxView.css';

const CATEGORIES = {
  regulators: 'Regulators',
  phenotype: 'Phenotype',
  evidence: 'Evidence',
  intervention: 'Intervention',
  workflow: 'Workflow',
  data: 'Import / Export',
};

const TOOLS = [
  { id: 'upstream', title: 'Upstream Regulators', desc: 'Which TFs have your gene in their regulon?', component: UpstreamPanel, category: 'regulators', accepts: 'sharedGeneSet' },
  { id: 'regulon-enrichment', title: 'Regulon Enrichment', desc: 'Test which TF regulons are enriched in a gene list', component: RegulonEnrichmentPanel, category: 'regulators', accepts: 'sharedGeneSet' },
  { id: 'tf-activity', title: 'TF / Pathway Activity', desc: 'Infer TF or pathway activity from expression data', component: TFActivityPanel, category: 'regulators', accepts: 'sharedGeneSet' },
  { id: 'regulon', title: 'Regulon Extraction', desc: 'See the full downstream target list of a candidate TF', component: RegulonPanel, category: 'regulators', accepts: 'sharedGeneSet', shares: true },
  { id: 'compare', title: 'Regulon Comparison', desc: 'Compare regulons of two TFs side by side', component: RegulonComparePanel, category: 'regulators', shares: true },
  { id: 'motif', title: 'Motif Query', desc: 'Check for TF binding motif hits in the target promoter', component: MotifQueryPanel, category: 'evidence' },
  { id: 'literature-grounding', title: 'Literature Grounding', desc: 'Map gene names from papers to atlas IDs', component: LiteratureGroundingPanel, category: 'data' },
  { id: 'transition-drivers', title: 'Transition Drivers', desc: 'Which TFs’ regulons overlap your DEG list?', component: TransitionDriversPanel, category: 'phenotype', accepts: 'sharedGeneSet' },
  { id: 'diffreg', title: 'Differential Regulation', desc: 'Compare TF activity between tissue conditions', component: DiffRegulationPanel, category: 'phenotype' },
  { id: 'modules', title: 'Module Detection', desc: 'Find co-regulated gene communities in your list', component: ModulePanel, category: 'phenotype' },
  { id: 'patterns', title: 'Network Patterns', desc: 'Feed-forward loops, autoregulation, bi-fan motifs', component: NetworkPatternsPanel, category: 'phenotype' },
  { id: 'centrality', title: 'Centrality Metrics', desc: 'Rank genes by network centrality (hub TFs)', component: CentralityPanel, category: 'phenotype' },
  { id: 'multiome-audit', title: 'Multi-layer Evidence', desc: 'Check network + motif + chromatin + expression + perturbation support', component: MultiomeAuditPanel, category: 'evidence' },
  { id: 'validation-dashboard', title: 'Validation Dashboard', desc: 'Gold-standard recall, specificity, atlas coverage', component: ValidationDashboard, category: 'evidence' },
  { id: 'inferred', title: 'Inferred Edges', desc: 'GRNBoost2/GENIE3 predicted edges (to estimate off-target risk)', component: InferredEdgesPanel, category: 'evidence', accepts: 'sharedGeneSet', shares: true },
  { id: 'edit-consequence', title: 'Edit Consequence', desc: 'What regulatory edges break if you edit a promoter or coding region?', component: EditConsequencePanel, category: 'intervention' },
  { id: 'crispr-vs-dsrna', title: 'CRISPR vs dsRNA', desc: 'Side-by-side comparison of RNAi and CRISPR for each target', component: CrisprVsDsrnaPanel, category: 'intervention' },
  { id: 'intervention-ranker', title: 'Intervention Ranker', desc: 'Rank strategies by feasibility, cost, and network impact', component: InterventionRankerPanel, category: 'intervention' },
  { id: 'wf-infer-enrich', title: 'Inferred → Enrichment', desc: 'Find predicted TF targets, then GO enrichment', component: InferredEnrichmentWorkflow, category: 'workflow' },
  { id: 'wf-module-motif', title: 'Module → Motif', desc: 'Gene communities, then TF motif enrichment', component: ModuleMotifWorkflow, category: 'workflow' },
  { id: 'wf-regulon-diff', title: 'Regulon → Differential', desc: 'TF regulon, then tissue activity comparison', component: RegulonDiffWorkflow, category: 'workflow' },
  { id: 'wf-infer-validate', title: 'Inferred → Validation', desc: 'Cross-reference predicted edges against curated evidence', component: InferredValidationWorkflow, category: 'workflow' },
  { id: 'omics-import', title: 'Omics Import', desc: 'Import expression matrices, DEG lists, cluster definitions', component: OmicsImportPanel, category: 'data' },
  { id: 'export', title: 'Edge Export', desc: 'Export edges with genomic context (JSON/TSV)', component: ExportPanel, category: 'data', accepts: 'sharedGeneSet' },
];

export default function ToolboxView({ gene, networkData, filters, onNodeAction, onDepthChange }) {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState(null);
  const [openTool, setOpenTool] = useState(null);
  const [sharedGeneSet, setSharedGeneSet] = useState(null);
  const currentSpecies = gene?.species || filters?.species?.[0] || '';

  const shareToPanel = useCallback((targetPanel, genes, label) => {
    setSharedGeneSet({ genes, label, target: targetPanel });
    setOpenTool(targetPanel);
  }, []);

  const filtered = useMemo(() => {
    let list = TOOLS;
    if (activeCategory) list = list.filter(t => t.category === activeCategory);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(t =>
        t.title.toLowerCase().includes(q) ||
        t.desc.toLowerCase().includes(q) ||
        CATEGORIES[t.category]?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [search, activeCategory]);

  return (
    <div className="toolbox-view">
      <div className="toolbox-controls">
        <input
          className="toolbox-search"
          type="text"
          placeholder="Search tools…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="toolbox-filters">
          <button
            className={`toolbox-chip${!activeCategory ? ' active' : ''}`}
            onClick={() => setActiveCategory(null)}
          >All</button>
          {Object.entries(CATEGORIES).map(([key, label]) => (
            <button
              key={key}
              className={`toolbox-chip${activeCategory === key ? ' active' : ''}`}
              onClick={() => setActiveCategory(activeCategory === key ? null : key)}
            >{label}</button>
          ))}
        </div>
      </div>

      {sharedGeneSet && (
        <div className="shared-gene-banner">
          Shared: <strong>{sharedGeneSet.label}</strong> ({sharedGeneSet.genes.length} genes)
          <button onClick={() => setSharedGeneSet(null)}>Clear</button>
        </div>
      )}

      <div className="toolbox-grid">
        {filtered.map(tool => {
          const isOpen = openTool === tool.id;
          const Panel = tool.component;
          return (
            <div key={tool.id} className={`toolbox-card${isOpen ? ' open' : ''}`}>
              <div className="toolbox-card-header" onClick={() => setOpenTool(isOpen ? null : tool.id)}>
                <div>
                  <span className="toolbox-card-category">{CATEGORIES[tool.category]}</span>
                  <strong className="toolbox-card-title">{tool.title}</strong>
                  <span className="toolbox-card-desc">{tool.desc}</span>
                </div>
                <span className="chevron">{isOpen ? '▾' : '▸'}</span>
              </div>
              {isOpen && (
                <div className="toolbox-card-body">
                  <Panel
                    currentGene={gene}
                    currentSpecies={currentSpecies}
                    {...(tool.shares ? { onShareGenes: shareToPanel } : {})}
                    {...(tool.accepts && sharedGeneSet?.target === tool.id ? { sharedGeneSet } : {})}
                  />
                </div>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="toolbox-empty">No tools match your search.</div>
        )}
      </div>
    </div>
  );
}
