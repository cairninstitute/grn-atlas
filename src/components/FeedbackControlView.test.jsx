import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import FeedbackControlView from './FeedbackControlView';
import { analysisAPI } from '../services/apiService';


vi.mock('../services/apiService', () => ({
  analysisAPI: { feedbackControl: vi.fn(), feedbackBackbone: vi.fn(), feedbackCycles: vi.fn() },
}));

vi.mock('./SubgraphGraph', () => ({
  default: ({ nodes, edges }) => <div data-testid="circuit-graph">{nodes.length} nodes / {edges.length} edges</div>,
}));

const payload = {
  run_id: 'run-1',
  species: 'arabidopsis',
  graph: { nodes: 12, edges: 19 },
  summary: {
    feedback_cores: 1, feedback_genes: 3, circuits_returned: 1, controller_candidates: 1,
    biological_systems: 1, feedback_edges: 3, core_groups: 1, macro_circuits: 1,
  },
  truncation: { cores: false, circuits: true, search: true },
  storage: { status: 'cached', backend: 'versioned_sidecar' },
  evidence_boundary: 'Topology identifies candidate control structures, not demonstrated dynamics.',
  systems: [{
    system_id: 'system-1', rank: 1, name: 'Circadian rhythm', score: 0.88,
    confidence_label: 'high', discovery_mode: 'annotation_supported',
    architecture_label: 'Incomplete oscillator scaffold', completeness: 'partial_architecture',
    gene_count: 3, edge_count: 3, feedback_gene_count: 2,
    classification_reasons: ['rhythm-related biological annotation', 'signed negative feedback present'],
    annotation: { enrichment: { fold: 12.4 } },
    context_support: { cis_supported_edges: 1, perturbation_supported_edges: 0, coexpressed_edges: 2,
      conservation: { conserved_signed_edges: 1, tested_edges: 2, species: ['human'] },
      top_tissues: [{ tissue: 'seedling', supported_edges: 2 }] },
    genes: [{ id: 'A', symbol: 'CCA1' }, { id: 'B', symbol: 'PRR7' }, { id: 'C', symbol: 'LUX' }],
    edges: [
      { source: 'A', target: 'B', regulation_type: 'repression' },
      { source: 'B', target: 'C', regulation_type: 'repression' },
      { source: 'C', target: 'A', regulation_type: 'repression' },
    ],
    evidence_boundary: 'Architecture is a mechanistic hypothesis, not proof of dynamics.',
  }],
  core_groups: [{
    group_id: 'group-1', rank: 1, core_count: 2, relationship_count: 1,
    gene_count: 5, bridge_gene_count: 1, score: 0.81,
    relationship_ids: ['relationship-1'],
    cores: [
      { core_id: 'core-1', rank: 1, score: 0.91, node_count: 3, edge_count: 3, top_genes: [] },
      { core_id: 'core-2', rank: 2, score: 0.8, node_count: 2, edge_count: 2, top_genes: [] },
    ],
  }],
  core_relationships: [{
    relationship_id: 'relationship-1', source_core_id: 'core-1', target_core_id: 'core-2',
    source_core_rank: 1, target_core_rank: 2, relationship_type: 'bridged_regulatory_path',
    hop_count: 2, score: 0.81, net_sign: 'repression',
    path_genes: [{ symbol: 'CCA1' }, { symbol: 'BRIDGE' }, { symbol: 'TARGET' }],
    bridge_genes: [{ symbol: 'BRIDGE' }],
  }],
  macro_circuits: [{
    macro_circuit_id: 'macro-1', rank: 1, parent_core_count: 2,
    merged_parent_core_count: 2,
    gene_loop_length: 4, merged_gene_count: 6, added_feedback_gene_count: 1,
    polarity: 'negative', architecture: 'negative_macro_feedback',
    augmented_layer: 'supported', score: 0.74, confidence_label: 'structural_candidate',
    behavior_hypothesis: 'homeostasis, adaptation, or oscillation candidate',
    parent_cores: [
      { core_id: 'core-1', rank: 1, node_count: 3 },
      { core_id: 'core-2', rank: 2, node_count: 2 },
    ],
    genes: [
      { id: 'A', symbol: 'CCA1' }, { id: 'B', symbol: 'PRR7' },
      { id: 'C', symbol: 'LUX' }, { id: 'D', symbol: 'BRIDGE' },
    ],
    edges: [
      { source: 'A', target: 'B', regulation_type: 'activation' },
      { source: 'B', target: 'C', regulation_type: 'repression' },
      { source: 'C', target: 'D', regulation_type: 'activation' },
      { source: 'D', target: 'A', regulation_type: 'activation' },
    ],
    introduced_edges: [{
      source: 'D', target: 'A', sign: 'activation', evidence_tier: 'supported',
      sign_evidence: 'candidate', confidence: 0.76,
    }],
    boundary: 'This is a structural witness, not proof of shared biological context.',
  }],
  cores: [{
    core_id: 'core-1', rank: 1, score: 0.91, node_count: 3, edge_count: 3,
    mean_edge_confidence: 0.9,
    backbone: { cycle_capable_nodes: 3, cycle_capable_edges: 3, complete: true },
    cycle_catalog: { exact: true, cataloged_cycles: 1, mode: 'exact' },
    cycle_cover: { complete: true, coverage: 1, circuits: [] },
    circuit_search: { search_states: 1234, truncated: true },
    controller_analysis: {
      exact: true,
      controllers: [{ id: 'A', symbol: 'CCA1' }],
    },
    circuits: [{
      circuit_id: 'circuit-1', family: 'repressilator', polarity: 'negative',
      confidence_label: 'high', score: 0.93,
      behavior_hypothesis: 'oscillation candidate if delays and kinetics support it',
      genes: [
        { id: 'A', symbol: 'CCA1' }, { id: 'B', symbol: 'PRR7' }, { id: 'C', symbol: 'LUX' },
      ],
      edges: [
        { source: 'A', target: 'B', regulation_type: 'repression' },
        { source: 'B', target: 'C', regulation_type: 'repression' },
        { source: 'C', target: 'A', regulation_type: 'repression' },
      ],
    }],
  }],
};

describe('FeedbackControlView', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('renders bounded feedback analysis and its evidence boundary', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      json: async () => ({ species_list: ['arabidopsis', 'human'] }),
    })));
    analysisAPI.feedbackControl.mockResolvedValue(payload);
    analysisAPI.feedbackBackbone.mockResolvedValue({
      run_id: 'run-1', core_id: 'core-1', node_count: 3, edge_count: 3, complete: true,
      nodes: payload.systems[0].genes, edges: payload.systems[0].edges,
    });
    render(<FeedbackControlView initialSpecies="arabidopsis" />);

    await waitFor(() => expect(screen.getByText('Biological control systems')).toBeInTheDocument());
    expect(screen.getAllByText('Circadian rhythm')).toHaveLength(2);
    expect(screen.getByText('PARTIAL ARCHITECTURE')).toBeInTheDocument();
    expect(screen.getByText('Connected groups of feedback cores')).toBeInTheDocument();
    expect(screen.getByText('Analyze supported evidence')).toBeInTheDocument();
    expect(screen.getByText('Larger feedback loops created by augmented evidence')).toBeInTheDocument();
    expect(screen.getByText('Edges that close the larger loop')).toBeInTheDocument();
    expect(screen.getByText('Complete cycle-capable backbone')).toBeInTheDocument();
    expect(screen.getByText(/bounded representative analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/not demonstrated dynamics/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByTestId('circuit-graph')).toHaveLength(4));
    expect(analysisAPI.feedbackBackbone).toHaveBeenCalledWith('run-1', 'core-1');
    expect(analysisAPI.feedbackControl).toHaveBeenCalledWith('arabidopsis', {
      minConfidence: 0.5, maxLoopLength: 6, includeCandidates: false,
      includeExploratory: false, includeMultilayer: false, probabilisticSamples: 0,
    });
  });
});
