import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WorkflowWorkspace from './WorkflowWorkspace';
import { geneAPI, workflowAPI } from '../services/apiService';

const mocks = vi.hoisted(() => ({
  differentialExpressionMock: vi.fn(),
}));

vi.mock('../services/apiService', () => ({
  geneAPI: {
    search: vi.fn(),
  },
  workflowAPI: {
    importDataset: vi.fn(),
    analyzeGeneSet: vi.fn(),
    consensusRanking: vi.fn(),
    counterfactualAnalysis: vi.fn(),
    researchBrief: vi.fn(),
    validationPlan: vi.fn(),
    studyReport: vi.fn(),
    experimentOptimize: vi.fn(),
    differentialExpression: mocks.differentialExpressionMock,
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
  it('renders the workflow-first researcher entry shell', async () => {
    mocks.differentialExpressionMock.mockResolvedValue({ available_tissues: ['flower', 'petal_limb'] });
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
        onFocusGeneChange={() => {}}
        onOpenGeneSetAnalysis={() => {}}
        onOpenDsRna={() => {}}
      />,
    );

    expect(screen.getByText('Run the atlas like a study, not a demo.')).toBeInTheDocument();
    expect(screen.getByText('Start from a hit list')).toBeInTheDocument();
    expect(screen.getByText('2. Start from a phenotype question')).toBeInTheDocument();
    expect(screen.getByText('4. First-pass interpretation')).toBeInTheDocument();
    expect(screen.getByText('Current focus gene')).toBeInTheDocument();
    expect(screen.getByText('Allowed follow-up types')).toBeInTheDocument();
    expect(screen.getByText('Computational only')).toBeInTheDocument();
    expect(screen.getByText('RNAi / dsRNA design')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Available tissue labels for human')).toBeInTheDocument());
    expect(screen.getByText('flower')).toBeInTheDocument();
    expect(screen.getAllByText('TP53').length).toBeGreaterThan(0);
  });

  it('loads literature-suggested genes into the hit list and shows paper abstracts', async () => {
    mocks.differentialExpressionMock.mockResolvedValue({ available_tissues: ['flower', 'petal_limb'] });
    workflowAPI.literatureReview.mockResolvedValue({
      search_term: 'petunia flower color pigmentation anthocyanin regulator gene target',
      summary: {
        direct_phenotype_evidence: 2,
        comparative_evidence: 1,
        mechanistic_background: 1,
        low_relevance: 0,
      },
      candidate_summary: {
        candidate_genes: [
          { name: 'DntMYB1-Centered', mentions: 3 },
          { name: 'RcMYB308', mentions: 2 },
        ],
        mechanisms: [{ name: 'anthocyanin', mentions: 4 }],
      },
      results: [
        {
          year: '2026',
          title: 'A petunia color regulator paper',
          classification: 'direct_phenotype_evidence',
          snippet: 'This abstract explains a candidate regulator for flower color.',
          url: 'https://example.org/paper',
        },
      ],
    });
    workflowAPI.importDataset.mockResolvedValue({
      mapped_gene_ids: ['PeaxiMapped1'],
      mapped_genes: [
        { gene_id: 'PeaxiMapped1', symbol: 'AN2', label: 'AN2', label_inferred: false, species: 'petunia' },
      ],
      unmapped_rows: [{ input: 'RcMYB308' }],
      unmapped_count: 1,
    });
    geneAPI.search.mockImplementation(async (query) => {
      if (query === 'AN2') return { results: [{ id: 'PeaxiMapped1', gene_id: 'PeaxiMapped1', symbol: 'AN2', species: 'petunia', synonyms: ['PAP1'] }] };
      if (query === 'JAF13') return { results: [{ id: 'PeaxiMapped2', gene_id: 'PeaxiMapped2', symbol: 'JAF13', species: 'petunia', synonyms: ['EGL3', 'GL3'] }] };
      if (query === 'DFR') return { results: [{ id: 'PeaxiMapped3', gene_id: 'PeaxiMapped3', symbol: 'Peaxi162Scf00238g00125', label: 'DFR', label_inferred: true, species: 'petunia', synonyms: ['DFR', 'TT3'] }] };
      if (query === 'CHS') return { results: [{ id: 'PeaxiMapped4', gene_id: 'PeaxiMapped4', symbol: 'CHSJ', species: 'petunia', synonyms: ['CHS', 'TT4'] }] };
      if (query === 'MYB') return { results: [{ id: 'PeaxiMapped5', gene_id: 'PeaxiMapped5', symbol: 'MYB12', species: 'petunia', synonyms: ['MYB12'] }] };
      return { results: [] };
    });

    render(
      <WorkflowWorkspace
        selectedGene={null}
        networkData={{ regulators: [], targets: [] }}
        filters={{ species: ['petunia'], includeInferred: true }}
        onNavigate={() => {}}
        onFocusGeneChange={() => {}}
        onOpenGeneSetAnalysis={() => {}}
        onOpenDsRna={() => {}}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Which genes are the best targets for changing flower color in this species?'), {
      target: { value: 'Which genes are the best targets for changing flower color in this species?' },
    });
    fireEvent.click(screen.getByText('Search literature first'));

    await waitFor(() => expect(screen.getByText('Load atlas-mappable genes into hit list')).toBeInTheDocument());
    expect(screen.getByText('Atlas-mappable genes for petunia')).toBeInTheDocument();
    expect(screen.getByText('petunia homolog / family candidates inferred from the literature')).toBeInTheDocument();
    expect(screen.getByText('JAF13')).toBeInTheDocument();
    expect(screen.getByText('CHSJ')).toBeInTheDocument();
    expect(screen.getByText('Literature suggestions not mapped into the selected species')).toBeInTheDocument();
    expect(screen.getByText('This abstract explains a candidate regulator for flower color.')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Load atlas-mappable genes into hit list'));

    const hitList = screen.getByPlaceholderText(/TP53/i);
    expect(hitList.value).toContain('AN2');
    expect(hitList.value).not.toContain('DntMYB1-Centered');
    expect(hitList.value).not.toContain('RcMYB308');
  });

  it('seeds dsRNA from consensus winner and friendly labels', async () => {
    mocks.differentialExpressionMock.mockResolvedValue({ available_tissues: ['flower', 'petal_limb'] });
    const onOpenDsRna = vi.fn();
    const importDatasetPayload = {
      mapped_gene_ids: ['Pea1', 'Pea2'],
      mapped_genes: [
        { gene_id: 'Pea1', symbol: 'Peaxi162Scf00118g00310', label: 'AN2', label_inferred: false, species: 'petunia' },
        { gene_id: 'Pea2', symbol: 'Peaxi162Scf00119g00942', label: 'JAF13', label_inferred: false, species: 'petunia' },
      ],
      unmapped_rows: [],
      unmapped_count: 0,
    };
    workflowAPI.importDataset.mockResolvedValue(importDatasetPayload);
    workflowAPI.analyzeGeneSet.mockResolvedValue({
      import_summary: importDatasetPayload,
      candidate_triage: {
        ranked_candidates: [
          { gene_id: 'Pea2', symbol: 'Peaxi162Scf00119g00942', label: 'JAF13', species: 'petunia' },
        ],
      },
    });
    workflowAPI.consensusRanking.mockResolvedValue({
      ranked_candidates: [
        { gene_id: 'Pea3', symbol: 'Peaxi162Scf00129g01231', label: 'EOBI', species: 'petunia', consensus_score: 0.48 },
      ],
    });
    workflowAPI.counterfactualAnalysis.mockResolvedValue({ overturn_conditions: [] });

    render(
      <WorkflowWorkspace
        selectedGene={{ id: 'Focus1', symbol: 'FOCUS', name: 'focus', species: 'petunia', is_tf: true }}
        networkData={{ regulators: [], targets: [] }}
        filters={{ species: ['petunia'], includeInferred: true }}
        onNavigate={() => {}}
        onFocusGeneChange={() => {}}
        onOpenGeneSetAnalysis={() => {}}
        onOpenDsRna={onOpenDsRna}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(/TP53/i), {
      target: { value: 'AN2\nJAF13' },
    });
    fireEvent.click(screen.getByText('Map genes'));
    await waitFor(() => expect(workflowAPI.importDataset).toHaveBeenCalled());

    fireEvent.click(screen.getByText('Run first-pass analysis'));
    await waitFor(() => expect(workflowAPI.analyzeGeneSet).toHaveBeenCalled());

    fireEvent.click(screen.getByText('Run consensus ranking'));
    await waitFor(() => expect(workflowAPI.consensusRanking).toHaveBeenCalled());

    fireEvent.click(screen.getAllByText('dsRNA')[0]);

    expect(onOpenDsRna).toHaveBeenCalledWith(
      expect.objectContaining({
        target: expect.objectContaining({ label: 'EOBI' }),
        geneSet: expect.arrayContaining(['EOBI', 'JAF13', 'AN2']),
      }),
    );
  });

  it('promotes first-pass and consensus winners to focus gene', async () => {
    mocks.differentialExpressionMock.mockResolvedValue({ available_tissues: ['flower', 'petal_limb'] });
    const onFocusGeneChange = vi.fn();
    workflowAPI.importDataset.mockResolvedValue({
      mapped_gene_ids: ['Pea1'],
      mapped_genes: [{ gene_id: 'Pea1', symbol: 'AN2', label: 'AN2', species: 'petunia' }],
      unmapped_rows: [],
      unmapped_count: 0,
    });
    workflowAPI.analyzeGeneSet.mockResolvedValue({
      import_summary: {
        mapped_gene_ids: ['Pea1'],
        mapped_genes: [{ gene_id: 'Pea1', symbol: 'AN2', label: 'AN2', species: 'petunia' }],
      },
      candidate_triage: {
        ranked_candidates: [{ gene_id: 'Pea2', symbol: 'JAF13', label: 'JAF13', species: 'petunia' }],
      },
    });
    workflowAPI.consensusRanking.mockResolvedValue({
      ranked_candidates: [{ gene_id: 'Pea3', symbol: 'EOBI', label: 'EOBI', species: 'petunia', consensus_score: 0.48 }],
    });
    workflowAPI.counterfactualAnalysis.mockResolvedValue({ overturn_conditions: [] });

    render(
      <WorkflowWorkspace
        selectedGene={null}
        networkData={{ regulators: [], targets: [] }}
        filters={{ species: ['petunia'], includeInferred: true }}
        onNavigate={() => {}}
        onFocusGeneChange={onFocusGeneChange}
        onOpenGeneSetAnalysis={() => {}}
        onOpenDsRna={() => {}}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(/TP53/i), {
      target: { value: 'AN2' },
    });
    fireEvent.click(screen.getByText('Run first-pass analysis'));
    await waitFor(() => expect(onFocusGeneChange).toHaveBeenCalledWith(expect.objectContaining({ label: 'JAF13' })));

    fireEvent.click(screen.getByText('Run consensus ranking'));
    await waitFor(() => expect(onFocusGeneChange).toHaveBeenCalledWith(expect.objectContaining({ label: 'EOBI' })));
  });
});
