import React, { useCallback, useEffect, useMemo, useState } from 'react';
import '../../styles/EvidenceTierSlider.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const SPECIES = ['arabidopsis', 'human', 'mouse', 'tomato', 'petunia', 'rice', 'pepper', 'potato'];
const LABELS = {
  arabidopsis: 'Arabidopsis', human: 'Human', mouse: 'Mouse', tomato: 'Tomato',
  petunia: 'Petunia', rice: 'Rice', pepper: 'Pepper', potato: 'Potato',
};

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function RunCard({ run, isSelected, onClick }) {
  return (
    <button
      className={`evidence-run-card${isSelected ? ' selected' : ''}`}
      onClick={onClick}
      title={`Run ${run.run_id.slice(0, 8)} — ${run.generated_at}`}
    >
      <div className="evidence-run-date">{formatDate(run.generated_at)}</div>
      <div className="evidence-run-stats">
        <span className="evidence-run-cores">{run.cores} cores</span>
        <span className="evidence-run-nodes">{run.total_nodes} genes</span>
        <span className="evidence-run-edges">{run.total_edges} edges</span>
      </div>
      <div className="evidence-run-hash" title={run.graph_hash}>
        {run.graph_hash?.slice(0, 8)}
      </div>
    </button>
  );
}

function ComparisonBar({ label, before, after }) {
  const max = Math.max(before || 0, after || 0, 1);
  const bPct = ((before || 0) / max) * 100;
  const aPct = ((after || 0) / max) * 100;
  const delta = (after || 0) - (before || 0);
  const sign = delta > 0 ? '+' : '';
  return (
    <div className="evidence-comparison-row">
      <div className="evidence-comparison-label">{label}</div>
      <div className="evidence-comparison-bars">
        <div className="evidence-bar before" style={{ width: `${bPct}%` }}>
          <span>{before?.toLocaleString() ?? '—'}</span>
        </div>
        <div className="evidence-bar after" style={{ width: `${aPct}%` }}>
          <span>{after?.toLocaleString() ?? '—'}</span>
        </div>
      </div>
      <div className={`evidence-comparison-delta ${delta > 0 ? 'up' : delta < 0 ? 'down' : ''}`}>
        {delta !== 0 ? `${sign}${delta.toLocaleString()}` : '—'}
      </div>
    </div>
  );
}

export default function EvidenceTierSlider() {
  const [species, setSpecies] = useState('arabidopsis');
  const [timeline, setTimeline] = useState(null);
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [compareIdx, setCompareIdx] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchTimeline = useCallback(async (sp) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/network/feedback-control/${sp}/timeline`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTimeline(data.runs || []);
      if (data.runs?.length > 0) {
        setSelectedIdx(data.runs.length - 1);
        setCompareIdx(data.runs.length > 1 ? data.runs.length - 2 : null);
      }
    } catch (e) {
      setError(e.message);
      setTimeline(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTimeline(species); }, [species, fetchTimeline]);

  const selected = timeline?.[selectedIdx];
  const compared = compareIdx != null ? timeline?.[compareIdx] : null;

  const distinctHashes = useMemo(() => {
    if (!timeline) return [];
    const seen = new Set();
    return timeline.filter((r) => {
      if (seen.has(r.graph_hash)) return false;
      seen.add(r.graph_hash);
      return true;
    });
  }, [timeline]);

  return (
    <div className="evidence-tier-slider">
      <header className="evidence-tier-header">
        <h2>Evidence-Tier Slider</h2>
        <p>
          Watch the feedback core grow and merge as each evidence source is switched on.
          Each point is a feedback analysis run under a different graph state.
        </p>
        <div className="evidence-tier-species">
          {SPECIES.map((sp) => (
            <button
              key={sp}
              className={sp === species ? 'active' : ''}
              onClick={() => setSpecies(sp)}
            >
              {LABELS[sp]}
            </button>
          ))}
        </div>
      </header>

      {loading && <div className="evidence-loading">Loading timeline…</div>}
      {error && <div className="evidence-error">{error}</div>}

      {timeline && timeline.length > 0 && (
        <>
          <div className="evidence-timeline">
            <div className="evidence-timeline-track">
              {timeline.map((run, i) => (
                <RunCard
                  key={run.run_id}
                  run={run}
                  isSelected={i === selectedIdx}
                  onClick={() => {
                    if (selectedIdx !== null && i !== selectedIdx) {
                      setCompareIdx(selectedIdx);
                    }
                    setSelectedIdx(i);
                  }}
                />
              ))}
            </div>
            <input
              type="range"
              min={0}
              max={timeline.length - 1}
              value={selectedIdx ?? 0}
              onChange={(e) => {
                const idx = Number(e.target.value);
                if (selectedIdx !== null) setCompareIdx(selectedIdx);
                setSelectedIdx(idx);
              }}
              className="evidence-slider"
            />
          </div>

          <div className="evidence-detail">
            {selected && (
              <div className="evidence-selected">
                <h3>Selected: {formatDate(selected.generated_at)}</h3>
                <div className="evidence-metric-grid">
                  <div className="evidence-metric">
                    <span className="evidence-metric-value">{selected.cores}</span>
                    <span className="evidence-metric-label">Feedback cores</span>
                  </div>
                  <div className="evidence-metric">
                    <span className="evidence-metric-value">{selected.total_nodes.toLocaleString()}</span>
                    <span className="evidence-metric-label">Genes in cores</span>
                  </div>
                  <div className="evidence-metric">
                    <span className="evidence-metric-value">{selected.total_edges.toLocaleString()}</span>
                    <span className="evidence-metric-label">Edges in cores</span>
                  </div>
                  <div className="evidence-metric">
                    <span className="evidence-metric-value">{selected.largest_core_nodes}</span>
                    <span className="evidence-metric-label">Largest core</span>
                  </div>
                </div>
                <div className="evidence-graph-hash">
                  Graph: <code>{selected.graph_hash}</code>
                </div>
              </div>
            )}

            {selected && compared && selected.run_id !== compared.run_id && (
              <div className="evidence-comparison">
                <h3>
                  Comparison: {formatDate(compared.generated_at)} → {formatDate(selected.generated_at)}
                </h3>
                <ComparisonBar label="Cores" before={compared.cores} after={selected.cores} />
                <ComparisonBar label="Genes" before={compared.total_nodes} after={selected.total_nodes} />
                <ComparisonBar label="Edges" before={compared.total_edges} after={selected.total_edges} />
                <ComparisonBar label="Largest core" before={compared.largest_core_nodes} after={selected.largest_core_nodes} />
                {compared.graph_hash !== selected.graph_hash && (
                  <div className="evidence-hash-change">
                    Graph changed: <code>{compared.graph_hash?.slice(0, 8)}</code> → <code>{selected.graph_hash?.slice(0, 8)}</code>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="evidence-distinct-states">
            <h3>{distinctHashes.length} distinct graph states</h3>
            <div className="evidence-state-chips">
              {distinctHashes.map((r) => (
                <span key={r.graph_hash} className="evidence-state-chip" title={r.generated_at}>
                  {r.graph_hash?.slice(0, 8)} · {r.cores} cores · {r.total_nodes} genes
                </span>
              ))}
            </div>
          </div>
        </>
      )}

      {timeline && timeline.length === 0 && (
        <div className="evidence-empty">
          No feedback analysis runs found for {LABELS[species]}.
          Run <code>grn-feedback-control</code> first.
        </div>
      )}
    </div>
  );
}
