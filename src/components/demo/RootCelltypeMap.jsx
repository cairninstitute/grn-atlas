import React, { useCallback, useEffect, useState } from 'react';
import '../../styles/RootCelltypeMap.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const CELL_TYPES = [
  { id: 'meristem', label: 'Meristem', color: '#6b9d8e', desc: 'Root tip stem cells' },
  { id: 'epidermis', label: 'Epidermis', color: '#8bb89f', desc: 'Outer protective layer' },
  { id: 'cortex', label: 'Cortex', color: '#a3c5b0', desc: 'Ground tissue' },
  { id: 'stele', label: 'Stele', color: '#d08955', desc: 'Vascular cylinder' },
];

const KNOWN_ROOT_TFS = [
  'AT5G11260', 'AT2G43010', 'AT1G49720', 'AT2G46830', 'AT1G01060',
  'AT2G36270', 'AT3G20770', 'AT5G61380', 'AT3G24650', 'AT2G25930',
];

function RootCrossSection({ highlights }) {
  const getOpacity = (cellType) => {
    const val = highlights?.[cellType];
    if (val == null) return 0.3;
    return 0.3 + 0.7 * Math.min(val, 1);
  };

  return (
    <svg viewBox="0 0 200 200" className="root-svg">
      <circle cx="100" cy="100" r="90" fill="#f4f7f4" stroke="#c5d4cc" strokeWidth="1" />
      <circle cx="100" cy="100" r="88" fill={CELL_TYPES[1].color} opacity={getOpacity('epidermis')} />
      <circle cx="100" cy="100" r="70" fill={CELL_TYPES[2].color} opacity={getOpacity('cortex')} />
      <circle cx="100" cy="100" r="40" fill="#f4f7f4" stroke="#c5d4cc" strokeWidth="0.5" />
      <circle cx="100" cy="100" r="38" fill={CELL_TYPES[3].color} opacity={getOpacity('stele')} />
      <circle cx="100" cy="100" r="15" fill={CELL_TYPES[0].color} opacity={getOpacity('meristem')} />
      <text x="100" y="103" textAnchor="middle" className="root-layer-label small">meristem</text>
      <text x="100" y="30" textAnchor="middle" className="root-layer-label">stele</text>
      <text x="100" y="58" textAnchor="middle" className="root-layer-label">cortex</text>
      <text x="100" y="175" textAnchor="middle" className="root-layer-label">epidermis</text>
    </svg>
  );
}

function TFHeatmap({ data, selectedTF, onSelect }) {
  if (!data?.length) return <div className="root-empty">No TF activity data loaded.</div>;

  return (
    <div className="root-heatmap">
      <table>
        <thead>
          <tr>
            <th>TF</th>
            {CELL_TYPES.map(ct => <th key={ct.id}>{ct.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map(row => (
            <tr
              key={row.gene_id}
              className={selectedTF === row.gene_id ? 'selected' : ''}
              onClick={() => onSelect(row.gene_id)}
            >
              <td className="root-tf-name">
                <strong>{row.symbol || row.gene_id}</strong>
              </td>
              {CELL_TYPES.map(ct => {
                const val = row.expression?.[ct.id] || 0;
                const maxVal = Math.max(...Object.values(row.expression || {}), 0.001);
                const intensity = val / maxVal;
                return (
                  <td key={ct.id}>
                    <div
                      className="root-heat-cell"
                      style={{ opacity: 0.15 + 0.85 * intensity, backgroundColor: ct.color }}
                      title={`${val.toFixed(2)} TPM`}
                    >
                      {val > 0 ? val.toFixed(1) : '—'}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function RootCelltypeMap() {
  const [tfData, setTfData] = useState(null);
  const [selectedTF, setSelectedTF] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/celltype/arabidopsis/tf-activity?dataset_id=scrna_arabidopsis`
        );
        if (res.ok) {
          const data = await res.json();
          setTfData(data.tfs || data);
        } else {
          const fallback = await fetch(
            `${API_BASE}/api/v1/scrna/arabidopsis/cluster-expression?gene_ids=${KNOWN_ROOT_TFS.join(',')}`
          ).catch(() => null);
          if (fallback?.ok) {
            setTfData(await fallback.json());
          } else {
            setError('Cell-type TF activity endpoint not available. Start the backend with make backend.');
          }
        }
      } catch (e) {
        setError(e.message);
      }
      setLoading(false);
    }
    load();
  }, []);

  const highlights = {};
  if (selectedTF && tfData) {
    const tf = tfData.find(t => t.gene_id === selectedTF);
    if (tf?.expression) {
      const maxVal = Math.max(...Object.values(tf.expression), 0.001);
      CELL_TYPES.forEach(ct => {
        highlights[ct.id] = (tf.expression[ct.id] || 0) / maxVal;
      });
    }
  }

  return (
    <div className="root-celltype-map">
      <header className="root-header">
        <h2>Root cell-type regulatory map</h2>
        <p>
          TF activity painted on an Arabidopsis root cross-section. Select a TF to see
          where it is expressed across the four cell-type zones (Denyer et al. 2019,
          4,727 cells from lateral root primordia).
        </p>
      </header>

      {loading && <div className="root-loading">Loading cell-type data…</div>}
      {error && <div className="root-error">{error}</div>}

      <div className="root-layout">
        <section className="root-diagram-section">
          <h3>Root cross-section</h3>
          <RootCrossSection highlights={highlights} />
          <div className="root-cell-legend">
            {CELL_TYPES.map(ct => (
              <span key={ct.id} className="root-cell-chip" style={{ borderColor: ct.color }}>
                <span className="root-cell-dot" style={{ background: ct.color }} />
                <strong>{ct.label}</strong>
                <small>{ct.desc}</small>
              </span>
            ))}
          </div>
          {selectedTF && (
            <div className="root-selected-tf">
              Showing: <strong>{tfData?.find(t => t.gene_id === selectedTF)?.symbol || selectedTF}</strong>
            </div>
          )}
        </section>

        <section className="root-heatmap-section">
          <h3>TF expression by cell type</h3>
          {tfData && (
            <TFHeatmap data={tfData} selectedTF={selectedTF} onSelect={setSelectedTF} />
          )}
        </section>
      </div>

      <section className="root-edges-section">
        <h3>Cell-type regulatory edges</h3>
        <p>
          The atlas contains <strong>1,192,254</strong> cell-type–specific regulatory edges
          for the Arabidopsis root dataset, linking TFs to targets within each cell zone.
          These edges reflect both global network topology and cell-type–specific expression
          weighting.
        </p>
        <div className="root-boundary">
          <strong>Boundary note:</strong> Cell-type edges are weighted by expression, not
          discovered from single-cell data alone. A TF–target edge present in the global
          network is scored higher in cell types where both genes are expressed. The edge
          does not prove cell-type–specific regulation — it means the regulatory potential
          is higher given the expression context.
        </div>
      </section>
    </div>
  );
}
