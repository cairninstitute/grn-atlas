import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import GeneNetworkExplorer from './GeneNetworkExplorer';

vi.mock('./components/Sidebar', () => ({
  default: () => <div>Sidebar</div>,
}));

vi.mock('./components/Toolbar', () => ({
  default: () => <div>Toolbar</div>,
}));

vi.mock('./components/ViewTabs', () => ({
  default: ({ viewMode }) => <div>ViewTabs {viewMode}</div>,
}));

vi.mock('./components/NetworkVisualization', () => ({
  default: () => <div>NetworkVisualization</div>,
}));

vi.mock('./components/GeneDetailPanel', () => ({
  default: () => <div>GeneDetailPanel</div>,
}));

vi.mock('./components/ComparisonView', () => ({
  default: () => <div>ComparisonView</div>,
}));

vi.mock('./components/GenomeComparisonView', () => ({
  default: () => <div>GenomeComparisonView</div>,
}));

vi.mock('./components/GeneSetPanel', () => ({
  default: ({ open }) => (open ? <div>GeneSetPanel</div> : null),
}));

vi.mock('./components/OrganismView', () => ({
  default: () => <div>OrganismView</div>,
}));

vi.mock('./components/InterventionDesigner', () => ({
  default: () => <div>InterventionDesigner</div>,
}));

vi.mock('./components/ToolboxView', () => ({
  default: () => <div>ToolboxView</div>,
}));

vi.mock('./components/PathwayView', () => ({
  default: () => <div>PathwayView</div>,
}));

vi.mock('./components/FeedbackControlView', () => ({
  default: () => <div>FeedbackControlView</div>,
}));

describe('GeneNetworkExplorer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, '', '/');
    global.fetch = vi.fn(async (url) => {
      const urlText = String(url);
      if (urlText.includes('/api/v1/expression/differential')) {
        return { json: async () => ({ available_tissues: ['petal_limb', 'seedling'] }) };
      }
      if (urlText.includes('/api/v1/genes/search')) {
        return { json: async () => ({ results: [{ id: 'GENE1', symbol: 'AN2', label: 'AN2' }] }) };
      }
      return { json: async () => ({}) };
    });
  });

  it('opens the dsRNA modal from the contextual actions menu without blanking the app', async () => {
    render(<GeneNetworkExplorer />);

    fireEvent.click(screen.getByRole('button', { name: 'Explore networks' }));
    await waitFor(() => expect(screen.getByText('Gene regulatory neighborhood')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Design a dsRNA / predict RNAi silencing + off-targets'));

    await waitFor(() => expect(screen.getByText('Design a dsRNA (RNAi)')).toBeInTheDocument());
    expect(screen.getByPlaceholderText('target gene — type a name (e.g. AN2)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('second target — type a name (e.g. JAF13)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('gene names/ids, space or comma separated (e.g. AN2, DFR, JAF13)')).toBeInTheDocument();
  });

  it('opens with a question-led home instead of expert filters', async () => {
    render(<GeneNetworkExplorer />);

    await waitFor(() => expect(screen.getByRole('heading', { name: 'What do you want to understand?' })).toBeInTheDocument());
    expect(screen.getByText('Choose a starting point')).toBeInTheDocument();
    expect(screen.queryByText('Sidebar')).not.toBeInTheDocument();
  });

  it('routes a whole-species question directly to feedback control', async () => {
    render(<GeneNetworkExplorer />);

    fireEvent.click(await screen.findByRole('button', { name: /Find feedback and control systems/ }));

    await waitFor(() => expect(screen.getByText('FeedbackControlView')).toBeInTheDocument());
    expect(screen.getByText('Feedback and control systems')).toBeInTheDocument();
  });

  it('opens the featured control-architecture walkthrough from home', async () => {
    render(<GeneNetworkExplorer />);

    fireEvent.click(await screen.findByRole('button', { name: /From millions of interactions to biological control architecture/ }));

    await waitFor(() => expect(screen.getByRole('heading', {
      name: 'From millions of interactions to biological control architecture',
    })).toBeInTheDocument());
    expect(window.location.search).toContain('view=control-demo');
  });

  it('syncs the research context species to the selected gene species', async () => {
    window.history.replaceState({}, '', '?gene=CHSJ');
    global.fetch = vi.fn(async (url) => {
      const urlText = String(url);
      if (urlText.includes('/api/v1/genes/symbol/CHSJ')) {
        return { json: async () => ({ id: 'Peaxi162Scf00047g01225', symbol: 'CHSJ', species: 'petunia', name: 'chalcone synthase J' }) };
      }
      if (urlText.includes('/api/v1/pathways/neighborhood/Peaxi162Scf00047g01225')) {
        return { json: async () => ({ regulators: [], targets: [] }) };
      }
      return { json: async () => ({}) };
    });

    render(<GeneNetworkExplorer />);

    await waitFor(() => expect(screen.getByText('CHSJ')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('petunia')).toBeInTheDocument());
  });
});
