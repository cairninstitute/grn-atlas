#!/usr/bin/env bash
# Batch runner for structural binding predictions across all species.
# Runs in batches of 500 per species, resumable (pipeline skips already-predicted edges).
# Usage: nohup bash scripts/run_structural_predictions.sh > /tmp/structural_predictions_r2.log 2>&1 &
set -o pipefail

cd /home/kjanik/grn-atlas

SCRIPT="backend/scripts/predict_structural_binding.py"
PYTHON="backend/venv/bin/python"
DB="backend/data/grn.sqlite3"
BATCH=500
TIER="all"

# Load API key
if [ -f "$HOME/.secrets.env" ]; then
  source "$HOME/.secrets.env" 2>/dev/null || true
fi

if [ -z "${NVIDIA_NIM_API_KEY:-}" ]; then
  echo "ERROR: NVIDIA_NIM_API_KEY not set. Source ~/.secrets.env or export it."
  exit 1
fi

echo "Structural binding prediction batch runner"
echo "Started: $(date -Iseconds)"
echo ""

for species in human mouse arabidopsis tomato rice petunia; do
    echo "============================================"
    echo "[$species] Starting — $(date -Iseconds)"
    echo "============================================"

    # Run in batches until no more edges are selected
    batch_num=0
    while true; do
        batch_num=$((batch_num + 1))
        echo ""
        echo "[$species] Batch $batch_num — processing up to $BATCH..."

        output=$($PYTHON "$SCRIPT" --species "$species" --tier "$TIER" --max-edges "$BATCH" --rate-limit 1.5 2>&1)
        echo "$output"

        # Check if any edges were selected
        if echo "$output" | grep -q "Selected 0 candidate edges"; then
            echo "[$species] All candidates predicted."
            break
        fi

        # Brief pause between batches
        sleep 5
    done

    echo "[$species] Done at $(date -Iseconds)"
    echo ""
done

echo ""
echo "============================================"
echo "FINAL SUMMARY — $(date -Iseconds)"
echo "============================================"
sqlite3 "$DB" "
  SELECT species, binding_class, COUNT(*),
    CASE WHEN binding_class IN ('likely','uncertain','unlikely')
      THEN ROUND(AVG(confidence_score),3) ELSE NULL END
  FROM structural_binding_predictions
  GROUP BY species, binding_class
  ORDER BY species, binding_class
"
echo ""
echo "Total predictions:"
sqlite3 "$DB" "SELECT COUNT(*) FROM structural_binding_predictions"
echo "Done."
