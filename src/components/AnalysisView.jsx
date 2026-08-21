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
import '../styles/AnalysisView.css';

const SECTIONS = [
  { label: 'Data Import', panels: [
    { id: 'omics-import', title: 'Omics Import', desc: 'Import gene expression matrices, DEG lists, and cluster definitions', component: OmicsImportPanel },
  ]},
  { label: 'Regulon & Upstream', panels: [
    { id: 'regulon', title: 'Regulon Extraction', desc: 'Extract the full regulon (downstream targets) of a transcription factor', component: RegulonPanel, accepts: 'sharedGeneSet', shares: true },
    { id: 'compare', title: 'Regulon Comparison', desc: 'Compare regulons of two TFs — overlap, Jaccard, significance', component: RegulonComparePanel, shares: true },
    { id: 'upstream', title: 'Upstream Regulators', desc: 'Given a gene set, predict which TFs regulate them', component: UpstreamPanel, accepts: 'sharedGeneSet' },
    { id: 'regulon-enrichment', title: 'Regulon Enrichment', desc: 'Test which TF regulons are enriched in a gene list (decoupleR-style)', component: RegulonEnrichmentPanel, accepts: 'sharedGeneSet' },
    { id: 'tf-activity', title: 'TF / Pathway Activity', desc: 'Infer TF or pathway activity from gene-level statistics (ULM/weighted mean)', component: TFActivityPanel, accepts: 'sharedGeneSet' },
  ]},
  { label: 'Network Structure', panels: [
    { id: 'patterns', title: 'Network Patterns', desc: 'Detect motifs: autoregulation, feed-forward loops, bi-fans', component: NetworkPatternsPanel },
    { id: 'centrality', title: 'Centrality Metrics', desc: 'Rank genes by network centrality (degree, betweenness, closeness, eigenvector)', component: CentralityPanel },
    { id: 'modules', title: 'Module Detection', desc: 'Detect co-regulated gene communities (louvain, leiden, infomap)', component: ModulePanel },
    { id: 'motif', title: 'Motif Query', desc: 'Query TF binding motif hits in gene promoters (JASPAR 2024)', component: MotifQueryPanel },
  ]},
  { label: 'Cell-type & Chromatin', panels: [
    { id: 'celltype', title: 'Cell-type Regulation', desc: 'Find TF regulators active in specific cell types/clusters from imported data', component: CelltypePanel, accepts: 'sharedGeneSet' },
    { id: 'chromatin', title: 'Chromatin / Enhancer Support', desc: 'View and import chromatin peaks, enhancer-gene links, motif hits', component: ChromatinPanel },
  ]},
  { label: 'Inference & Comparison', panels: [
    { id: 'inferred', title: 'Inferred Edges', desc: 'GRNBoost2/GENIE3 predicted regulatory edges from expression data', component: InferredEdgesPanel, accepts: 'sharedGeneSet', shares: true },
    { id: 'diffreg', title: 'Differential Regulation', desc: 'Compare TF regulatory activity between tissue conditions', component: DiffRegulationPanel },
    { id: 'tissue-weights', title: 'Tissue Coexpression', desc: 'View tissue-specific coexpression weights for regulatory edges', component: TissueWeightsPanel },
  ]},
  { label: 'Validation', panels: [
    { id: 'validation-dashboard', title: 'Validation Dashboard', desc: 'Benchmark results, per-species network quality, and atlas coverage', component: ValidationDashboard },
  ]},
  { label: 'Export', panels: [
    { id: 'export', title: 'Edge Export', desc: 'Export regulatory edges with genomic context (JSON/TSV)', component: ExportPanel, accepts: 'sharedGeneSet' },
  ]},
  { label: 'Workflows', panels: [
    { id: 'wf-infer-enrich', title: 'Inferred → Enrichment', desc: 'Find predicted TF targets, then run GO enrichment on the target set', component: InferredEnrichmentWorkflow },
    { id: 'wf-module-motif', title: 'Module → Motif', desc: 'Detect gene communities, then check TF motif enrichment in a module', component: ModuleMotifWorkflow },
    { id: 'wf-regulon-diff', title: 'Regulon → Differential', desc: 'Extract a TF regulon, then compare its activity across tissue conditions', component: RegulonDiffWorkflow },
    { id: 'wf-infer-validate', title: 'Inferred → Validation', desc: 'Find predicted edges, then cross-reference with curated evidence', component: InferredValidationWorkflow },
  ]},
];

export default function AnalysisView({ gene, networkData, filters, onNodeAction, onDepthChange }) {
  const [open, setOpen] = useState({ regulon: true });
  const [sharedGeneSet, setSharedGeneSet] = useState(null);
  const currentSpecies = gene?.species || filters?.species?.[0] || '';

  const toggle = (id) => setOpen(prev => ({ ...prev, [id]: !prev[id] }));

  const shareToPanel = useCallback((targetPanel, genes, label) => {
    setSharedGeneSet({ genes, label, target: targetPanel });
    setOpen(prev => ({ ...prev, [targetPanel]: true }));
  }, []);

  return (
    <div className="analysis-view">
      <h2 className="analysis-title">Network Analysis</h2>
      {gene && networkData ? (
        <div className="analysis-card open">
          <div className="analysis-card-header">
            <div>
              <strong>Current neighborhood</strong>
              <span className="analysis-card-desc"> — direct and expanded network context for the current focus gene</span>
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
      {sharedGeneSet && (
        <div className="shared-gene-banner">
          Shared: <strong>{sharedGeneSet.label}</strong> ({sharedGeneSet.genes.length} genes)
          <button onClick={() => setSharedGeneSet(null)}>Clear</button>
        </div>
      )}
      {SECTIONS.map(({ label, panels }) => (
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
