import React, { useEffect, useMemo, useState } from 'react';
import { analysisAPI } from '../services/apiService';
import SubgraphGraph from './SubgraphGraph';
import '../styles/FeedbackControlView.css';


const LABELS = {
  arabidopsis: 'Arabidopsis', human: 'Human', mouse: 'Mouse', tomato: 'Tomato',
  petunia: 'Petunia', rice: 'Rice', pepper: 'Pepper', potato: 'Potato',
};

const FAMILY_LABELS = {
  positive_autoregulation: 'Positive autoregulation',
  negative_autoregulation: 'Negative autoregulation',
  mutual_repression: 'Mutual repression',
  mutual_activation: 'Mutual activation',
  repressilator: 'Repressilator',
  positive_feedback: 'Positive feedback',
  negative_feedback: 'Negative feedback',
};

const number = (value) => (value ?? 0).toLocaleString();
const labelSpecies = (species) => LABELS[species] || species;

export default function FeedbackControlView({ initialSpecies = 'arabidopsis', onSpeciesChange, onSelectGene }) {
  const [speciesList, setSpeciesList] = useState([]);
  const [species, setSpecies] = useState(initialSpecies || 'arabidopsis');
  const [minConfidence, setMinConfidence] = useState(0.5);
  const [maxLoopLength, setMaxLoopLength] = useState(6);
  const [result, setResult] = useState(null);
  const [selectedSystemId, setSelectedSystemId] = useState(null);
  const [selectedCoreId, setSelectedCoreId] = useState(null);
  const [selectedCircuitId, setSelectedCircuitId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/v1/stats').then((response) => response.json()).then((stats) => {
      setSpeciesList(stats.species_list || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (initialSpecies && initialSpecies !== species) setSpecies(initialSpecies);
  }, [initialSpecies]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    analysisAPI.feedbackControl(species, { minConfidence, maxLoopLength })
      .then((data) => {
        if (cancelled) return;
        setResult(data);
        setSelectedSystemId(data.systems?.[0]?.system_id || null);
        const firstCore = data.cores?.[0];
        setSelectedCoreId(firstCore?.core_id || null);
        setSelectedCircuitId(firstCore?.circuits?.[0]?.circuit_id || null);
      })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [species, minConfidence, maxLoopLength]);

  const selectedCore = useMemo(
    () => result?.cores?.find((core) => core.core_id === selectedCoreId) || result?.cores?.[0],
    [result, selectedCoreId],
  );
  const selectedSystem = useMemo(
    () => result?.systems?.find((system) => system.system_id === selectedSystemId) || result?.systems?.[0],
    [result, selectedSystemId],
  );
  const selectedCircuit = useMemo(
    () => selectedCore?.circuits?.find((circuit) => circuit.circuit_id === selectedCircuitId)
      || selectedCore?.circuits?.[0],
    [selectedCore, selectedCircuitId],
  );
  const maxCoreNodes = Math.max(1, ...(result?.cores || []).map((core) => core.node_count));

  const chooseCore = (core) => {
    setSelectedCoreId(core.core_id);
    setSelectedCircuitId(core.circuits?.[0]?.circuit_id || null);
  };

  return (
    <div className="feedback-view">
      <header className="feedback-header">
        <div>
          <div className="feedback-kicker">BIOLOGICAL CONTROL DISCOVERY</div>
          <h1>Biological control systems</h1>
          <p>Find signed feedback, assemble it into biologically coherent systems, and distinguish supported mechanisms from incomplete hypotheses.</p>
        </div>
        <div className="feedback-controls">
          <label>
            <span>Species</span>
            <select value={species} onChange={(event) => {
              setSpecies(event.target.value);
              onSpeciesChange?.(event.target.value);
            }}>
              {speciesList.map((item) => <option key={item} value={item}>{labelSpecies(item)}</option>)}
            </select>
          </label>
          <label>
            <span>Evidence floor</span>
            <select value={minConfidence} onChange={(event) => setMinConfidence(Number(event.target.value))}>
              <option value={0.5}>Confidence ≥ 0.50</option>
              <option value={0.7}>Confidence ≥ 0.70</option>
              <option value={0.9}>Confidence ≥ 0.90</option>
            </select>
          </label>
          <label>
            <span>Longest loop</span>
            <select value={maxLoopLength} onChange={(event) => setMaxLoopLength(Number(event.target.value))}>
              {[3, 4, 5, 6, 8, 10].map((length) => <option key={length} value={length}>{length} genes</option>)}
            </select>
          </label>
        </div>
      </header>

      {loading && <div className="feedback-notice">Analyzing signed feedback cores…</div>}
      {error && <div className="feedback-notice error">{error}</div>}

      {result && !loading && (
        <>
          <section className="feedback-summary">
            <div><strong>{number(result.graph?.edges)}</strong><span>signed edges analyzed</span></div>
            <div><strong>{number(result.summary?.biological_systems)}</strong><span>candidate control systems</span></div>
            <div><strong>{number(result.summary?.feedback_cores)}</strong><span>feedback cores</span></div>
            <div><strong>{number(result.summary?.feedback_genes)}</strong><span>genes inside feedback</span></div>
            <div><strong>{number(result.summary?.circuits_returned)}</strong><span>representative circuits</span></div>
            <div className="feedback-run-state">
              <strong>{result.storage?.status === 'cached' ? 'REUSED' : 'STORED'}</strong>
              <span>versioned analysis</span>
            </div>
          </section>

          {(result.truncation?.search || result.truncation?.circuits || result.truncation?.cores) && (
            <div className="feedback-boundary">
              This is a bounded representative analysis. Feedback cores are complete for the filtered graph;
              longer circuit enumeration or controller search was truncated where reported.
            </div>
          )}

          {result.systems?.length ? (
            <section className="control-systems-workspace">
              <aside className="control-system-index">
                <div className="feedback-section-title">
                  <span>Discovered systems</span><small>biology + signed topology + context</small>
                </div>
                <div className="control-system-list">
                  {result.systems.map((system) => (
                    <button key={system.system_id}
                      className={system.system_id === selectedSystem?.system_id ? 'active' : ''}
                      onClick={() => setSelectedSystemId(system.system_id)}>
                      <span className="feedback-core-rank">{String(system.rank).padStart(2, '0')}</span>
                      <span className="control-system-copy">
                        <strong>{system.name}</strong>
                        <small>{system.architecture_label}</small>
                      </span>
                      <span className={`system-mode ${system.discovery_mode}`}>{system.discovery_mode === 'annotation_supported' ? 'KNOWN' : 'DE NOVO'}</span>
                    </button>
                  ))}
                </div>
              </aside>

              <div className="control-system-detail">
                <div className="control-system-heading">
                  <div>
                    <span className="feedback-kicker">SYSTEM {selectedSystem?.rank}</span>
                    <h2>{selectedSystem?.name}</h2>
                    <p>{selectedSystem?.architecture_label}</p>
                  </div>
                  <div className="control-system-score">
                    <strong>{selectedSystem?.score?.toFixed(2)}</strong>
                    <span>{selectedSystem?.confidence_label} evidence</span>
                  </div>
                </div>

                <div className="system-status-row">
                  <span className={`system-completeness ${selectedSystem?.completeness}`}>
                    {selectedSystem?.completeness === 'partial_architecture' ? 'PARTIAL ARCHITECTURE' : 'CLOSED FEEDBACK FOUND'}
                  </span>
                  <span>{number(selectedSystem?.gene_count)} genes</span>
                  <span>{number(selectedSystem?.edge_count)} signed edges</span>
                  <span>{number(selectedSystem?.feedback_gene_count)} genes in retained loops</span>
                </div>

                <div className="system-evidence-grid">
                  <div><strong>{number(selectedSystem?.context_support?.cis_supported_edges)}</strong><span>cis-supported edges</span></div>
                  <div><strong>{number(selectedSystem?.context_support?.perturbation_supported_edges)}</strong><span>perturbation-supported</span></div>
                  <div><strong>{number(selectedSystem?.context_support?.coexpressed_edges)}</strong><span>context-coexpressed</span></div>
                  <div><strong>{number(selectedSystem?.context_support?.conservation?.conserved_signed_edges)}</strong><span>sign-conserved edges</span></div>
                  <div><strong>{selectedSystem?.annotation?.enrichment?.fold?.toFixed?.(1) || '—'}×</strong><span>feedback enrichment</span></div>
                </div>

                <div className="system-rationale">
                  {(selectedSystem?.classification_reasons || []).map((reason) => <span key={reason}>{reason}</span>)}
                  {(selectedSystem?.context_support?.top_tissues || []).slice(0, 3).map((tissue) => (
                    <span key={tissue.tissue}>{tissue.tissue}: {tissue.supported_edges} edges</span>
                  ))}
                </div>

                <SubgraphGraph nodes={selectedSystem?.genes || []} edges={selectedSystem?.edges || []}
                  tfStyle="circle" onNodeClick={(gene) => onSelectGene?.(gene.symbol)} />

                <div className="system-boundary">
                  <strong>Interpretation boundary</strong>
                  <span>{selectedSystem?.evidence_boundary}</span>
                  {selectedSystem?.completeness === 'partial_architecture' && (
                    <span>Some regulatory arms required for the proposed behavior are absent from the filtered atlas.</span>
                  )}
                </div>
              </div>
            </section>
          ) : (
            <div className="feedback-boundary">No biological system passed the annotation and signed-feedback criteria.</div>
          )}

          {result.cores?.length ? (
            <>
            <div className="structural-heading">
              <span>Structural analysis</span>
              <h2>Feedback cores and representative circuits</h2>
              <p>The systems above interpret these topology-first results. Inspect the underlying cores and loops here.</p>
            </div>
            <main className="feedback-workspace">
              <aside className="feedback-core-index">
                <div className="feedback-section-title">
                  <span>Regulatory cores</span><small>ranked by evidence and connectivity</small>
                </div>
                <div className="feedback-core-list">
                  {result.cores.map((core) => (
                    <button key={core.core_id} className={core.core_id === selectedCore?.core_id ? 'active' : ''}
                      onClick={() => chooseCore(core)}>
                      <span className="feedback-core-rank">{String(core.rank).padStart(2, '0')}</span>
                      <span className="feedback-core-copy">
                        <strong>{number(core.node_count)} genes · {number(core.edge_count)} edges</strong>
                        <span className="feedback-core-bar"><i style={{ width: `${Math.max(5, core.node_count / maxCoreNodes * 100)}%` }} /></span>
                      </span>
                      <span className="feedback-core-score">{core.score.toFixed(2)}</span>
                    </button>
                  ))}
                </div>
              </aside>

              <section className="feedback-detail">
                <div className="feedback-core-heading">
                  <div>
                    <span>CORE {selectedCore?.rank}</span>
                    <h2>{number(selectedCore?.node_count)} genes in a closed regulatory region</h2>
                  </div>
                  <div className="feedback-core-metrics">
                    <span><b>{number(selectedCore?.edge_count)}</b> internal edges</span>
                    <span><b>{selectedCore?.mean_edge_confidence?.toFixed(2)}</b> mean confidence</span>
                    <span><b>{selectedCore?.circuit_search?.search_states?.toLocaleString()}</b> search states</span>
                  </div>
                </div>

                <div className="feedback-controller-strip">
                  <div>
                    <strong>Candidate control points</strong>
                    <span>{selectedCore?.controller_analysis?.exact ? 'exact minimum set' : 'bounded greedy approximation'}</span>
                  </div>
                  <div className="feedback-controller-pills">
                    {(selectedCore?.controller_analysis?.controllers || []).slice(0, 14).map((gene) => (
                      <button key={gene.id} onClick={() => onSelectGene?.(gene.symbol)}>{gene.symbol}</button>
                    ))}
                    {(selectedCore?.controller_analysis?.controllers?.length || 0) > 14 && (
                      <span>+{selectedCore.controller_analysis.controllers.length - 14} more</span>
                    )}
                  </div>
                </div>

                <div className="feedback-circuit-area">
                  <div className="feedback-circuit-list">
                    <div className="feedback-section-title">
                      <span>Representative circuits</span>
                      <small>{selectedCore?.circuit_search?.truncated ? 'bounded sample' : 'complete at this bound'}</small>
                    </div>
                    {(selectedCore?.circuits || []).map((circuit) => (
                      <button key={circuit.circuit_id}
                        className={circuit.circuit_id === selectedCircuit?.circuit_id ? 'active' : ''}
                        onClick={() => setSelectedCircuitId(circuit.circuit_id)}>
                        <span className={`feedback-polarity ${circuit.polarity}`} />
                        <span>
                          <strong>{FAMILY_LABELS[circuit.family] || circuit.family}</strong>
                          <small>{circuit.genes.map((gene) => gene.symbol).join(' → ')}</small>
                        </span>
                        <b>{circuit.score.toFixed(2)}</b>
                      </button>
                    ))}
                  </div>

                  <div className="feedback-circuit-visual">
                    {selectedCircuit ? (
                      <>
                        <div className="feedback-circuit-caption">
                          <div>
                            <span className={`feedback-badge ${selectedCircuit.confidence_label}`}>{selectedCircuit.confidence_label}</span>
                            <h3>{FAMILY_LABELS[selectedCircuit.family] || selectedCircuit.family}</h3>
                            <p>{selectedCircuit.behavior_hypothesis}</p>
                          </div>
                          <div className="feedback-circuit-score">
                            <strong>{selectedCircuit.score.toFixed(2)}</strong><span>circuit score</span>
                          </div>
                        </div>
                        <SubgraphGraph nodes={selectedCircuit.genes} edges={selectedCircuit.edges}
                          tfStyle="circle" onNodeClick={(gene) => onSelectGene?.(gene.symbol)} />
                        <div className="feedback-legend">
                          <span><i className="activation" /> activation</span>
                          <span><i className="repression" /> repression</span>
                          <span>Score is limited by the weakest edge.</span>
                        </div>
                      </>
                    ) : <div className="feedback-notice">No representative circuit was retained for this core.</div>}
                  </div>
                </div>
              </section>
            </main>
            </>
          ) : (
            <div className="feedback-empty">
              <strong>No signed feedback passed this evidence setting.</strong>
              <span>Lower the confidence floor or choose a species with stronger signed-edge coverage.</span>
            </div>
          )}

          <footer className="feedback-footer">{result.evidence_boundary}</footer>
        </>
      )}
    </div>
  );
}
