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
