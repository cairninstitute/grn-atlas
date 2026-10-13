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
  const [selectedGroupId, setSelectedGroupId] = useState(null);
  const [coreView, setCoreView] = useState('backbone');
  const [backbone, setBackbone] = useState(null);
  const [backboneLoading, setBackboneLoading] = useState(false);
  const [cycleResult, setCycleResult] = useState(null);
  const [cycleLoading, setCycleLoading] = useState(false);
  const [cyclePolarity, setCyclePolarity] = useState('');
  const [cycleMaxLength, setCycleMaxLength] = useState(6);
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
        setSelectedGroupId(data.core_groups?.[0]?.group_id || null);
        setBackbone(null);
        setCycleResult(null);
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
  const selectedGroup = useMemo(
    () => result?.core_groups?.find((group) => group.group_id === selectedGroupId)
      || result?.core_groups?.[0],
    [result, selectedGroupId],
  );
  const selectedCoverCircuit = useMemo(
    () => selectedCore?.cycle_cover?.circuits?.find((circuit) => circuit.circuit_id === selectedCircuitId)
      || selectedCore?.cycle_cover?.circuits?.[0],
    [selectedCore, selectedCircuitId],
  );
  const selectedQueriedCircuit = useMemo(
    () => cycleResult?.cycles?.find((circuit) => circuit.circuit_id === selectedCircuitId)
      || cycleResult?.cycles?.[0],
    [cycleResult, selectedCircuitId],
  );
  const maxCoreNodes = Math.max(1, ...(result?.cores || []).map((core) => core.node_count));

  const groupRelationships = useMemo(() => {
    const ids = new Set(selectedGroup?.relationship_ids || []);
    return (result?.core_relationships || []).filter((row) => ids.has(row.relationship_id));
  }, [result, selectedGroup]);
  const groupGraph = useMemo(() => ({
    nodes: (selectedGroup?.cores || []).map((core) => ({
      id: core.core_id,
      symbol: `CORE ${core.rank}`,
      name: `${core.node_count} genes; ${(core.top_genes || []).map((gene) => gene.symbol).join(', ')}`,
      is_tf: true,
    })),
    edges: groupRelationships.map((row) => ({
      source: row.source_core_id,
      target: row.target_core_id,
      regulation_type: row.net_sign,
      confidence: row.score,
    })),
  }), [selectedGroup, groupRelationships]);

  useEffect(() => {
    if (!result?.run_id || !selectedCore?.core_id || coreView !== 'backbone') return;
    let cancelled = false;
    setBackboneLoading(true);
    analysisAPI.feedbackBackbone(result.run_id, selectedCore.core_id)
      .then((data) => { if (!cancelled) setBackbone(data); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setBackboneLoading(false); });
    return () => { cancelled = true; };
  }, [result?.run_id, selectedCore?.core_id, coreView]);

  const chooseCore = (core) => {
    setSelectedCoreId(core.core_id);
    setSelectedCircuitId(core.circuits?.[0]?.circuit_id || null);
    setBackbone(null);
    setCycleResult(null);
  };

  const loadCycles = (cursor = 0, append = false) => {
    if (!result?.run_id || !selectedCore?.core_id) return;
    setCycleLoading(true);
    analysisAPI.feedbackCycles(result.run_id, selectedCore.core_id, {
      cursor, polarity: cyclePolarity || null, maxLength: cycleMaxLength, limit: 50,
    }).then((data) => {
      setCycleResult((previous) => append && previous ? {
        ...data,
        cycles: [...previous.cycles, ...data.cycles],
      } : data);
      if (!append) setSelectedCircuitId(data.cycles?.[0]?.circuit_id || null);
    }).catch((err) => setError(err.message)).finally(() => setCycleLoading(false));
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
            <div><strong>{number(result.summary?.biological_systems)}</strong><span>candidate control systems</span></div>
            <div><strong>{number(result.summary?.feedback_cores)}</strong><span>feedback cores</span></div>
            <div><strong>{number(result.summary?.core_groups)}</strong><span>linked core groups</span></div>
            <div><strong>{number(result.summary?.feedback_edges)}</strong><span>feedback-capable edges</span></div>
            <div><strong>{number(result.summary?.feedback_genes)}</strong><span>genes inside feedback</span></div>
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

          {result.core_groups?.length > 0 && (
            <section className="core-groups-workspace">
              <div className="structural-heading">
                <span>Higher-order control architecture</span>
                <h2>Connected groups of feedback cores</h2>
                <p>Short signed regulatory paths chain independently closed cores without merging them into one feedback component.</p>
              </div>
              <div className="core-groups-layout">
                <aside className="core-group-list">
                  {result.core_groups.map((group) => (
                    <button key={group.group_id}
                      className={group.group_id === selectedGroup?.group_id ? 'active' : ''}
                      onClick={() => setSelectedGroupId(group.group_id)}>
                      <strong>Group {group.rank}</strong>
                      <span>{group.core_count} cores · {group.relationship_count} relationships</span>
                      <small>{group.gene_count} feedback genes · {group.bridge_gene_count} bridge genes</small>
                    </button>
                  ))}
                </aside>
                <div className="core-group-detail">
                  <div className="core-group-metrics">
                    <strong>Group {selectedGroup?.rank}</strong>
                    <span>{selectedGroup?.core_count} cores connected by measured signed paths</span>
                    <b>{selectedGroup?.score?.toFixed(2)}</b>
                  </div>
                  <SubgraphGraph nodes={groupGraph.nodes} edges={groupGraph.edges} tfStyle="circle" />
                  <div className="core-relationship-list">
                    {groupRelationships.map((row) => (
                      <div key={row.relationship_id}>
                        <strong>Core {row.source_core_rank} → Core {row.target_core_rank}</strong>
                        <span>{row.path_genes.map((gene) => gene.symbol).join(' → ')}</span>
                        <small>{row.relationship_type.replaceAll('_', ' ')} · {row.net_sign} · {row.score.toFixed(2)}</small>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>
          )}

          {result.cores?.length ? (
            <>
            <div className="structural-heading">
              <span>Structural analysis</span>
              <h2>Complete feedback backbones and cycles</h2>
              <p>Every internal core edge is cycle-capable. Inspect the full backbone, a compact edge-covering cycle set, or enumerate individual loops.</p>
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

                <div className="feedback-layer-tabs">
                  <button className={coreView === 'backbone' ? 'active' : ''} onClick={() => setCoreView('backbone')}>
                    Complete backbone
                  </button>
                  <button className={coreView === 'cover' ? 'active' : ''} onClick={() => {
                    setCoreView('cover');
                    setSelectedCircuitId(selectedCore?.cycle_cover?.circuits?.[0]?.circuit_id || null);
                  }}>
                    Compact cycle cover
                  </button>
                  <button className={coreView === 'cycles' ? 'active' : ''} onClick={() => setCoreView('cycles')}>
                    Cycle explorer
                  </button>
                </div>

                {coreView === 'backbone' && (
                  <div className="feedback-backbone-view">
                    <div className="feedback-backbone-caption">
                      <div>
                        <strong>Complete cycle-capable backbone</strong>
                        <span>All {number(selectedCore?.backbone?.cycle_capable_nodes)} genes and {number(selectedCore?.backbone?.cycle_capable_edges)} internal edges belong to at least one directed cycle.</span>
                      </div>
                      <b>COMPLETE</b>
                    </div>
                    {backboneLoading && <div className="feedback-notice">Loading complete backbone…</div>}
                    {backbone && !backboneLoading && (
                      <>
                        <SubgraphGraph nodes={backbone.nodes} edges={backbone.edges}
                          tfStyle="circle" onNodeClick={(gene) => onSelectGene?.(gene.symbol)} />
                        {!backbone.complete && (
                          <div className="feedback-boundary">The graph shows the first {number(backbone.edges.length)} of {number(backbone.edge_count)} indexed edges.</div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {coreView === 'cover' && (
                  <div className="feedback-circuit-area">
                    <div className="feedback-circuit-list">
                      <div className="feedback-section-title">
                        <span>Edge-covering cycles</span>
                        <small>{Math.round((selectedCore?.cycle_cover?.coverage || 0) * 100)}% of backbone edges covered</small>
                      </div>
                      {(selectedCore?.cycle_cover?.circuits || []).map((circuit) => (
                        <button key={circuit.circuit_id}
                          className={circuit.circuit_id === selectedCoverCircuit?.circuit_id ? 'active' : ''}
                          onClick={() => setSelectedCircuitId(circuit.circuit_id)}>
                          <span className={`feedback-polarity ${circuit.polarity}`} />
                          <span><strong>{FAMILY_LABELS[circuit.family] || circuit.family}</strong>
                            <small>{circuit.genes.map((gene) => gene.symbol).join(' → ')}</small></span>
                          <b>{circuit.score.toFixed(2)}</b>
                        </button>
                      ))}
                    </div>
                    <div className="feedback-circuit-visual">
                      {selectedCoverCircuit ? (
                        <>
                          <div className="feedback-circuit-caption">
                            <div><span className={`feedback-badge ${selectedCoverCircuit.confidence_label}`}>{selectedCoverCircuit.confidence_label}</span>
                              <h3>{FAMILY_LABELS[selectedCoverCircuit.family] || selectedCoverCircuit.family}</h3>
                              <p>Shortest witness cycle selected to cover the feedback backbone.</p></div>
                          </div>
                          <SubgraphGraph nodes={selectedCoverCircuit.genes} edges={selectedCoverCircuit.edges}
                            tfStyle="circle" onNodeClick={(gene) => onSelectGene?.(gene.symbol)} />
                        </>
                      ) : <div className="feedback-notice">Cycle-cover witnesses were not materialized for this large core.</div>}
                    </div>
                  </div>
                )}

                {coreView === 'cycles' && (
                  <div className="feedback-cycle-explorer">
                    <div className="cycle-query-controls">
                      <label><span>Polarity</span><select value={cyclePolarity} onChange={(event) => setCyclePolarity(event.target.value)}>
                        <option value="">Positive and negative</option><option value="positive">Positive</option><option value="negative">Negative</option>
                      </select></label>
                      <label><span>Maximum length</span><select value={cycleMaxLength} onChange={(event) => setCycleMaxLength(Number(event.target.value))}>
                        {[3, 4, 5, 6, 8, 10, 20].map((length) => <option key={length} value={length}>{length} genes</option>)}
                      </select></label>
                      <button onClick={() => loadCycles(0, false)} disabled={cycleLoading}>{cycleLoading ? 'Searching…' : 'Find cycles'}</button>
                      <span>{selectedCore?.cycle_catalog?.exact ? `${number(selectedCore.cycle_catalog.cataloged_cycles)} cycles cataloged exactly` : 'resumable on-demand enumeration'}</span>
                    </div>
                    {cycleResult && (
                      <div className="feedback-circuit-area">
                        <div className="feedback-circuit-list">
                          <div className="feedback-section-title"><span>Matching cycles</span><small>{cycleResult.mode.replaceAll('_', ' ')}</small></div>
                          {cycleResult.cycles.map((circuit) => (
                            <button key={circuit.circuit_id}
                              className={circuit.circuit_id === selectedQueriedCircuit?.circuit_id ? 'active' : ''}
                              onClick={() => setSelectedCircuitId(circuit.circuit_id)}>
                              <span className={`feedback-polarity ${circuit.polarity}`} />
                              <span><strong>{FAMILY_LABELS[circuit.family] || circuit.family}</strong>
                                <small>{circuit.genes.map((gene) => gene.symbol).join(' → ')}</small></span>
                              <b>{circuit.length}</b>
                            </button>
                          ))}
                          {cycleResult.next_cursor != null && <button className="load-more-cycles" onClick={() => loadCycles(cycleResult.next_cursor, true)}>Continue enumeration</button>}
                        </div>
                        <div className="feedback-circuit-visual">
                          {selectedQueriedCircuit ? <SubgraphGraph nodes={selectedQueriedCircuit.genes} edges={selectedQueriedCircuit.edges}
                            tfStyle="circle" onNodeClick={(gene) => onSelectGene?.(gene.symbol)} />
                            : <div className="feedback-notice">No cycle matches the current filters.</div>}
                        </div>
                      </div>
                    )}
                  </div>
                )}
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
