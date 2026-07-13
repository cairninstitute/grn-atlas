import React, { useState, useEffect } from 'react';
import { analysisAPI, geneAPI } from '../services/apiService';
import GeneSearchInput from './GeneSearchInput';
import '../styles/GeneSetPanel.css';

// Transcript off-target map: shows the off-target density along the target transcript
// and highlights the chosen (clean) dsRNA window.
function TranscriptMap({ design }) {
  const prof = design.offtarget_profile;
  if (!prof || !design.transcript_length) return null;
  const W = 460, H = 46, n = prof.length;
  const max = Math.max(1, ...prof);
  const bw = W / n;
  const L = design.transcript_length;
  const wx = (design.start / L) * W;
  const ww = Math.max(2, ((design.end - design.start) / L) * W);
  return (
    <div className="txmap-wrap">
      <svg width={W} height={H} role="img" aria-label="off-target density along transcript">
        <rect className="txmap-track" x={0} y={H - 14} width={W} height={10} rx={2} />
        {prof.map((v, i) => v > 0 && (
          <rect key={i} className="txmap-bar" x={i * bw} y={(H - 18) * (1 - v / max)}
            width={Math.max(1, bw - 0.5)} height={(H - 18) * (v / max)} />
        ))}
        <rect className="txmap-win" x={wx} y={0} width={ww} height={H - 2} rx={2} />
      </svg>
      <div className="txmap-legend">
        Bars = off-target density along the {L} bp transcript; shaded band = the chosen
        dsRNA window ({design.start}–{design.end} bp), placed where off-targets are fewest.
      </div>
    </div>
  );
}

const EXAMPLES = {
  petunia: ['AN2', 'DFR', 'JAF13'],
  tomato: ['DFR', 'CHS'],
  arabidopsis: ['TT4', 'PAP1', 'AG'],
  dahlia: [],
};

// Resolve a typed token (gene symbol OR locus id) to a gene id for a species.
async function resolveGene(token, species) {
  const d = await geneAPI.search(token, 1, species);
  return d.results && d.results[0] ? d.results[0] : null;
}

// gene label with an inferred-ortholog marker (° = not a native symbol)
function GLabel({ symbol, inferred }) {
  return <>{symbol}{inferred && <span className="gs-ns" title="inferred from ortholog — not a native symbol">°</span>}</>;
}

// tiny per-transcript hit-density sparkline (where the dsRNA hits this off-target)
function SiteTrack({ profile, length }) {
  if (!profile || !profile.length) return null;
  const W = 90, H = 12, n = profile.length, max = Math.max(1, ...profile), bw = W / n;
  return (
    <svg width={W} height={H} role="img" aria-label={`hits across ${length} bp`}>
      <rect x={0} y={H - 3} width={W} height={2} fill="var(--surface-2,#eee)" />
      {profile.map((v, i) => v > 0 && (
        <rect key={i} x={i * bw} y={(H - 3) * (1 - v / max)} width={Math.max(1, bw - 0.4)}
          height={(H - 3) * (v / max)} fill="var(--warning-dark,#c63)" />
      ))}
    </svg>
  );
}

function gcPercent(s) {
  if (!s) return null;
  const u = s.toUpperCase();
  const gc = (u.match(/[GC]/g) || []).length;
  return Math.round((gc / u.length) * 100);
}

function downloadFasta(seq, name) {
  const header = `>${name || 'dsRNA'} designed_by=GRN_Atlas`;
  const blob = new Blob([`${header}\n${seq}\n`], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${(name || 'dsRNA').replace(/[^\w.-]/g, '_')}_dsRNA.fasta`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function Verdict({ offCount }) {
  if (offCount === 0) return <span className="gs-cons-yes">✓ Fully specific (no off-targets)</span>;
  return <span className="gs-cons-no">⚠ predicted to also hit {offCount} other gene{offCount === 1 ? '' : 's'}</span>;
}

// dsRNA / RNAi design + off-target analysis. Everything is PREDICTED silencing
// (siRNA k-mer matching), not a guarantee of knockdown.
export default function DsRnaPanel({ open, onClose, initialTarget, initialSpecies }) {
  const [seq, setSeq] = useState('');
  const [target, setTarget] = useState('');
  const [species, setSpecies] = useState('petunia');
  const [setText, setSetText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [res, setRes] = useState(null);
  const [screen, setScreen] = useState(null);
  const [copied, setCopied] = useState(false);

  // Prefill when launched from a specific gene ("Design dsRNA for this gene").
  useEffect(() => {
    if (open && initialTarget) {
      setSpecies(initialSpecies || 'petunia');
      setTarget(initialTarget);
      setSeq(''); setRes(null); setScreen(null); setError(null);
    }
  }, [open, initialTarget, initialSpecies]);

  if (!open) return null;

  const run = async () => {
    if (!seq.trim() && !target.trim()) { setError('Enter a target gene (name or id), or paste a dsRNA sequence.'); return; }
    setLoading(true); setError(null); setRes(null); setCopied(false);
    try {
      let targetId = null;
      if (target.trim()) {
        const g = await resolveGene(target.trim(), species);
        if (!g) { setError(`No ${species} gene matching "${target.trim()}".`); setLoading(false); return; }
        targetId = g.id;
      }
      const r = await analysisAPI.dsrna({ sequence: seq.trim() || null, targetGeneId: targetId, species });
      if (r.available === false) setError(r.note || 'No transcript store for this species.');
      else setRes(r);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };

  const runScreen = async () => {
    const tokens = setText.split(/[\s,]+/).map((t) => t.trim()).filter(Boolean);
    if (!tokens.length) { setError('Enter gene names or ids to screen.'); return; }
    setLoading(true); setError(null); setScreen(null);
    try {
      const resolved = await Promise.all(tokens.map((t) => resolveGene(t, species)));
      const ids = resolved.filter(Boolean).map((g) => g.id);
      if (!ids.length) { setError('Could not resolve those genes.'); setLoading(false); return; }
      const r = await analysisAPI.dsrnaScreen(ids, species);
      if (r.available === false) setError(r.note); else setScreen(r);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };

  const copySeq = () => {
    if (res?.design?.sequence) {
      navigator.clipboard.writeText(res.design.sequence);
      setCopied(true); setTimeout(() => setCopied(false), 1500);
    }
  };

  const pe = res?.predicted_effect;
  const examples = EXAMPLES[species] || [];
  return (
    <div className="gs-overlay" onClick={onClose}>
      <div className="gs-modal" onClick={(e) => e.stopPropagation()}>
        <div className="gs-header">
          <h2>Design a dsRNA (RNAi)</h2>
          <button className="gs-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <p className="gs-hint">
          Pick a <strong>target gene</strong> (by name or id) to design the most specific
          dsRNA, or paste a dsRNA to check what it would silence. Predicted from siRNA
          k-mer matches — a specificity guide, not a guarantee of knockdown.
        </p>

        <div className="gs-cons-controls">
          <label className="gs-label">Species</label>
          <select value={species} onChange={(e) => setSpecies(e.target.value)}>
            <option value="petunia">petunia</option>
            <option value="tomato">tomato</option>
            <option value="arabidopsis">arabidopsis</option>
            <option value="dahlia">dahlia</option>
          </select>
          <GeneSearchInput species={species} value={target} onChange={setTarget}
            placeholder="target gene — type a name (e.g. AN2)" style={{ flex: 1 }} />
        </div>
        {examples.length > 0 && (
          <p className="gs-hint">
            Try:{' '}
            {examples.map((ex) => (
              <button key={ex} className="gs-export" style={{ padding: '2px 8px', marginRight: 4 }}
                onClick={() => setTarget(ex)}>{ex}</button>
            ))}
            <span className="gs-label"> (pigment-pathway genes)</span>
          </p>
        )}
        <textarea className="gs-input" rows={2} value={seq}
          placeholder="…or paste a dsRNA sequence to analyze (optional)"
          onChange={(e) => setSeq(e.target.value)} />
        <button className="gs-run" onClick={run} disabled={loading}>
          {loading ? 'Working…' : (seq.trim() ? 'Analyze this dsRNA' : 'Design a specific dsRNA')}
        </button>
        {error && <div className="gs-error">{error}</div>}

        {res && (
          <>
            <div className="gs-section">
              <h3>{res.mode === 'design' ? 'Designed dsRNA' : 'dsRNA analysis'}</h3>
              <p className="gs-metrics"><Verdict offCount={res.off_target_gene_count} /></p>
              <p className="gs-metrics">
                {res.dsrna_length} bp · {res.n_sirnas} siRNAs · specificity {(res.specificity * 100).toFixed(0)}%
                {res.on_target && <> · on-target <strong>{res.on_target.symbol}</strong> {res.on_target.sites} sites
                  {res.on_target.mean_tpm != null && ` (${res.on_target.mean_tpm} TPM)`}</>}
              </p>
              {(() => {
                const seqOut = res.design ? res.design.sequence : seq.replace(/\s/g, '').toUpperCase();
                const gc = gcPercent(seqOut);
                const gcOk = gc != null && gc >= 30 && gc <= 65;
                const len = seqOut ? seqOut.length : 0;
                const lenOk = len >= 100 && len <= 600;
                return (
                  <>
                    <p className="gs-metrics">
                      GC <strong className={gcOk ? 'gs-cons-yes' : 'gs-cons-no'}>{gc}%</strong>
                      {' '}(aim 30–65%) · length{' '}
                      <strong className={lenOk ? 'gs-cons-yes' : 'gs-cons-no'}>{len} bp</strong>
                      {' '}(typical 100–600 bp for a dsRNA construct)
                    </p>
                    {res.design && <TranscriptMap design={res.design} />}
                    <button className="gs-export" onClick={copySeq}>{copied ? '✓ Copied' : '⧉ Copy sequence'}</button>
                    <button className="gs-export" style={{ marginLeft: 6 }}
                      onClick={() => downloadFasta(seqOut, res.on_target?.symbol || 'dsRNA')}>
                      ⤓ FASTA
                    </button>
                    {res.design && (
                      <textarea className="gs-input" rows={3} readOnly value={res.design.sequence}
                        title={`transcript window ${res.design.start}-${res.design.end}`} />
                    )}
                  </>
                );
              })()}
            </div>

            {res.off_targets.length > 0 && (
              <div className="gs-section">
                <h3>Predicted off-targets <span className="gs-label">(also silenced)</span></h3>
                <table className="gs-table">
                  <thead><tr><th>Gene</th><th title="matching siRNA sites">siRNA sites</th>
                    <th title="where the sites fall along the off-target transcript">site map</th>
                    <th>mean TPM</th></tr></thead>
                  <tbody>
                    {res.off_targets.map((o) => (
                      <tr key={o.gene_id}>
                        <td><GLabel symbol={o.symbol} inferred={o.label_inferred} />{o.is_tf && <span className="gs-ns"> TF</span>}</td>
                        <td className="gs-num">{o.sites}</td>
                        <td><SiteTrack profile={o.profile} length={o.length} /></td>
                        <td className="gs-num">{o.mean_tpm != null ? o.mean_tpm : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {pe && (
              <div className="gs-section">
                <h3>Predicted downstream effect</h3>
                <p className="gs-metrics">
                  Silencing → {pe.affected} genes affected · ↓{pe.down} down · ↑{pe.up} up · ?{pe.unknown} unknown
                </p>
                {pe.top.length > 0 && (
                  <table className="gs-table">
                    <thead><tr><th>Gene</th><th>direction</th><th title="confidence-weighted magnitude">strength</th></tr></thead>
                    <tbody>
                      {pe.top.map((e, i) => (
                        <tr key={i}>
                          <td>{e.symbol}</td>
                          <td>{e.predicted_direction === 'up' ? '↑ up' : e.predicted_direction === 'down' ? '↓ down' : '? unknown'}</td>
                          <td className="gs-num">{e.magnitude.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}

        <div className="gs-section">
          <h3>Or screen many genes at once</h3>
          <p className="gs-hint">Rank a set (e.g. a whole pathway) by how cleanly a specific dsRNA can be made.</p>
          <textarea className="gs-input" rows={2} value={setText}
            placeholder="gene names/ids, space or comma separated (e.g. AN2, DFR, JAF13)"
            onChange={(e) => setSetText(e.target.value)} />
          <button className="gs-run" onClick={runScreen} disabled={loading}>
            {loading ? 'Screening…' : 'Screen set'}
          </button>
          {screen && (
            <>
              <p className="gs-metrics">
                {screen.designable}/{screen.n_genes} genes can get a fully-specific dsRNA
                {screen.predicted_effect && ` · silencing all → ↓${screen.predicted_effect.down} down`}
              </p>
              <table className="gs-table">
                <thead><tr>
                  <th>Gene</th>
                  <th title="Off-target genes hit by the best (most specific) window">off-targets (best window)</th>
                  <th title="Off-target genes anywhere in the transcript">off-targets (whole gene)</th>
                  <th>mean TPM</th>
                </tr></thead>
                <tbody>
                  {screen.results.map((r) => (
                    <tr key={r.gene_id}>
                      <td><GLabel symbol={r.symbol} inferred={r.label_inferred} />{r.designable && <span className="gs-cons-yes"> ✓</span>}</td>
                      <td className="gs-num">{r.best_window_off_targets}</td>
                      <td className="gs-num">{r.transcript_off_targets}</td>
                      <td className="gs-num">{r.mean_tpm != null ? r.mean_tpm : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
