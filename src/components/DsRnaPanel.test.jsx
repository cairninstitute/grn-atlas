import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DsRnaPanel from './DsRnaPanel';

vi.mock('../services/apiService', () => ({
  geneAPI: { search: vi.fn(async () => ({ results: [{ id: 'GENE1', symbol: 'AN2', label: 'AN2' }] })) },
  analysisAPI: {
    dsrna: vi.fn(async () => ({
      available: true, mode: 'design', dsrna_length: 250, n_sirnas: 460, specificity: 1.0,
      off_target_gene_count: 0,
      on_target: { gene_id: 'GENE1', symbol: 'AN2', sites: 230, mean_tpm: 4.9, label_inferred: false },
      design: { start: 275, end: 525, sequence: 'ACGT'.repeat(60),
                transcript_length: 750, offtarget_profile: [0, 1, 0, 2] },
      off_targets: [],
      predicted_effect: { affected: 12, up: 1, down: 11, unknown: 0, top: [] },
    })),
    dsrnaScreen: vi.fn(),
  },
}));

describe('DsRnaPanel', () => {
  beforeEach(() => vi.clearAllMocks());

  it('does not render when closed', () => {
    const { container } = render(<DsRnaPanel open={false} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('designs a dsRNA and shows the specificity verdict + on-target', async () => {
    render(<DsRnaPanel open onClose={() => {}} initialTarget="AN2" initialSpecies="petunia" />);
    fireEvent.click(screen.getByText('Design a specific dsRNA'));
    expect(await screen.findByText(/Fully specific/)).toBeInTheDocument();
    expect(screen.getByText(/230 sites/)).toBeInTheDocument();
    expect(screen.getByText(/12 genes affected/)).toBeInTheDocument();
  });
});
