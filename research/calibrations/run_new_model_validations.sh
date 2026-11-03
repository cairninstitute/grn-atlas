#!/bin/bash
# Run new model binding calibrations sequentially.
# Borzoi -> AgroNT -> deepTFBS (if weights available)
#
# Usage:
#   nohup bash backend/scripts/run_new_model_validations.sh \
#       > /tmp/new_model_validations.log 2>&1 &

set -euo pipefail

cd "$(dirname "$0")/../.."
source venv/bin/activate

echo "=== New Model Binding Calibrations ==="
echo "Started: $(date)"
echo ""

# 1. Borzoi (human, 524K bp input, PyTorch)
echo "=== BORZOI (human) ==="
python backend/scripts/validate_borzoi_binding.py \
    --positives 50 --negatives 50
echo "Borzoi complete: $(date)"
echo ""

# 2. AgroNT (arabidopsis, 1B param plant DNA foundation model)
echo "=== AGRONT (arabidopsis) ==="
python backend/scripts/validate_plantcaduceus_binding.py \
    --positives 50 --negatives 50 --species arabidopsis
echo "AgroNT complete: $(date)"
echo ""

# 3. deepTFBS (arabidopsis, Docker-based, 359 TF multi-task model)
WEIGHTS_DIR="deepTFBS/pretrained_weights"
if [ -d "$WEIGHTS_DIR" ] && [ "$(ls -A $WEIGHTS_DIR 2>/dev/null)" ]; then
    echo "=== DEEPTFBS (arabidopsis) ==="
    python backend/scripts/validate_deeptfbs_binding.py \
        --positives 50 --negatives 50
    echo "deepTFBS complete: $(date)"
else
    echo "=== DEEPTFBS: SKIPPED (no weights in $WEIGHTS_DIR) ==="
fi
echo ""

echo "=== All validations complete: $(date) ==="
