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
  { id: 'discover', label: 'Discover', icon: '🔍',
    desc: 'Find regulators, regulons, and enriched TFs',
    sections: [
      { label: 'Regulon & Upstream', panels: [
        { id: 'regulon', title: 'Regulon Extraction', desc: 'Extract downstream targets of a TF', component: RegulonPanel, accepts: 'sharedGeneSet', shares: true },
        { id: 'compare', title: 'Regulon Comparison', desc: 'Compare regulons of two TFs', component: RegulonComparePanel, shares: true },
        { id: 'upstream', title: 'Upstream Regulators', desc: 'Predict which TFs regulate a gene set', component: UpstreamPanel, accepts: 'sharedGeneSet' },
        { id: 'regulon-enrichment', title: 'Regulon Enrichment', desc: 'Test which TF regulons are enriched in a gene list', component: RegulonEnrichmentPanel, accepts: 'sharedGeneSet' },
        { id: 'tf-activity', title: 'TF / Pathway Activity', desc: 'Infer TF or pathway activity from gene statistics', component: TFActivityPanel, accepts: 'sharedGeneSet' },
      ]},
      { label: 'Network Structure', panels: [
        { id: 'patterns', title: 'Network Patterns', desc: 'Feed-forward loops, autoregulation, bi-fans', component: NetworkPatternsPanel },
        { id: 'centrality', title: 'Centrality Metrics', desc: 'Rank genes by network centrality', component: CentralityPanel },
        { id: 'modules', title: 'Module Detection', desc: 'Co-regulated gene communities', component: ModulePanel },
      ]},
      { label: 'Cell State & Transitions', panels: [
        { id: 'celltype', title: 'Cell-type Regulation', desc: 'TF regulators active in specific cell types/clusters', component: CelltypePanel, accepts: 'sharedGeneSet' },
        { id: 'transition-drivers', title: 'Transition Drivers', desc: 'TF drivers of cell-state transitions', component: TransitionDriversPanel, accepts: 'sharedGeneSet' },
        { id: 'diffreg', title: 'Differential Regulation', desc: 'Compare TF activity between tissue conditions', component: DiffRegulationPanel },
      ]},
    ],
  },
  { id: 'evidence', label: 'Evidence', icon: '🔬',
    desc: 'Audit regulatory edge support across data layers',
    sections: [
      { label: 'Edge Auditing', panels: [
        { id: 'cis-support-audit', title: 'Cis-Support Audit', desc: 'Is a TF→target edge supported by motif, chromatin, and prior evidence?', component: CisSupportAuditPanel },
        { id: 'multiome-audit', title: 'Multi-layer Evidence', desc: 'Triangulate support across network, motif, chromatin, expression, perturbation', component: MultiomeAuditPanel },
      ]},
      { label: 'Chromatin & Enhancers', panels: [
        { id: 'enhancer-network', title: 'Enhancer Network', desc: "Gene's enhancer-linked regulatory neighborhood", component: EnhancerNetworkPanel },
        { id: 'chromatin', title: 'Chromatin Peaks', desc: 'View and import chromatin peaks, enhancer-gene links', component: ChromatinPanel },
        { id: 'motif', title: 'Motif Query', desc: 'TF binding motif hits in gene promoters', component: MotifQueryPanel },
      ]},
      { label: 'Expression & Inference', panels: [
        { id: 'inferred', title: 'Inferred Edges', desc: 'GRNBoost2/GENIE3 predicted regulatory edges', component: InferredEdgesPanel, accepts: 'sharedGeneSet', shares: true },
        { id: 'tissue-weights', title: 'Tissue Coexpression', desc: 'Tissue-specific edge coexpression weights', component: TissueWeightsPanel },
      ]},
      { label: 'Validation', panels: [
        { id: 'validation-dashboard', title: 'Validation Dashboard', desc: 'Benchmarks, per-species quality, atlas coverage', component: ValidationDashboard },
      ]},
    ],
  },
  { id: 'intervene', label: 'Intervene', icon: '🎯',
    desc: 'Design and compare intervention strategies',
    sections: [
      { label: 'Strategy Comparison', panels: [
        { id: 'crispr-vs-dsrna', title: 'CRISPR vs dsRNA', desc: 'Compare RNAi and CRISPR for the same gene targets', component: CrisprVsDsrnaPanel },
        { id: 'intervention-ranker', title: 'Intervention Ranker', desc: 'Rank dsRNA, CRISPR, and promoter editing by feasibility and cost', component: InterventionRankerPanel },
      ]},
      { label: 'Consequence Prediction', panels: [
        { id: 'edit-consequence', title: 'Edit Consequence', desc: 'Predict regulatory effects of promoter or coding edits', component: EditConsequencePanel },
      ]},
      { label: 'Multi-step Workflows', panels: [
        { id: 'wf-infer-enrich', title: 'Inferred → Enrichment', desc: 'Find predicted TF targets, then GO enrichment', component: InferredEnrichmentWorkflow },
        { id: 'wf-module-motif', title: 'Module → Motif', desc: 'Gene communities, then TF motif enrichment', component: ModuleMotifWorkflow },
        { id: 'wf-regulon-diff', title: 'Regulon → Differential', desc: 'TF regulon, then tissue activity comparison', component: RegulonDiffWorkflow },
        { id: 'wf-infer-validate', title: 'Inferred → Validation', desc: 'Predicted edges, then curated evidence cross-ref', component: InferredValidationWorkflow },
      ]},
    ],
  },
  { id: 'import', label: 'Import', icon: '📥',
    desc: 'Bring in datasets, gene lists, and literature terms',
    sections: [
      { label: 'Data Import', panels: [
        { id: 'omics-import', title: 'Omics Import', desc: 'Import expression matrices, DEG lists, cluster definitions', component: OmicsImportPanel },
      ]},
      { label: 'Literature & Naming', panels: [
        { id: 'literature-grounding', title: 'Literature Grounding', desc: 'Map gene names from papers to atlas-grounded IDs', component: LiteratureGroundingPanel },
      ]},
      { label: 'Export', panels: [
        { id: 'export', title: 'Edge Export', desc: 'Export edges with genomic context (JSON/TSV)', component: ExportPanel, accepts: 'sharedGeneSet' },
      ]},
    ],
  },
];

export default function AnalysisView({ gene, networkData, filters, onNodeAction, onDepthChange }) {
  const [activeTab, setActiveTab] = useState('discover');
  const [open, setOpen] = useState({ regulon: true });
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
              <span className="analysis-card-desc"> — network context for {gene.symbol || gene.id}</span>
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
                  {!open[id] && <span className="analysis-card-desc"> — {desc}</span>}
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
