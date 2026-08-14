import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function DiffRegulationPanel() {
  const [species, setSpecies] = useState('human');
  const [tfGeneId, setTfGeneId] = useState('');
  const [groupA, setGroupA] = useState('');
  const [groupB, setGroupB] = useState('');
  const [minFoldChange, setMinFoldChange] = useState(1.0);
  const [top, setTop] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [availableTissues, setAvailableTissues] = useState(null);

  const fetchTissues = async () => {
    try {
      const data = await analysisAPI.diffRegulation({
        species, tfGeneId: null, groupA: [], groupB: [],
        minFoldChange, top,
      });
      if (data.available_tissues) setAvailableTissues(data.available_tissues);
    } catch { /* ignore */ }
  };

  const run = async () => {
    if (!groupA.trim() || !groupB.trim()) { setError('Both tissue groups are required'); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await analysisAPI.diffRegulation({
        species,
        tfGeneId: tfGeneId.trim() || null,
        groupA: groupA.split(',').map(s => s.trim()).filter(Boolean),
        groupB: groupB.split(',').map(s => s.trim()).filter(Boolean),
        minFoldChange, top,
      });
      if (data.error) throw new Error(data.error);
      if (data.available_tissues) setAvailableTissues(data.available_tissues);
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="analysis-form">
        <div className="field">
          <label>Species</label>
          <select value={species} onChange={e => { setSpecies(e.target.value); setAvailableTissues(null); }}>
            <option value="human">Human</option>
            <option value="mouse">Mouse</option>
            <option value="arabidopsis">Arabidopsis</option>
            <option value="tomato">Tomato</option>
            <option value="petunia">Petunia</option>
          </select>
          <button type="button" onClick={fetchTissues}
            style={{ fontSize: '0.75rem', marginLeft: 4 }}>Show tissues</button>
        </div>
        <div className="field">
          <label>TF Gene ID (optional)</label>
          <input type="text" value={tfGeneId} onChange={e => setTfGeneId(e.target.value)}
            placeholder="e.g. TP53" />
        </div>
        <div className="field" style={{ minWidth: 180 }}>
          <label>Group A Tissues (comma-separated)</label>
          <input type="text" value={groupA} onChange={e => setGroupA(e.target.value)}
            placeholder="liver,kidney" />
        </div>
        <div className="field" style={{ minWidth: 180 }}>
          <label>Group B Tissues (comma-separated)</label>
          <input type="text" value={groupB} onChange={e => setGroupB(e.target.value)}
            placeholder="brain,heart" />
        </div>
        <div className="field">
          <label>Min Fold Change</label>
          <input type="number" value={minFoldChange} onChange={e => setMinFoldChange(+e.target.value)}
            min={0} step={0.1} style={{ width: 70 }} />
        </div>
        <div className="field">
          <label>Top</label>
          <input type="number" value={top} onChange={e => setTop(+e.target.value)}
            min={1} max={500} style={{ width: 60 }} />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? 'Comparing...' : 'Compare Regulation'}
        </button>
      </div>

      {availableTissues && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '4px 0 8px' }}>
          Available tissues: {availableTissues.join(', ')}
        </div>
      )}

      {error && <div className="analysis-error">{error}</div>}

      {result && (
        <>
          {result.note && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8, fontStyle: 'italic' }}>
              {result.note}
            </div>
          )}
          <div className="analysis-table-wrap">
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>TF Symbol</th><th>Mean A</th><th>Mean B</th>
                  <th>Fold Change</th><th>Direction</th><th>Num Targets</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((r, i) => (
                  <tr key={i}>
                    <td><strong>{r.tf_symbol}</strong></td>
                    <td>{r.mean_a?.toFixed(3)}</td>
                    <td>{r.mean_b?.toFixed(3)}</td>
                    <td>{r.fold_change?.toFixed(2)}</td>
                    <td>{r.direction === 'up' ? '↑' : '↓'}</td>
                    <td>{r.num_targets}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
