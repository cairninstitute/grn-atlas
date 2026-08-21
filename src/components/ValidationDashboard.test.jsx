import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ValidationDashboard from './ValidationDashboard';

const basePayload = {
  atlas_summary: {
    genes: 123,
    interactions: 456,
    species: ['human', 'petunia'],
    tissue_weight_rows: 12,
  },
  benchmarks: [
    {
      species: 'human',
      ground_truth: 'DoRothEA',
      n_predictions: 1000,
      auroc: 0.95,
      auprc: 0.91,
      early_precision_100: 0.74,
    },
  ],
  species_validation: {
    human: {
      go_coverage: { total_edges: 1000, genes_with_go: 800 },
      regulon_coherence: { sigma: 1.4 },
      multi_evidence: { z_score: 2.3 },
      motif_enrichment: { mean_enrichment: 3.2 },
    },
  },
  validation_report_md: '# Validation report',
  artifact_health: {
    status: 'ok',
    warnings: [],
    summary: {
      suite_status: 'pass',
      benchmark_corpus_version: '2026-08-21',
      git_sha: 'abc1234',
      run_at_utc: '2026-08-21T12:00:00Z',
    },
    artifact_manifest: { artifacts: ['latest_summary.json'] },
    schema_report: { status: 'pass' },
  },
};

describe('ValidationDashboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('renders complete validation state', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ json: async () => basePayload })));
    render(<ValidationDashboard />);
    await waitFor(() => expect(screen.getByText(/Living validation dashboard/i)).toBeInTheDocument());
    expect(screen.getByText('Benchmark artifact health')).toBeInTheDocument();
    expect(screen.getByText('Healthy')).toBeInTheDocument();
    expect(screen.getByText('Validation suite')).toBeInTheDocument();
    expect(screen.getByText('pass')).toBeInTheDocument();
    expect(screen.getByText('Corpus version')).toBeInTheDocument();
  });

  it('renders degraded warnings when artifact health is not clean', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      json: async () => ({
        ...basePayload,
        artifact_health: {
          status: 'degraded',
          warnings: ['Missing validation_runs/schema_report.json'],
          summary: null,
          artifact_manifest: null,
          schema_report: null,
        },
      }),
    })));
    render(<ValidationDashboard />);
    await waitFor(() => expect(screen.getByText('Degraded')).toBeInTheDocument());
    expect(screen.getByText('Missing validation_runs/schema_report.json')).toBeInTheDocument();
  });
});
