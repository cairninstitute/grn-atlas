#!/bin/bash
# Run all three large-scale binding validation scripts autonomously.
# Designed to run without Claude tokens — continues through disconnects.
#
# Usage:
#   nohup bash backend/scripts/run_large_validations.sh > /tmp/all_validations.log 2>&1 &
#
# Outputs:
#   backend/data/jaspar_calibration.json        — JASPAR (seconds, no API)
#   backend/data/enformer_large_validation.json  — Enformer (GPU, ~30-60 min)
#   backend/data/boltz2_large_validation.json    — Boltz-2 (NIM API, ~2-4 hours)

set -uo pipefail
cd "$(dirname "$0")/../.."

# Activate project venv (has tensorflow, sklearn, etc.)
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
    echo "Activated venv: $(which python3)"
fi

LOG_DIR="/tmp"
DATA_DIR="backend/data"

echo "=========================================="
echo "Large-scale binding validation suite"
echo "Started: $(date)"
echo "=========================================="

# Load API keys (set +e because secrets.env may have lines that fail in strict mode)
if [ -f ~/.secrets.env ]; then
    set +e
    source ~/.secrets.env 2>/dev/null
    set -e
    echo "API keys loaded from ~/.secrets.env"
fi

# Set GPU environment
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TF_CPP_MIN_LOG_LEVEL=2

# Phase 1: JASPAR (fastest — pure database, no API, no GPU)
echo ""
echo "=========================================="
echo "Phase 1/3: JASPAR motif scanning calibration"
echo "Started: $(date)"
echo "=========================================="

python3 backend/scripts/validate_jaspar_calibration.py \
    --max-per-tf 50 \
    2>&1 | tee "${LOG_DIR}/jaspar_calibration.log" \
    && echo "JASPAR complete: $(date)" \
    || echo "JASPAR FAILED: $(date) — continuing to next phase"

echo ""

# Phase 2: Enformer (local GPU, no API calls, ~30-60 min)
echo "=========================================="
echo "Phase 2/3: Enformer large-scale validation"
echo "Started: $(date)"
echo "=========================================="

# Enformer needs specific TF/GPU setup
export XLA_FLAGS="--xla_gpu_cuda_data_dir=/usr/lib/cuda"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/home/kjanik/.local/lib/python3.12/site-packages/nvidia/cudnn/lib:/home/kjanik/.local/lib/python3.12/site-packages/nvidia/cuda_cupti/lib"

python3 backend/scripts/validate_enformer_large_scale.py \
    --species human --positives 50 --negatives 50 \
    2>&1 | tee "${LOG_DIR}/enformer_large_validation.log" \
    && echo "Enformer complete: $(date)" \
    || echo "Enformer FAILED: $(date) — continuing to next phase"

echo ""

# Phase 3: Boltz-2 (NIM API, rate-limited, ~2-4 hours)
echo "=========================================="
echo "Phase 3/3: Boltz-2 large-scale validation"
echo "Started: $(date)"
echo "=========================================="

python3 backend/scripts/validate_boltz2_large_scale.py \
    --species arabidopsis human \
    --positives 50 --negatives 50 \
    --rate-limit 2.0 \
    2>&1 | tee "${LOG_DIR}/boltz2_large_validation.log" \
    && echo "Boltz-2 complete: $(date)" \
    || echo "Boltz-2 FAILED: $(date)"
echo ""

# Summary
echo "=========================================="
echo "ALL VALIDATIONS COMPLETE"
echo "Finished: $(date)"
echo "=========================================="
echo ""
echo "Results:"
echo "  ${DATA_DIR}/jaspar_calibration.json"
echo "  ${DATA_DIR}/enformer_large_validation.json"
echo "  ${DATA_DIR}/boltz2_large_validation.json"
echo ""

# Quick summary from each output
for f in jaspar_calibration enformer_large_validation boltz2_large_validation; do
    if [ -f "${DATA_DIR}/${f}.json" ]; then
        echo "--- ${f} ---"
        python3 -c "
import json
d = json.load(open('${DATA_DIR}/${f}.json'))
status = d.get('status', 'unknown')
print(f'  Status: {status}')
if 'overall_auc' in d:
    print(f'  Overall AUC: {d[\"overall_auc\"]}')
if 'species_results' in d:
    for sp, r in d['species_results'].items():
        auc = r.get('overall_auc') or r.get('auc')
        print(f'  {sp}: AUC={auc}')
" 2>/dev/null || echo "  (could not parse)"
    fi
done
