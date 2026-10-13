import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import FeedbackControlView from './FeedbackControlView';
import { analysisAPI } from '../services/apiService';


vi.mock('../services/apiService', () => ({
  analysisAPI: { feedbackControl: vi.fn() },
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
    biological_systems: 1,
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
  cores: [{
    core_id: 'core-1', rank: 1, score: 0.91, node_count: 3, edge_count: 3,
    mean_edge_confidence: 0.9,
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
    render(<FeedbackControlView initialSpecies="arabidopsis" />);

    await waitFor(() => expect(screen.getByText('Biological control systems')).toBeInTheDocument());
    expect(screen.getAllByText('Circadian rhythm')).toHaveLength(2);
    expect(screen.getByText('PARTIAL ARCHITECTURE')).toBeInTheDocument();
    expect(screen.getAllByText('Repressilator')).toHaveLength(2);
    expect(screen.getByText('CCA1')).toBeInTheDocument();
    expect(screen.getByText(/bounded representative analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/not demonstrated dynamics/i)).toBeInTheDocument();
    expect(screen.getAllByTestId('circuit-graph')).toHaveLength(2);
    expect(analysisAPI.feedbackControl).toHaveBeenCalledWith('arabidopsis', {
      minConfidence: 0.5, maxLoopLength: 6,
    });
  });
});
