import { describe, it, expect } from 'vitest';
import { geneLabel } from './geneLabel';

describe('geneLabel', () => {
  it('uses a real symbol when it differs from the id', () => {
    expect(geneLabel({ id: 'AT5G13930', symbol: 'TT4' }))
      .toEqual({ label: 'TT4', inferred: false, id: 'AT5G13930' });
  });

  it('falls back to the first inferred synonym when symbol == id', () => {
    const g = { id: 'Peaxi162Scf00047g01225', symbol: 'Peaxi162Scf00047g01225', synonyms: ['CHS', 'TT4'] };
    expect(geneLabel(g)).toEqual({ label: 'CHS', inferred: true, id: 'Peaxi162Scf00047g01225' });
  });

  it('prefers a curated symbol over an inferred synonym', () => {
    // once BLAST gives AN2 as the real symbol, it wins over any synonym
    const g = { id: 'Peaxi162Scf00118g00310', symbol: 'AN2', synonyms: ['PAP1'] };
    expect(geneLabel(g).label).toBe('AN2');
    expect(geneLabel(g).inferred).toBe(false);
  });

  it('falls back to the locus id when there is no symbol or synonym', () => {
    const g = { id: 'Solyc01g000010.2', symbol: 'Solyc01g000010.2' };
    expect(geneLabel(g)).toEqual({ label: 'Solyc01g000010.2', inferred: false, id: 'Solyc01g000010.2' });
  });

  it('handles empty/undefined input', () => {
    expect(geneLabel(null)).toEqual({ label: '', inferred: false, id: '' });
    expect(geneLabel({})).toEqual({ label: '', inferred: false, id: '' });
  });
});
