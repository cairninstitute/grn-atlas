import React, { useState } from 'react';
import { analysisAPI } from '../services/apiService';

export default function RegulonDiffWorkflow() {
  const [geneId, setGeneId] = useState('');
  const [species, setSpecies] = useState('arabidopsis');
  const [groupA, setGroupA] = useState('');
  const [groupB, setGroupB] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(null);
  const [error, setError] = useState(null);
  const [regulon, setRegulon] = useState(null);
  const [diffResults, setDiffResults] = useState(null);
  const [availableTissues, setAvailableTissues] = useState(null);

  const run = async () => {
    if (!geneId.trim()) { setError('TF Gene ID is required'); return; }
    if (!groupA.trim() || !groupB.trim()) { setError('Both tissue groups are required'); return; }
    setLoading(true); setError(null); setRegulon(null); setDiffResults(null);
    try {
      setStep('Extracting regulon...');
      const regData = await analysisAPI.regulon(geneId.trim(), { depth: 1 });
      if (regData.error) throw new Error(regData.error);
      setRegulon(regData);
      const targetIds = Object.keys(regData.genes || {});
      if (targetIds.length === 0) { setError('No regulon targets found'); return; }

      setStep(`Comparing regulation of ${targetIds.length} targets across tissues...`);
      const diffData = await analysisAPI.diffRegulation({
        species,
        tfGeneId: geneId.trim(),
        groupA: groupA.split(',').map(s => s.trim()).filter(Boolean),
        groupB: groupB.split(',').map(s => s.trim()).filter(Boolean),
      });
      if (diffData.error) throw new Error(diffData.error);
      if (diffData.available_tissues) setAvailableTissues(diffData.available_tissues);
      setDiffResults(diffData);
      setStep(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchTissues = async () => {
    try {
      const data = await analysisAPI.diffRegulation({ species, groupA: [], groupB: [] });
      if (data.available_tissues) setAvailableTissues(data.available_tissues);
    } catch {}
  };

  return (
    <div>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '0 0 12px' }}>
        Extract a TF's regulon, then compare its regulatory activity across tissue conditions.
      </p>
      <div className="analysis-form">
        <div className="field">
          <label>Species</label>
          <select value={species} onChange={e => { setSpecies(e.target.value); setAvailableTissues(null); }}>
            <option value="arabidopsis">Arabidopsis</option>
            <option value="tomato">Tomato</option>
            <option value="petunia">Petunia</option>
          </select>
          <button type="button" onClick={fetchTissues}
            style={{ fontSize: '0.75rem', marginLeft: 4 }}>Show tissues</button>
        </div>
        <div className="field">
          <label>TF Gene ID</label>
          <input type="text" value={geneId} onChange={e => setGeneId(e.target.value)}
            placeholder="e.g. AT5G11260" />
        </div>
        <div className="field" style={{ minWidth: 150 }}>
          <label>Group A Tissues</label>
          <input type="text" value={groupA} onChange={e => setGroupA(e.target.value)}
            placeholder="root,seedling" />
        </div>
        <div className="field" style={{ minWidth: 150 }}>
          <label>Group B Tissues</label>
          <input type="text" value={groupB} onChange={e => setGroupB(e.target.value)}
            placeholder="leaf,flower" />
        </div>
        <button className="btn-run" onClick={run} disabled={loading}>
          {loading ? step || 'Running...' : 'Regulon → Diff'}
        </button>
      </div>

      {availableTissues && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '4px 0 8px' }}>
          Available tissues: {availableTissues.join(', ')}
        </div>
      )}

      {error && <div className="analysis-error">{error}</div>}

      {regulon && (
        <div className="analysis-stats">
          <div className="analysis-stat">
            <div className="stat-value">{regulon.total}</div>
            <div className="stat-label">Regulon size</div>
          </div>
          <div className="analysis-stat">
            <div className="stat-value">{regulon.symbol}</div>
            <div className="stat-label">TF</div>
          </div>
        </div>
      )}

      {diffResults && diffResults.results?.length > 0 && (
        <div className="analysis-table-wrap">
          <table className="analysis-table">
            <thead>
              <tr><th>TF</th><th>Mean A</th><th>Mean B</th><th>Fold Change</th><th>Dir</th><th>Targets</th></tr>
            </thead>
            <tbody>
              {diffResults.results.map((r, i) => (
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
      )}

      {diffResults && diffResults.note && (
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 8, fontStyle: 'italic' }}>
          {diffResults.note}
        </div>
      )}
    </div>
  );
}
