import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/apiService';

export default function TissueWeightsPanel({ currentGene, currentSpecies }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [tissues, setTissues] = useState([]);
  const [edgeWeights, setEdgeWeights] = useState([]);
  const [selectedTissue, setSelectedTissue] = useState('');

  useEffect(() => {
    if (!currentSpecies) return;
    analysisAPI.listTissues(currentSpecies).then(data => {
      setTissues(data.tissues || []);
    }).catch(() => {});
  }, [currentSpecies]);

  useEffect(() => {
    if (!currentGene?.id) return;
    setLoading(true);
    setError(null);
    const geneId = currentGene.id;

    fetch(`/api/v1/edge-tissues/${encodeURIComponent(geneId)}${selectedTissue ? `?tissue=${encodeURIComponent(selectedTissue)}` : ''}`)
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        setEdgeWeights(data.edges || []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [currentGene?.id, selectedTissue]);

  const maxAbs = edgeWeights.length
    ? Math.max(...edgeWeights.map(e => Math.abs(e.coexpression)))
    : 1;

  return (
    <div>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-2)', marginBottom: 12 }}>
        Tissue-specific coexpression for edges involving <strong>{currentGene?.symbol || currentGene?.id || '—'}</strong>.
        Positive = coactivated, negative = inversely expressed.
      </p>

      {tissues.length > 0 && (
        <div className="analysis-form" style={{ marginBottom: 12 }}>
          <div className="field">
            <label>Filter by tissue</label>
            <select value={selectedTissue} onChange={e => setSelectedTissue(e.target.value)}>
              <option value="">All tissues (global)</option>
              {tissues.map(t => (
                <option key={t.tissue} value={t.tissue}>
                  {t.tissue.replace(/_/g, ' ')} ({t.edge_count.toLocaleString()} edges)
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {loading && <p style={{ color: 'var(--text-2)' }}>Loading tissue weights…</p>}
      {error && <div className="analysis-error">{error}</div>}

      {!loading && !error && edgeWeights.length === 0 && currentGene && (
        <p style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}>
          No tissue coexpression data available for this gene's edges.
          {!tissues.length && ' (No expression data for this species.)'}
        </p>
      )}

      {edgeWeights.length > 0 && (
        <>
          <div className="analysis-stats">
            <div className="analysis-stat">
              <div className="stat-value">{edgeWeights.length}</div>
              <div className="stat-label">Edges with data</div>
            </div>
            {selectedTissue && (
              <div className="analysis-stat">
                <div className="stat-value">{selectedTissue.replace(/_/g, ' ')}</div>
                <div className="stat-label">Tissue</div>
              </div>
            )}
          </div>
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Direction</th>
                  <th>Partner</th>
                  <th>{selectedTissue ? 'Tissue' : 'Best tissue'}</th>
                  <th>r</th>
                  <th>Coexpression</th>
                </tr>
              </thead>
              <tbody>
                {edgeWeights.map((e, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>{e.direction}</td>
                    <td><strong>{e.partner_symbol || e.partner_id}</strong></td>
                    <td style={{ fontSize: '0.8rem' }}>{(e.tissue || '').replace(/_/g, ' ')}</td>
                    <td className="mono">{e.coexpression.toFixed(3)}</td>
                    <td>
                      <span style={{
                        display: 'inline-block',
                        width: `${(Math.abs(e.coexpression) / maxAbs) * 80}px`,
                        height: 12,
                        background: e.coexpression > 0 ? 'var(--accent, #4a9eff)' : '#e05050',
                        borderRadius: 2,
                      }} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!currentGene && (
        <p style={{ color: 'var(--text-2)', fontSize: '0.85rem' }}>
          Select a gene to view tissue coexpression for its regulatory edges.
        </p>
      )}
    </div>
  );
}
