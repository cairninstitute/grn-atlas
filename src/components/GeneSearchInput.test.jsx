import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GeneSearchInput from './GeneSearchInput';

vi.mock('../services/apiService', () => ({
  geneAPI: {
    search: vi.fn(async () => ({
      results: [
        { id: 'Peaxi162Scf00118g00310', symbol: 'AN2', is_tf: true, name: 'anthocyanin 2',
          label: 'AN2', label_inferred: false },
        { id: 'Peaxi162Scf00238g00125', symbol: 'Peaxi162Scf00238g00125', name: 'DFR gene',
          label: 'DFR', label_inferred: true },
      ],
    })),
  },
}));

describe('GeneSearchInput', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows suggestions with friendly labels and an inferred marker', async () => {
    render(<GeneSearchInput species="petunia" value="" onChange={() => {}} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'AN' } });
    expect(await screen.findByText('AN2')).toBeInTheDocument();
    // inferred label DFR shows with the ° marker
    const dfr = await screen.findByText('DFR');
    expect(dfr).toBeInTheDocument();
    expect(screen.getByTitle('inferred from ortholog')).toBeInTheDocument();
  });

  it('calls onSelect with the picked gene and its friendly label via onChange', async () => {
    const onChange = vi.fn();
    const onSelect = vi.fn();
    render(<GeneSearchInput species="petunia" value="" onChange={onChange} onSelect={onSelect} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'DF' } });
    const dfr = await screen.findByText('DFR');
    fireEvent.mouseDown(dfr);
    await waitFor(() => expect(onSelect).toHaveBeenCalled());
    expect(onChange).toHaveBeenLastCalledWith('DFR');           // fills the friendly label
    expect(onSelect.mock.calls[0][0].id).toBe('Peaxi162Scf00238g00125');
  });
});
