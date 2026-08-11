const API_BASE = '/api/v1';

// Gene API calls
export const geneAPI = {
  search: async (query, limit = 10, species = null) => {
    const params = new URLSearchParams({ q: query, limit });
    if (species) params.append('species', species);
    const response = await fetch(`${API_BASE}/genes/search?${params}`);
    return response.json();
  },

  getById: async (geneId) => {
    const response = await fetch(`${API_BASE}/genes/${geneId}`);
    return response.json();
  },

  getBySymbol: async (symbol) => {
    const response = await fetch(`${API_BASE}/genes/symbol/${symbol}`);
    return response.json();
  },

  getRegulators: async (geneId) => {
    const response = await fetch(`${API_BASE}/genes/${geneId}/regulators`);
    return response.json();
  },

  getTargets: async (geneId) => {
    const response = await fetch(`${API_BASE}/genes/${geneId}/targets`);
    return response.json();
  },

  getInteractions: async (geneId) => {
    const response = await fetch(`${API_BASE}/genes/${geneId}/interactions`);
    return response.json();
  },

  getExpression: async (geneId) => {
    const response = await fetch(`${API_BASE}/expression/${geneId}`);
    return response.json();
  },

  getOrthology: async (geneId, species = null) => {
    const params = species ? `?species=${species.join(',')}` : '';
    const response = await fetch(`${API_BASE}/genes/orthology/${geneId}${params}`);
    return response.json();
  }
};

// Pathway API calls
export const pathwayAPI = {
  findPaths: async (sourceGeneId, targetSymbol, options = {}) => {
    const response = await fetch(`${API_BASE}/pathways/pathfinding`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_gene_id: sourceGeneId,
        target_symbol: targetSymbol,
        max_depth: options.maxDepth || 3,
        limit: options.limit || 20,
        min_confidence: options.minConfidence || 0.3,
        regulation_type: options.regulationType || ['activation', 'repression'],
        ...options
      })
    });
    return response.json();
  },

  getNeighborhood: async (geneId, options = {}) => {
    const response = await fetch(`${API_BASE}/pathways/neighborhood/${geneId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        max_depth: options.maxDepth || 1,
        direction: options.direction || 'both',
        regulation_type: options.regulationType || ['activation', 'repression'],
        min_confidence: options.minConfidence || 0.3,
        ...options
      })
    });
    return response.json();
  },

  getSubgraph: async (geneIds, format = 'json') => {
    const response = await fetch(`${API_BASE}/pathways/subgraph`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: geneIds,
        format: format // 'json', 'cytoscape', 'graphml'
      })
    });
    return response.json();
  },

  predictCascade: async (targetGeneId, interventions, options = {}) => {
    const response = await fetch(`${API_BASE}/pathway/predict-cascade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_gene_id: targetGeneId,
        interventions: interventions,
        depth: options.depth || 3,
        return_nodes: options.returnNodes !== false,
        ...options
      })
    });
    return response.json();
  },

  // Signed-path propagation: predict qualitative up/down of downstream genes
  // after a set of ko/oe perturbations.
  perturb: async (interventions, options = {}) => {
    const response = await fetch(`${API_BASE}/perturb`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        interventions,
        depth: options.depth || 4,
        min_confidence: options.minConfidence || 0.0,
        include_inferred: options.includeInferred !== false,
      })
    });
    return response.json();
  }
};

// Gene-set analysis: induced subgraph + GO enrichment
export const analysisAPI = {
  subgraph: async (geneIds, options = {}) => {
    const response = await fetch(`${API_BASE}/pathways/subgraph`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: geneIds,
        min_confidence: options.minConfidence || 0.0,
        include_inferred: options.includeInferred !== false,
      }),
    });
    return response.json();
  },

  enrich: async (geneIds, species) => {
    const response = await fetch(`${API_BASE}/enrichment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gene_ids: geneIds, species }),
    });
    return response.json();
  },

  // Predicted dsRNA/RNAi silencing: analyze (sequence) or design (target gene).
  dsrna: async (options = {}) => {
    const response = await fetch(`${API_BASE}/dsrna`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sequence: options.sequence || null,
        target_gene_id: options.targetGeneId || null,
        species: options.species || null,
        design_window: options.designWindow || 250,
      }),
    });
    return response.json();
  },

  // Batch dsRNA-designability screen across a gene set (or a pathway).
  dsrnaScreen: async (geneIds, species, options = {}) => {
    const response = await fetch(`${API_BASE}/dsrna/screen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: geneIds, pathway_id: options.pathwayId || null, species,
        design_window: options.designWindow || 250,
      }),
    });
    return response.json();
  },

  traitEnrich: async (geneIds, species) => {
    const response = await fetch(`${API_BASE}/trait_enrichment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gene_ids: geneIds, species }),
    });
    return response.json();
  },

  pathwayEnrich: async (geneIds, species) => {
    const response = await fetch(`${API_BASE}/pathway_enrichment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gene_ids: geneIds, species }),
    });
    return response.json();
  },

  motifEnrich: async (geneIds, species) => {
    const response = await fetch(`${API_BASE}/motif_enrichment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gene_ids: geneIds, species }),
    });
    return response.json();
  },

  // Predicted co-expression partners of a gene (petunia) across the RNA-seq panel.
  coexpression: async (geneId, options = {}) => {
    const response = await fetch(`${API_BASE}/coexpression`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_id: geneId,
        top: options.top || 25,
        min_abs_r: options.minAbsR ?? 0.7,
        tf_only: options.tfOnly || false,
      }),
    });
    return response.json();
  },

  conservation: async (geneIds, speciesB, options = {}) => {
    const response = await fetch(`${API_BASE}/conservation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: geneIds, species_b: speciesB,
        include_inferred: options.includeInferred !== false,
      }),
    });
    return response.json();
  },

  regulon: async (geneId, options = {}) => {
    const response = await fetch(`${API_BASE}/regulon`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_id: geneId,
        depth: options.depth || 2,
        min_confidence: options.minConfidence || 0.0,
        include_inferred: options.includeInferred !== false,
      }),
    });
    return response.json();
  },

  regulonCompare: async (tfA, tfB, options = {}) => {
    const response = await fetch(`${API_BASE}/regulon/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tf_a: tfA, tf_b: tfB,
        depth: options.depth || 2,
        min_confidence: options.minConfidence || 0.0,
        include_inferred: options.includeInferred !== false,
      }),
    });
    return response.json();
  },

  upstreamRegulators: async (geneIds, species, options = {}) => {
    const response = await fetch(`${API_BASE}/upstream-regulators`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: geneIds, species,
        depth: options.depth || 1,
        top: options.top || 50,
        min_overlap: options.minOverlap || 2,
        min_confidence: options.minConfidence || 0.0,
        include_inferred: options.includeInferred !== false,
      }),
    });
    return response.json();
  },

  networkPatterns: async (options = {}) => {
    const response = await fetch(`${API_BASE}/network/patterns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || null,
        species: options.species || null,
        pattern_types: options.patternTypes || ['ffl', 'autoregulation', 'bifan'],
        min_confidence: options.minConfidence || 0.0,
        limit: options.limit || 100,
      }),
    });
    return response.json();
  },

  centrality: async (options = {}) => {
    const response = await fetch(`${API_BASE}/network/centrality`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species: options.species || null,
        gene_ids: options.geneIds || null,
        metric: options.metric || 'degree',
        top: options.top || 50,
        min_confidence: options.minConfidence || 0.0,
        include_inferred: options.includeInferred !== false,
      }),
    });
    return response.json();
  },

  motifQuery: async (options = {}) => {
    const response = await fetch(`${API_BASE}/motif/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_id: options.geneId || null,
        tf_gene_id: options.tfGeneId || null,
        species: options.species || null,
        max_pvalue: options.maxPvalue || 1e-4,
        min_score: options.minScore || 0,
        include_edge_support: options.includeEdgeSupport || false,
        top: options.top || 100,
      }),
    });
    return response.json();
  },

  modules: async (options = {}) => {
    const response = await fetch(`${API_BASE}/network/modules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species: options.species || null,
        algorithm: options.algorithm || 'louvain',
        ...(options.geneId && { gene_id: options.geneId }),
        min_confidence: options.minConfidence || 0,
        include_inferred: options.includeInferred !== false,
        resolution: options.resolution || 0.01,
        top_modules: options.topModules || 20,
        max_genes_per_module: options.maxGenesPerModule || 50,
      }),
    });
    return response.json();
  },

  diffRegulation: async (options = {}) => {
    const response = await fetch(`${API_BASE}/differential-regulation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species: options.species || null,
        ...(options.tfGeneId && { tf_gene_id: options.tfGeneId }),
        group_a: options.groupA || [],
        group_b: options.groupB || [],
        min_fold_change: options.minFoldChange || 1.0,
        top: options.top || 50,
      }),
    });
    return response.json();
  },

  inferredEdges: async (options = {}) => {
    const response = await fetch(`${API_BASE}/inferred-edges`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species: options.species || null,
        ...(options.geneId && { gene_id: options.geneId }),
        direction: options.direction || 'both',
        ...(options.method && { method: options.method }),
        min_importance: options.minImportance || 0.01,
        compare_curated: options.compareCurated || false,
        top: options.top || 50,
      }),
    });
    return response.json();
  },

  exportEdges: async (options = {}) => {
    const response = await fetch(`${API_BASE}/export/edges`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        min_confidence: options.minConfidence || 0,
        include_inferred: options.includeInferred !== false,
        signed_only: options.signedOnly || false,
        include_sequence_context: options.includeSequenceContext || false,
        format: options.format || 'json',
      }),
    });
    return response.json();
  },
};

// Genome / synteny comparison
export const genomeAPI = {
  getSpecies: async () => {
    const response = await fetch(`${API_BASE}/genome/species`);
    return response.json();
  },

  getGenome: async (species) => {
    const response = await fetch(`${API_BASE}/genome/${species}`);
    return response.json();
  },

  getOrthologs: async (speciesA, speciesB) => {
    const params = new URLSearchParams({ species_a: speciesA, species_b: speciesB });
    const response = await fetch(`${API_BASE}/genome/orthologs?${params}`);
    return response.json();
  }
};

// Analytics / Stats
export const analyticsAPI = {
  getStats: async () => {
    const response = await fetch(`${API_BASE}/stats`);
    return response.json();
  },

  getSpeciesStats: async (species) => {
    const response = await fetch(`${API_BASE}/stats/species/${species}`);
    return response.json();
  }
};

export const workflowAPI = {
  importDataset: async (options = {}) => {
    const response = await fetch(`${API_BASE}/datasets/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: options.content || '',
        species: options.species || null,
        filename: options.filename || null,
      }),
    });
    return response.json();
  },

  analyzeGeneSet: async (options = {}) => {
    const response = await fetch(`${API_BASE}/user/gene-set/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: options.content || null,
        gene_ids: options.geneIds || null,
        species: options.species || null,
        filename: options.filename || null,
        intent: options.intent || 'experiment',
        top_terms: options.topTerms || 8,
        top_regulators: options.topRegulators || 8,
        top_candidates: options.topCandidates || 5,
        include_subgraph: options.includeSubgraph !== false,
      }),
    });
    return response.json();
  },

  consensusRanking: async (options = {}) => {
    const response = await fetch(`${API_BASE}/research/consensus-ranking`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        intent: options.intent || 'experiment',
        species: options.species || null,
        top_n: options.topN || 10,
        include_external: options.includeExternal || false,
        years_back: options.yearsBack || 5,
      }),
    });
    return response.json();
  },

  counterfactualAnalysis: async (options = {}) => {
    const response = await fetch(`${API_BASE}/research/counterfactual-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        intent: options.intent || 'experiment',
        species: options.species || null,
        include_external: options.includeExternal || false,
        years_back: options.yearsBack || 5,
      }),
    });
    return response.json();
  },

  researchBrief: async (options = {}) => {
    const response = await fetch(`${API_BASE}/research/brief`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        intent: options.intent || 'experiment',
        species: options.species || null,
        max_candidates: options.maxCandidates || 5,
        max_experiments: options.maxExperiments || 3,
      }),
    });
    return response.json();
  },

  validationPlan: async (options = {}) => {
    const response = await fetch(`${API_BASE}/research/validation-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        intent: options.intent || 'experiment',
        species: options.species || null,
        max_candidates: options.maxCandidates || 3,
        max_experiments: options.maxExperiments || 3,
      }),
    });
    return response.json();
  },

  studyReport: async (options = {}) => {
    const response = await fetch(`${API_BASE}/research/study-report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        intent: options.intent || 'experiment',
        species: options.species || null,
        max_candidates: options.maxCandidates || 3,
        max_experiments: options.maxExperiments || 3,
      }),
    });
    return response.json();
  },

  experimentOptimize: async (options = {}) => {
    const response = await fetch(`${API_BASE}/experiments/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        intent: options.intent || 'experiment',
        species: options.species || null,
        budget_level: options.budgetLevel || null,
        timeline_days: options.timelineDays || null,
        allowed_assays: options.allowedAssays || [],
        max_recommendations: options.maxRecommendations || 5,
      }),
    });
    return response.json();
  },

  differentialExpression: async (options = {}) => {
    const response = await fetch(`${API_BASE}/expression/differential`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species: options.species || null,
        group_a: options.groupA || [],
        group_b: options.groupB || [],
        content: options.content || null,
        filename: options.filename || null,
        top: options.top || 50,
        min_abs_log2fc: options.minAbsLog2Fc || 0,
      }),
    });
    return response.json();
  },

  literatureReview: async (options = {}) => {
    const params = new URLSearchParams({
      scope: options.scope || 'gene',
      years_back: String(options.yearsBack || 5),
      max_results: String(options.maxResults || 10),
    });
    if (options.geneId) params.set('gene_id', options.geneId);
    if (options.sourceId) params.set('source_id', options.sourceId);
    if (options.targetId) params.set('target_id', options.targetId);
    if (options.query) params.set('query', options.query);
    if (options.species) params.set('species', options.species);
    const response = await fetch(`${API_BASE}/literature/review?${params.toString()}`);
    return response.json();
  },

  variantEffect: async (options = {}) => {
    const response = await fetch(`${API_BASE}/variants/effect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_id: options.geneId,
        position: options.position,
        assembly: options.assembly || null,
        window_type: options.windowType || 'promoter',
        ref: options.ref || null,
        alt: options.alt || null,
      }),
    });
    return response.json();
  },

  promoterEditPrioritize: async (options = {}) => {
    const response = await fetch(`${API_BASE}/promoter/edit-prioritize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_id: options.geneId,
        top: options.top || 10,
      }),
    });
    return response.json();
  },

  crisprDesign: async (options = {}) => {
    const response = await fetch(`${API_BASE}/crispr/design`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sequence: options.sequence || null,
        gene_id: options.geneId || null,
        pam: options.pam || 'NGG',
        top: options.top || 10,
      }),
    });
    return response.json();
  },

  primerDesign: async (options = {}) => {
    const response = await fetch(`${API_BASE}/primers/design`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sequence: options.sequence || null,
        gene_id: options.geneId || null,
        product_min: options.productMin || 80,
        product_max: options.productMax || 250,
        top: options.top || 10,
      }),
    });
    return response.json();
  },

  celltypeRegulation: async (options = {}) => {
    const response = await fetch(`${API_BASE}/celltype/regulation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species: options.species,
        gene_ids: options.geneIds || null,
      }),
    });
    return response.json();
  },

  trajectoryRegulation: async (options = {}) => {
    const response = await fetch(`${API_BASE}/trajectory/regulation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species: options.species,
        gene_ids: options.geneIds || null,
      }),
    });
    return response.json();
  },

  combinatorialPerturbation: async (options = {}) => {
    const response = await fetch(`${API_BASE}/perturb/combinatorial`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gene_ids: options.geneIds || [],
        action: options.action || 'ko',
        combo_size: options.comboSize || 2,
        species: options.species || null,
        top: options.top || 10,
      }),
    });
    return response.json();
  },

  speciesOnboardingPlan: async (options = {}) => {
    const response = await fetch(`${API_BASE}/species/onboarding-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        species_name: options.speciesName,
        intended_capabilities: options.intendedCapabilities || [],
      }),
    });
    return response.json();
  },
};

// GraphQL query helper
export const graphqlAPI = {
  query: async (query, variables = {}) => {
    const response = await fetch('/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, variables })
    });
    return response.json();
  }
};

// Export/Download utilities
export const exportAPI = {
  exportCytoscape: async (geneIds) => {
    const data = await pathwayAPI.getSubgraph(geneIds, 'cytoscape');
    return data;
  },

  exportGraphML: async (geneIds) => {
    const data = await pathwayAPI.getSubgraph(geneIds, 'graphml');
    downloadFile(data, `network_${Date.now()}.graphml`, 'application/xml');
  },

  exportJSON: async (geneIds) => {
    const data = await pathwayAPI.getSubgraph(geneIds, 'json');
    downloadFile(JSON.stringify(data, null, 2), `network_${Date.now()}.json`, 'application/json');
  }
};

// Utility function to download files
function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// Caching utility
class APICache {
  constructor(ttl = 5 * 60 * 1000) { // 5 minutes default
    this.cache = new Map();
    this.ttl = ttl;
  }

  set(key, value) {
    this.cache.set(key, {
      value,
      timestamp: Date.now()
    });
  }

  get(key) {
    const item = this.cache.get(key);
    if (!item) return null;

    if (Date.now() - item.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }

    return item.value;
  }

  clear() {
    this.cache.clear();
  }
}

export const apiCache = new APICache();

// Rate limiting utility
class RateLimiter {
  constructor(maxRequests = 10, windowMs = 1000) {
    this.maxRequests = maxRequests;
    this.windowMs = windowMs;
    this.requests = [];
  }

  async wait() {
    const now = Date.now();
    this.requests = this.requests.filter(t => now - t < this.windowMs);

    if (this.requests.length >= this.maxRequests) {
      const oldestRequest = this.requests[0];
      const waitTime = this.windowMs - (now - oldestRequest) + 10;
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }

    this.requests.push(now);
  }
}

export const rateLimiter = new RateLimiter(30, 1000); // 30 requests per second
