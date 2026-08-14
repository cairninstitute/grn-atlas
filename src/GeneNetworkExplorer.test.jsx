import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import GeneNetworkExplorer from './GeneNetworkExplorer';

vi.mock('./components/WorkflowWorkspace', () => ({
  default: ({ onDsRnaSeedChange }) => {
    React.useEffect(() => {
      onDsRnaSeedChange?.({
        target: { id: 'GENE1', symbol: 'EOBI', label: 'EOBI', species: 'petunia' },
        compareTarget: { id: 'GENE2', symbol: 'JAF13', label: 'JAF13', species: 'petunia' },
        geneSet: ['EOBI', 'JAF13', 'AN2'],
        species: 'petunia',
      });
    }, [onDsRnaSeedChange]);
    return <div>WorkflowWorkspace</div>;
  },
}));

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

vi.mock('./components/AnalysisView', () => ({
  default: () => <div>AnalysisView</div>,
}));

vi.mock('./components/PathwayView', () => ({
  default: () => <div>PathwayView</div>,
}));

describe('GeneNetworkExplorer', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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

  it('opens the dsRNA modal from the top-level button without blanking the app', async () => {
    render(<GeneNetworkExplorer />);

    fireEvent.click(screen.getAllByRole('button', { name: /Start from a gene/ })[0]);
    await waitFor(() => expect(screen.getByText('WorkflowWorkspace')).toBeInTheDocument());
    fireEvent.click(screen.getByTitle('Design a dsRNA / predict RNAi silencing + off-targets'));

    await waitFor(() => expect(screen.getByText('Design a dsRNA (RNAi)')).toBeInTheDocument());
    expect(screen.getByPlaceholderText('target gene — type a name (e.g. AN2)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('second target — type a name (e.g. JAF13)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('gene names/ids, space or comma separated (e.g. AN2, DFR, JAF13)')).toBeInTheDocument();
  });
});
