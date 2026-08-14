export const initialResearchSession = {
  species: null,
  intent: 'experiment',
  focusGene: null,
  candidateSet: [],
  mappedGeneIds: [],
  phenotypeQuestion: '',
  comparison: {
    groupA: [],
    groupB: [],
  },
  artifacts: {},
};

function mergeArtifacts(current, patch = {}) {
  return { ...current, ...patch };
}

function dedupeCandidates(candidates = []) {
  const seen = new Set();
  const out = [];
  for (const gene of candidates) {
    const id = gene?.gene_id || gene?.id || gene?.symbol;
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push({
      id,
      gene_id: gene?.gene_id || gene?.id || id,
      symbol: gene?.symbol || gene?.label || id,
      label: gene?.label || gene?.symbol || id,
      species: gene?.species || null,
    });
  }
  return out;
}

export function researchSessionReducer(state, action) {
  switch (action.type) {
    case 'SET_SPECIES':
      return { ...state, species: action.species || null };
    case 'SET_INTENT':
      return { ...state, intent: action.intent || state.intent };
    case 'SET_FOCUS_GENE':
      return { ...state, focusGene: action.gene || null };
    case 'SET_CANDIDATE_SET':
      return { ...state, candidateSet: dedupeCandidates(action.candidates || []) };
    case 'SET_MAPPED_GENE_IDS':
      return { ...state, mappedGeneIds: [...new Set(action.geneIds || [])] };
    case 'SET_PHENOTYPE_QUESTION':
      return { ...state, phenotypeQuestion: action.question || '' };
    case 'SET_COMPARISON':
      return {
        ...state,
        comparison: {
          groupA: [...new Set(action.groupA || [])],
          groupB: [...new Set(action.groupB || [])],
        },
      };
    case 'MERGE_ARTIFACTS':
      return { ...state, artifacts: mergeArtifacts(state.artifacts, action.artifacts) };
    case 'SYNC_WORKFLOW':
      return {
        ...state,
        species: action.payload?.species || state.species,
        intent: action.payload?.intent || state.intent,
        focusGene: action.payload?.focusGene || state.focusGene,
        candidateSet: action.payload?.candidateSet
          ? dedupeCandidates(action.payload.candidateSet)
          : state.candidateSet,
        mappedGeneIds: action.payload?.mappedGeneIds
          ? [...new Set(action.payload.mappedGeneIds)]
          : state.mappedGeneIds,
        phenotypeQuestion: action.payload?.phenotypeQuestion ?? state.phenotypeQuestion,
        comparison: action.payload?.comparison
          ? {
              groupA: [...new Set(action.payload.comparison.groupA || [])],
              groupB: [...new Set(action.payload.comparison.groupB || [])],
            }
          : state.comparison,
        artifacts: action.payload?.artifacts
          ? mergeArtifacts(state.artifacts, action.payload.artifacts)
          : state.artifacts,
      };
    case 'RESET_RESEARCH_SESSION':
      return initialResearchSession;
    default:
      return state;
  }
}
