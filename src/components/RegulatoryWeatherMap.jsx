import React, { useEffect, useMemo, useState } from 'react';
import '../styles/RegulatoryWeatherMap.css';

const API = import.meta.env.VITE_API_URL || '';

const SPECIES_LABELS = {
  arabidopsis: { short: 'Ath', latin: 'A. thaliana' },
  tomato:      { short: 'Sly', latin: 'S. lycopersicum' },
  petunia:     { short: 'Pax', latin: 'P. axillaris' },
  potato:      { short: 'Stu', latin: 'S. tuberosum' },
  rice:        { short: 'Osa', latin: 'O. sativa' },
  pepper:      { short: 'Can', latin: 'C. annuum' },
  human:       { short: 'Hsa', latin: 'H. sapiens' },
  mouse:       { short: 'Mmu', latin: 'M. musculus' },
};

function heatColor(value, max) {
  if (!value || max === 0) return 'var(--wm-empty, #1a1a2e)';
  const t = Math.min(value / max, 1);
  if (t < 0.25) return `rgba(59, 139, 212, ${0.15 + t * 2})`;
  if (t < 0.5)  return `rgba(59, 139, 212, ${0.55 + (t - 0.25) * 1.5})`;
  if (t < 0.75) return `rgba(127, 119, 221, ${0.6 + (t - 0.5) * 1.2})`;
  return `rgba(232, 163, 61, ${0.7 + (t - 0.75) * 1.2})`;
}

function conservationBar(count, total) {
  const pct = (count / total) * 100;
  let color = '#4CAF50';
  if (pct < 50) color = '#F44336';
  else if (pct < 75) color = '#FF9800';
  return (
    <div className="wm-conservation">
      <div className="wm-conservation-fill" style={{ width: `${pct}%`, background: color }} />
      <span className="wm-conservation-label">{count}/{total}</span>
    </div>
  );
}

export default function RegulatoryWeatherMap() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [metric, setMetric] = useState('tf_count');
  const [hoveredCell, setHoveredCell] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/v1/regulatory-map`)
      .then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  const maxVal = useMemo(() => {
    if (!data) return 1;
    let mx = 1;
    for (const row of data.matrix) {
      for (const sp of data.species) {
        const v = row.species[sp]?.[metric] || 0;
        if (v > mx) mx = v;
      }
    }
    return mx;
  }, [data, metric]);

  if (loading) return <div className="wm-loading">Loading regulatory map...</div>;
  if (error) return <div className="wm-error">Error: {error}</div>;
  if (!data) return null;

  const totalSpecies = data.species.length;

  return (
    <div className="wm-container">
      <div className="wm-header">
        <div className="wm-title-block">
          <h2 className="wm-title">Regulatory Weather Map</h2>
          <p className="wm-subtitle">
            {data.total_tfs.toLocaleString()} transcription factors across {totalSpecies} species
          </p>
        </div>
        <div className="wm-controls">
          <div className="wm-metric-switch">
            {[
              { id: 'tf_count', label: 'TF count' },
              { id: 'target_count', label: 'Targets' },
              { id: 'edge_count', label: 'Edges' },
            ].map(m => (
              <button
                key={m.id}
                className={`wm-metric-btn ${metric === m.id ? 'active' : ''}`}
                onClick={() => setMetric(m.id)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="wm-scroll">
        <table className="wm-table">
          <thead>
            <tr>
              <th className="wm-th-family">Family</th>
              <th className="wm-th-conservation">Conservation</th>
              {data.species.map(sp => (
                <th key={sp} className="wm-th-species" title={SPECIES_LABELS[sp]?.latin || sp}>
                  <span className="wm-sp-short">{SPECIES_LABELS[sp]?.short || sp.slice(0, 3)}</span>
                  <span className="wm-sp-total">{data.species_totals[sp]}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.matrix.map(row => {
              const fam = row.family;
              return (
                <tr key={fam} className={fam === 'Other' ? 'wm-row-other' : ''}>
                  <td className="wm-td-family">{fam}</td>
                  <td className="wm-td-conservation">
                    {conservationBar(row.conservation, totalSpecies)}
                  </td>
                  {data.species.map(sp => {
                    const cell = row.species[sp];
                    const val = cell?.[metric] || 0;
                    const isHovered =
                      hoveredCell?.family === fam && hoveredCell?.species === sp;
                    return (
                      <td
                        key={sp}
                        className={`wm-cell ${isHovered ? 'wm-cell-hover' : ''}`}
                        style={{ background: heatColor(val, maxVal) }}
                        onMouseEnter={() => setHoveredCell({ family: fam, species: sp })}
                        onMouseLeave={() => setHoveredCell(null)}
                      >
                        {val > 0 && <span className="wm-cell-val">{val}</span>}
                        {isHovered && cell && (
                          <div className="wm-tooltip">
                            <strong>{fam}</strong> in {SPECIES_LABELS[sp]?.latin || sp}
                            <div className="wm-tooltip-row">TFs: {cell.tf_count}</div>
                            <div className="wm-tooltip-row">Targets: {cell.target_count.toLocaleString()}</div>
                            <div className="wm-tooltip-row">Edges: {cell.edge_count.toLocaleString()}</div>
                          </div>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="wm-legend">
        <div className="wm-legend-title">Intensity scale ({metric.replace('_', ' ')})</div>
        <div className="wm-legend-bar">
          <span className="wm-legend-lo">0</span>
          <div className="wm-gradient" />
          <span className="wm-legend-hi">{maxVal.toLocaleString()}</span>
        </div>
        <div className="wm-legend-note">
          Conservation = number of species with at least one TF in the family
        </div>
      </div>
    </div>
  );
}
