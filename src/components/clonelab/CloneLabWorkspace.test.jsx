import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AssayComparison from './AssayComparison';
import VirtualGel from './VirtualGel';

describe('CloneLab deterministic result views', () => {
  it('shows ambiguity rather than a false success', () => {
    render(<AssayComparison optimization={{
      hypotheses: ['intended', 'reverse'],
      best_digest: { enzymes: ['EcoRI'], fully_discriminatory: false, pairwise_distinguishable: 0, pairwise_total: 1, information_bits: 0 },
      rankings: [{ enzymes: ['EcoRI'], score: 0, unique_hypotheses: [], fully_discriminatory: false }],
      claim_boundary: { sequence_identity: 'A restriction pattern does not establish base-perfect sequence identity.' },
    }} />);
    expect(screen.getByText('Ambiguity remains')).toBeInTheDocument();
    expect(screen.getByText(/does not establish base-perfect/)).toBeInTheDocument();
  });

  it('provides a table equivalent for the gel graphic', () => {
    render(<VirtualGel gel={{ model_boundary: 'Prediction only', lanes: [{
      lane_id: 'sample', label: 'Intended', hidden_fragments: [], bands: [{
        band_id: 'b1', representative_bp: 800, source_fragments_bp: [800], merged: false,
        migration: 0.6, relative_intensity: 1,
      }],
    }] }} />);
    expect(screen.getByRole('cell', { name: 'Intended' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '800' })).toBeInTheDocument();
    expect(screen.getByText('SIMULATION')).toBeInTheDocument();
  });
});
