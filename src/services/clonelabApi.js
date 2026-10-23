const BASE = '/api/v1/clonelab';

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || `CloneLab request failed (${response.status})`);
  return body;
}

export const clonelabAPI = {
  listDemonstrations: () => request('/demonstrations'),
  loadDemonstration: (id) => request(`/demonstrations/${encodeURIComponent(id)}`),
  generateHypotheses: (payload) => request('/constructs/hypotheses', {
    method: 'POST', body: JSON.stringify(payload),
  }),
  optimizeDigest: (payload) => request('/assays/optimize', {
    method: 'POST', body: JSON.stringify(payload),
  }),
  simulateGel: (payload) => request('/gels/simulate', {
    method: 'POST', body: JSON.stringify(payload),
  }),
  interpretResults: (payload) => request('/results/interpret', {
    method: 'POST', body: JSON.stringify(payload),
  }),
  exportReport: (payload) => request('/reports/export', {
    method: 'POST', body: JSON.stringify(payload),
  }),
};
