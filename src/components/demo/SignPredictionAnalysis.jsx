import React, { useEffect, useState } from 'react';
import '../../styles/SignPredictionAnalysis.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const METHOD_META = {
  'perturbation-calibration': {
    label: 'Perturbation consensus',
    principle: 'Aggregate KO/OE expression changes across experiments to infer activation vs repression',
    color: '#d08955',
  },
  'inferred-sign-model': {
    label: 'Supervised logistic model',
    principle: 'Binding strength + perturbation features → sign (grouped cross-validation)',
    color: '#7f94a7',
  },
  'expression-correlation': {
    label: 'Expression correlation',
    principle: 'Positive co-expression → activation, negative → repression',
    color: '#4a8876',
  },
  'sae-features': {
    label: 'ESM2/SAE latent features',
    principle: 'Protein language model sparse autoencoder features → regulatory sign',
    color: '#9a7598',
  },
};

function PrecisionBar({ value, baseline, label, gate }) {
  const pct = Math.min(value * 100, 100);
  const basePct = Math.min(baseline * 100, 100);
  const passed = gate === true;
  return (
    <div className="sign-precision-row">
      <div className="sign-precision-label">{label}</div>
      <div className="sign-precision-track">
        <div className="sign-precision-baseline" style={{ left: `${basePct}%` }} title={`Baseline: ${(baseline * 100).toFixed(1)}%`} />
        <div
          className={`sign-precision-fill ${passed ? 'passed' : 'failed'}`}
          style={{ width: `${pct}%` }}
        />
        <span className="sign-precision-value">{(value * 100).toFixed(1)}%</span>
      </div>
      <div className={`sign-precision-gate ${passed ? 'passed' : 'failed'}`}>
        {passed ? 'Pass' : 'Fail'}
      </div>
    </div>
  );
}

export default function SignPredictionAnalysis() {
  const [perturbData, setPerturbData] = useState(null);
  const [modelData, setModelData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [pResp, mResp] = await Promise.all([
          fetch('/docs/benchmarks/perturbation-sign-calibration.json').catch(() => null),
          fetch('/docs/benchmarks/inferred-sign-model.json').catch(() => null),
        ]);
        if (pResp?.ok) setPerturbData(await pResp.json());
        if (mResp?.ok) setModelData(await mResp.json());
      } catch {
        // Static files may not be served; fall back to empty
      }
      setLoading(false);
    }
    load();
  }, []);

  if (loading) return <div className="sign-loading">Loading sign prediction data…</div>;

  const perturbClasses = perturbData?.classes || [];
  const modelCV = modelData?.tf_grouped_cross_validation;
  const modelGate = modelData?.promotion_gate;

  return (
    <div className="sign-prediction-analysis">
      <header className="sign-header">
        <h2>Where sign prediction breaks</h2>
        <p>
          Four independent methods built on different principles — expression correlation,
          perturbation consensus, a supervised logistic model, and a genomic language model's
          SAE features — all fail on the same task: predicting whether a regulatory edge
          is activation or repression.
        </p>
        <p className="sign-finding">
          This is a finding about the <em>problem</em>, not about any one method.
          Regulatory sign is context-dependent, and no global predictor crosses the
          precision gate the atlas requires.
        </p>
      </header>

      <section className="sign-methods">
        <h3>Methods tested</h3>
        <div className="sign-method-grid">
          {Object.entries(METHOD_META).map(([key, meta]) => (
            <div key={key} className="sign-method-card" style={{ borderTopColor: meta.color }}>
              <strong>{meta.label}</strong>
              <p>{meta.principle}</p>
            </div>
          ))}
        </div>
      </section>

      {perturbClasses.length > 0 && (
        <section className="sign-results-section">
          <h3>Perturbation sign calibration</h3>
          <p className="sign-note">
            Only <strong>human activation</strong> passes the gate. All repression classes
            and all non-human species fail — precision does not reliably exceed the base rate.
          </p>
          <div className="sign-results-grid">
            {perturbClasses.map((cls, i) => (
              <PrecisionBar
                key={i}
                label={`${cls.species} ${cls.relation_type}`}
                value={cls.precision}
                baseline={cls.baseline_rate}
                gate={cls.gate_pass}
              />
            ))}
          </div>
          <div className="sign-gate-note">
            Gate: precision must exceed base rate with Wilson CI lower bound above base rate.
            Supported: {perturbData.supported_classes?.join(', ') || 'none'}.
          </div>
        </section>
      )}

      {modelCV && (
        <section className="sign-results-section">
          <h3>Supervised logistic model</h3>
          <p className="sign-note">
            A logistic model trained on binding strength, perturbation features, and sign
            consistency achieves <strong>{(modelCV.roc_auc * 100).toFixed(1)}% ROC-AUC</strong> under
            TF-grouped cross-validation — barely above chance.
          </p>
          <div className="sign-model-stats">
            <div>
              <span className="sign-stat-value">{(modelCV.balanced_accuracy * 100).toFixed(1)}%</span>
              <span className="sign-stat-label">Balanced accuracy</span>
            </div>
            <div>
              <span className="sign-stat-value">{(modelCV.activation_precision * 100).toFixed(1)}%</span>
              <span className="sign-stat-label">Activation precision</span>
            </div>
            <div>
              <span className="sign-stat-value">{(modelCV.repression_precision * 100).toFixed(1)}%</span>
              <span className="sign-stat-label">Repression precision</span>
            </div>
            <div>
              <span className="sign-stat-value">{modelCV.cases.toLocaleString()}</span>
              <span className="sign-stat-label">Test cases</span>
            </div>
          </div>
          {modelGate && (
            <div className={`sign-gate-verdict ${modelGate.passed ? 'passed' : 'failed'}`}>
              Gate: minimum {(modelGate.minimum_balanced_accuracy * 100)}% balanced accuracy,
              {' '}{(modelGate.minimum_precision_each_sign * 100)}% precision each sign.
              <strong> {modelGate.passed ? 'Passed' : 'Rejected'}</strong> —{' '}
              {modelData.deployment_status?.replace(/_/g, ' ')}
            </div>
          )}
        </section>
      )}

      <section className="sign-interpretation">
        <h3>What this means</h3>
        <div className="sign-boundary">
          <p>
            <strong>Expression correlation is uninformative for sign.</strong> A positive
            correlation between TF and target does not reliably indicate activation — many
            repressors are co-expressed with their targets during the same developmental programs.
          </p>
          <p>
            <strong>Perturbation consensus works for human activation only.</strong> The
            directional effect of KO/OE on targets is consistent enough to clear the gate for
            activation, but repression calls are unreliable — probably because indirect effects
            dominate the response.
          </p>
          <p>
            <strong>The atlas draws the line here.</strong> Signs that pass the gate are labeled
            as supported; signs from failed classes are marked exploratory and are never promoted
            into the interaction graph. This is by design — a wrong sign is worse than no sign.
          </p>
        </div>
      </section>
    </div>
  );
}
