import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WorkflowWorkspace from './WorkflowWorkspace';

vi.mock('../services/apiService', () => ({
  workflowAPI: {
    importDataset: vi.fn(),
    analyzeGeneSet: vi.fn(),
    consensusRanking: vi.fn(),
    counterfactualAnalysis: vi.fn(),
    researchBrief: vi.fn(),
    validationPlan: vi.fn(),
    studyReport: vi.fn(),
    experimentOptimize: vi.fn(),
    differentialExpression: vi.fn(),
    literatureReview: vi.fn(),
    variantEffect: vi.fn(),
    promoterEditPrioritize: vi.fn(),
    crisprDesign: vi.fn(),
    primerDesign: vi.fn(),
    celltypeRegulation: vi.fn(),
    trajectoryRegulation: vi.fn(),
    combinatorialPerturbation: vi.fn(),
    speciesOnboardingPlan: vi.fn(),
  },
}));

describe('WorkflowWorkspace', () => {
  it('renders the workflow-first researcher entry shell', () => {
    render(
      <WorkflowWorkspace
        selectedGene={{
          id: 'TP53',
          symbol: 'TP53',
          name: 'tumor protein p53',
          species: 'human',
          is_tf: true,
        }}
        networkData={{
          regulators: [{ id: 'MDM2' }],
          targets: [{ id: 'BAX' }, { id: 'CDKN1A' }],
        }}
        filters={{ species: ['human'], includeInferred: true }}
        onNavigate={() => {}}
        onOpenGeneSetAnalysis={() => {}}
        onOpenDsRna={() => {}}
      />,
    );

    expect(screen.getByText('Run the atlas like a study, not a demo.')).toBeInTheDocument();
    expect(screen.getByText('Start from a hit list')).toBeInTheDocument();
    expect(screen.getByText('3. First-pass interpretation')).toBeInTheDocument();
    expect(screen.getByText('Current focus gene')).toBeInTheDocument();
    expect(screen.getAllByText('TP53').length).toBeGreaterThan(0);
  });
});
