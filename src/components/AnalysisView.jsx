import React, { useState, useCallback } from 'react';
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
import TissueWeightsPanel from './TissueWeightsPanel';
import ValidationDashboard from './ValidationDashboard';
import OmicsImportPanel from './OmicsImportPanel';
import CelltypePanel from './CelltypePanel';
import ChromatinPanel from './ChromatinPanel';
import ExportPanel from './ExportPanel';
import InferredEnrichmentWorkflow from './InferredEnrichmentWorkflow';
import ModuleMotifWorkflow from './ModuleMotifWorkflow';
import RegulonDiffWorkflow from './RegulonDiffWorkflow';
import InferredValidationWorkflow from './InferredValidationWorkflow';
import NetworkVisualization from './NetworkVisualization';
import CisSupportAuditPanel from './CisSupportAuditPanel';
import EnhancerNetworkPanel from './EnhancerNetworkPanel';
import MultiomeAuditPanel from './MultiomeAuditPanel';
import CrisprVsDsrnaPanel from './CrisprVsDsrnaPanel';
import EditConsequencePanel from './EditConsequencePanel';
import InterventionRankerPanel from './InterventionRankerPanel';
import LiteratureGroundingPanel from './LiteratureGroundingPanel';
import TransitionDriversPanel from './TransitionDriversPanel';
import '../styles/AnalysisView.css';

const TABS = [
  {
    id: 'regulators',
    label: 'Who regulates my gene?',
    icon: '↑',
    desc: 'Find upstream TFs, enriched regulons, and binding evidence for your gene of interest',
    sections: [
      { label: '1. Find candidate regulators', panels: [
        { id: 'upstream', title: 'Upstream Regulators', desc: 'Which TFs have your gene in their regulon?', component: UpstreamPanel, accepts: 'sharedGeneSet' },
        { id: 'regulon-enrichment', title: 'Regulon Enrichment', desc: 'Test which TF regulons are enriched in a gene list', component: RegulonEnrichmentPanel, accepts: 'sharedGeneSet' },
        { id: 'tf-activity', title: 'TF / Pathway Activity', desc: 'Infer TF or pathway activity from expression data', component: TFActivityPanel, accepts: 'sharedGeneSet' },
      ]},
      { label: '2. Examine the regulon', panels: [
        { id: 'regulon', title: 'Regulon Extraction', desc: 'See the full downstream target list of a candidate TF', component: RegulonPanel, accepts: 'sharedGeneSet', shares: true },
        { id: 'compare', title: 'Regulon Comparison', desc: 'Compare regulons of two TFs side by side', component: RegulonComparePanel, shares: true },
      ]},
      { label: '3. Validate the evidence', panels: [
        { id: 'cis-support-audit', title: 'Cis-Support Audit', desc: 'Is the TF→target edge backed by motif, chromatin, and prior data?', component: CisSupportAuditPanel },
        { id: 'motif', title: 'Motif Query', desc: 'Check for TF binding motif hits in the target promoter', component: MotifQueryPanel },
        { id: 'literature-grounding', title: 'Literature Grounding', desc: 'Map gene names from papers to atlas IDs', component: LiteratureGroundingPanel },
      ]},
    ],
  },
  {
    id: 'phenotype',
    label: "What's driving this phenotype?",
    icon: '⚙',
    desc: 'Starting from DEGs or a gene list, find the TF drivers, co-regulated modules, and network structure behind a phenotype',
    sections: [
      { label: '1. Identify driver TFs', panels: [
        { id: 'transition-drivers', title: 'Transition Drivers', desc: 'Which TFs’ regulons overlap your DEG list?', component: TransitionDriversPanel, accepts: 'sharedGeneSet' },
        { id: 'celltype', title: 'Cell-type Regulators', desc: 'TFs active in specific cell types or clusters', component: CelltypePanel, accepts: 'sharedGeneSet' },
        { id: 'diffreg', title: 'Differential Regulation', desc: 'Compare TF activity between tissue conditions', component: DiffRegulationPanel },
      ]},
      { label: '2. Explore network structure', panels: [
        { id: 'modules', title: 'Module Detection', desc: 'Find co-regulated gene communities in your list', component: ModulePanel },
        { id: 'patterns', title: 'Network Patterns', desc: 'Feed-forward loops, autoregulation, bi-fan motifs', component: NetworkPatternsPanel },
        { id: 'centrality', title: 'Centrality Metrics', desc: 'Rank genes by network centrality (hub TFs)', component: CentralityPanel },
      ]},
      { label: '3. Multi-step workflows', panels: [
        { id: 'wf-infer-enrich', title: 'Inferred → Enrichment', desc: 'Find predicted TF targets, then GO enrichment', component: InferredEnrichmentWorkflow },
        { id: 'wf-module-motif', title: 'Module → Motif', desc: 'Gene communities, then TF motif enrichment', component: ModuleMotifWorkflow },
        { id: 'wf-regulon-diff', title: 'Regulon → Differential', desc: 'TF regulon, then tissue activity comparison', component: RegulonDiffWorkflow },
      ]},
    ],
  },
  {
    id: 'intervene',
    label: 'How should I intervene?',
    icon: '✂',
    desc: 'Compare CRISPR, RNAi, and promoter editing strategies for your target genes',
    sections: [
      { label: '1. Compare strategies', panels: [
        { id: 'crispr-vs-dsrna', title: 'CRISPR vs dsRNA', desc: 'Side-by-side comparison of RNAi and CRISPR for each target', component: CrisprVsDsrnaPanel },
        { id: 'intervention-ranker', title: 'Intervention Ranker', desc: 'Rank strategies by feasibility, cost, and network impact', component: InterventionRankerPanel },
      ]},
      { label: '2. Predict consequences', panels: [
        { id: 'edit-consequence', title: 'Edit Consequence', desc: 'What regulatory edges break if you edit a promoter or coding region?', component: EditConsequencePanel },
        { id: 'tissue-weights', title: 'Tissue Coexpression', desc: 'Which tissues will be most affected?', component: TissueWeightsPanel },
      ]},
      { label: '3. Examine inferred edges', panels: [
        { id: 'inferred', title: 'Inferred Edges', desc: 'GRNBoost2/GENIE3 predicted edges (to estimate off-target risk)', component: InferredEdgesPanel, accepts: 'sharedGeneSet', shares: true },
        { id: 'wf-infer-validate', title: 'Inferred → Validation', desc: 'Cross-reference predicted edges against curated evidence', component: InferredValidationWorkflow },
      ]},
    ],
  },
  {
    id: 'evidence',
    label: 'Is this edge real?',
    icon: '✔',
    desc: 'Triangulate support for a regulatory edge across chromatin, motif, expression, and perturbation layers',
    sections: [
      { label: '1. Multi-layer audit', panels: [
        { id: 'multiome-audit', title: 'Multi-layer Evidence', desc: 'Check network + motif + chromatin + expression + perturbation support', component: MultiomeAuditPanel },
        { id: 'cis-support-audit-2', title: 'Cis-Support Audit', desc: 'Motif, chromatin, and prior-literature support for an edge', component: CisSupportAuditPanel },
      ]},
      { label: '2. Chromatin & enhancers', panels: [
        { id: 'enhancer-network', title: 'Enhancer Network', desc: 'Gene’s enhancer-linked regulatory neighborhood', component: EnhancerNetworkPanel },
        { id: 'chromatin', title: 'Chromatin Peaks', desc: 'View chromatin accessibility peaks and enhancer-gene links', component: ChromatinPanel },
      ]},
      { label: '3. Benchmarks & validation', panels: [
        { id: 'validation-dashboard', title: 'Validation Dashboard', desc: 'Gold-standard recall, specificity, atlas coverage', component: ValidationDashboard },
      ]},
    ],
  },
  {
    id: 'import',
    label: 'Import & Export',
    icon: '⇅',
    desc: 'Bring in datasets, map gene names, and export results',
    sections: [
      { label: 'Data import', panels: [
        { id: 'omics-import', title: 'Omics Import', desc: 'Import expression matrices, DEG lists, cluster definitions', component: OmicsImportPanel },
        { id: 'literature-grounding-2', title: 'Literature Grounding', desc: 'Map gene names from papers to atlas-grounded IDs', component: LiteratureGroundingPanel },
      ]},
      { label: 'Export', panels: [
        { id: 'export', title: 'Edge Export', desc: 'Export edges with genomic context (JSON/TSV)', component: ExportPanel, accepts: 'sharedGeneSet' },
      ]},
    ],
  },
];

export default function AnalysisView({ gene, networkData, filters, onNodeAction, onDepthChange }) {
  const [activeTab, setActiveTab] = useState('regulators');
  const [open, setOpen] = useState({ upstream: true });
  const [sharedGeneSet, setSharedGeneSet] = useState(null);
  const currentSpecies = gene?.species || filters?.species?.[0] || '';

  const toggle = (id) => setOpen(prev => ({ ...prev, [id]: !prev[id] }));

  const shareToPanel = useCallback((targetPanel, genes, label) => {
    setSharedGeneSet({ genes, label, target: targetPanel });
    setOpen(prev => ({ ...prev, [targetPanel]: true }));
  }, []);

  const currentTab = TABS.find(t => t.id === activeTab) || TABS[0];

  return (
    <div className="analysis-view">
      {gene && networkData ? (
        <div className="analysis-card open">
          <div className="analysis-card-header">
            <div>
              <strong>Current neighborhood</strong>
              <span className="analysis-card-desc"> &mdash; network context for {gene.symbol || gene.id}</span>
            </div>
          </div>
          <div className="analysis-card-body">
            <div className="analysis-network-frame">
              <NetworkVisualization
                gene={gene}
                data={networkData}
                filters={filters}
                onNodeAction={onNodeAction}
                onDepthChange={onDepthChange}
              />
            </div>
          </div>
        </div>
      ) : null}

      <div className="analysis-tab-bar">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`analysis-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
            title={tab.desc}
          >
            <span className="analysis-tab-icon">{tab.icon}</span>
            <span className="analysis-tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="analysis-tab-desc">{currentTab.desc}</div>

      {sharedGeneSet && (
        <div className="shared-gene-banner">
          Shared: <strong>{sharedGeneSet.label}</strong> ({sharedGeneSet.genes.length} genes)
          <button onClick={() => setSharedGeneSet(null)}>Clear</button>
        </div>
      )}

      {currentTab.sections.map(({ label, panels }) => (
        <div key={label} className="analysis-section">
          <h3 className="analysis-section-title">{label}</h3>
          {panels.map(({ id, title, desc, component: Panel, accepts, shares }) => (
            <div key={id} className={`analysis-card ${open[id] ? 'open' : ''}`}>
              <div className="analysis-card-header" onClick={() => toggle(id)}>
                <div>
                  <strong>{title}</strong>
                  {!open[id] && <span className="analysis-card-desc"> &mdash; {desc}</span>}
                </div>
                <span className="chevron">{open[id] ? '▾' : '▸'}</span>
              </div>
              {open[id] && (
                <div className="analysis-card-body">
                  <Panel
                    currentGene={gene}
                    currentSpecies={currentSpecies}
                    {...(shares ? { onShareGenes: shareToPanel } : {})}
                    {...(accepts && sharedGeneSet?.target === id ? { sharedGeneSet } : {})}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
