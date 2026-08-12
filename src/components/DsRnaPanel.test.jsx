import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DsRnaPanel from './DsRnaPanel';

vi.mock('../services/apiService', () => ({
  geneAPI: { search: vi.fn(async () => ({ results: [{ id: 'GENE1', symbol: 'AN2', label: 'AN2' }] })) },
  analysisAPI: {
    dsrna: vi.fn(async (options) => ({
      available: true, mode: 'design', dsrna_length: 250, n_sirnas: 460, specificity: 1.0,
      off_target_gene_count: options?.targetGeneId === 'GENE2' ? 1 : 0,
      on_target: {
        gene_id: options?.targetGeneId || 'GENE1',
        symbol: options?.targetGeneId === 'GENE2' ? 'JAF13' : 'AN2',
        sites: 230,
        mean_tpm: options?.targetGeneId === 'GENE2' ? 25.3 : 4.9,
        label_inferred: false,
      },
      design: { start: 275, end: 525, sequence: 'ACGT'.repeat(60),
                transcript_length: 750, offtarget_profile: [0, 1, 0, 2] },
      off_targets: [],
      predicted_effect: { affected: options?.targetGeneId === 'GENE2' ? 33 : 12, up: 1, down: 11, unknown: 0, top: [] },
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

  it('accepts an object initialTarget without crashing', () => {
    render(
      <DsRnaPanel
        open
        onClose={() => {}}
        initialTarget={{ id: 'GENE1', symbol: 'AN2', label: 'AN2', species: 'petunia' }}
        initialSpecies="petunia"
      />,
    );
    expect(screen.getByDisplayValue('AN2')).toBeInTheDocument();
  });

  it('prefills the screen set from initialSet', () => {
    render(
      <DsRnaPanel
        open
        onClose={() => {}}
        initialTarget="AN2"
        initialSpecies="petunia"
        initialSet={['AN2', 'JAF13', 'DFR']}
      />,
    );
    expect(screen.getByDisplayValue('AN2, JAF13, DFR')).toBeInTheDocument();
  });

  it('supports side-by-side comparison for two targets', async () => {
    const { geneAPI } = await import('../services/apiService');
    geneAPI.search
      .mockResolvedValueOnce({ results: [{ id: 'GENE1', symbol: 'AN2', label: 'AN2' }] })
      .mockResolvedValueOnce({ results: [{ id: 'GENE2', symbol: 'JAF13', label: 'JAF13' }] });

    render(
      <DsRnaPanel
        open
        onClose={() => {}}
        initialTarget="AN2"
        initialCompareTarget="JAF13"
        initialSpecies="petunia"
      />,
    );

    fireEvent.click(screen.getByText('Compare top 2'));
    expect(await screen.findByText('Side-by-side comparison')).toBeInTheDocument();
    expect(screen.getByText(/Recommended first target:/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'AN2' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: 'JAF13' })).toBeInTheDocument();
  });
});
