import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AssayComparison from './AssayComparison';
import PlasmidMap from './PlasmidMap';
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

  it('renders the assembled molecular structure with components, junctions, and digest cuts', () => {
    render(<PlasmidMap construct={{
      hypothesis_id: 'intended', label: 'Correct insert orientation', length: 1200,
      orientation: 'forward', sequence_sha256: 'abcdef1234567890abcdef',
      insert_interval: { start: 200, end: 600 },
      components: [
        { type: 'vector', start: 0, end: 200 },
        { type: 'insert', start: 200, end: 600, orientation: 'forward' },
        { type: 'vector', start: 600, end: 1200 },
      ],
      junctions: {
        left: { position: 200, sequence: 'A'.repeat(20) + 'C'.repeat(20) },
        right: { position: 600, sequence: 'G'.repeat(20) + 'T'.repeat(20) },
      },
    }} digest={{ cut_sites: [{ enzyme: 'SalI', top_cut: 850 }] }} />);
    expect(screen.getByRole('img', { name: /circular molecular structure, 1200 base pairs/i })).toBeInTheDocument();
    expect(screen.getByText('→ INSERT')).toBeInTheDocument();
    expect(screen.getByText(/Left junction · 200 bp/)).toBeInTheDocument();
    expect(screen.getByText(/SalI · 850/)).toBeInTheDocument();
    expect(screen.getByText(/abcdef1234567890/)).toBeInTheDocument();
  });
});
