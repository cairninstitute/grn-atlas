#!/usr/bin/env bash
# Batch runner for implementation items 3, 4, and 5:
#   3. ESM2 protein embedding table
#   4. Sign inference via ortholog transfer
#   5. Human base-resolution binding (JASPAR vertebrate)
#
# Usage: bash scripts/run_items_3_4_5.sh 2>&1 | tee /tmp/items_3_4_5.log
set -euo pipefail

PYTHON="backend/venv/bin/python"
SYSPYTHON="python3"
DB="backend/data/grn.sqlite3"

echo "=== Implementation Items 3, 4, 5 ==="
echo "Started: $(date -Iseconds)"
echo ""

# ======================================================================
# Item 4: Sign inference via ortholog transfer (pure Python, no deps)
# ======================================================================
echo "============================================"
echo "Item 4: Sign inference via ortholog transfer"
echo "============================================"
echo ""
$PYTHON backend/scripts/transfer_ortholog_signs.py --db "$DB"
echo ""
echo "Item 4 complete: $(date -Iseconds)"
echo ""

# ======================================================================
# Item 5: JASPAR vertebrate motifs + scan
# ======================================================================
echo "============================================"
echo "Item 5: JASPAR vertebrate motifs for human/mouse"
echo "============================================"
echo ""
$PYTHON backend/scripts/fetch_jaspar_vertebrate.py --db "$DB" --scan
echo ""
echo "Item 5 complete: $(date -Iseconds)"
echo ""

# ======================================================================
# Item 3: ESM2 protein embeddings (requires torch + transformers)
# ======================================================================
echo "============================================"
echo "Item 3: ESM2 protein embeddings"
echo "============================================"
echo ""

# Install dependencies if needed
if ! $PYTHON -c "from transformers import AutoModel" 2>/dev/null; then
    echo "Installing torch and transformers in backend venv..."
    $PYTHON -m pip install --quiet torch transformers 2>&1 | tail -3
    echo ""
fi

# Verify
if $PYTHON -c "import torch; from transformers import AutoModel; print('Dependencies OK, CUDA:', torch.cuda.is_available())" 2>/dev/null; then
    $PYTHON backend/scripts/generate_esm2_embeddings.py --db "$DB" --batch-size 4
else
    echo "WARNING: Could not install torch/transformers in backend venv."
    echo "Falling back to system python..."
    if $SYSPYTHON -c "import torch; from transformers import AutoModel; print('System python OK')" 2>/dev/null; then
        $SYSPYTHON backend/scripts/generate_esm2_embeddings.py --db "$DB" --batch-size 4
    else
        echo "ERROR: Neither venv nor system python has torch+transformers."
        echo "Install manually: pip install torch transformers"
    fi
fi
echo ""
echo "Item 3 complete: $(date -Iseconds)"
echo ""

# ======================================================================
# Final Report
# ======================================================================
echo "============================================"
echo "FINAL REPORT — $(date -Iseconds)"
echo "============================================"
echo ""

echo "Sign distribution:"
sqlite3 "$DB" "
  SELECT sign, sign_evidence, COUNT(*)
  FROM interactions
  WHERE sign IS NOT NULL AND sign != ''
  GROUP BY sign, sign_evidence
  ORDER BY COUNT(*) DESC
"
echo ""

echo "Unsigned remaining:"
sqlite3 "$DB" "SELECT COUNT(*) FROM interactions WHERE sign IS NULL OR sign = ''"
echo ""

echo "Motifs:"
sqlite3 "$DB" "SELECT source, COUNT(*) FROM motifs GROUP BY source"
echo ""

echo "Motif hits:"
sqlite3 "$DB" "SELECT COUNT(*) FROM motif_hits" 2>/dev/null || echo "0"
echo ""

echo "ESM2 embeddings:"
sqlite3 "$DB" "SELECT species, COUNT(*) FROM esm2_embeddings GROUP BY species" 2>/dev/null || echo "none yet"
echo ""

echo "Protein sequences:"
sqlite3 "$DB" "SELECT fetch_status, COUNT(*) FROM protein_sequences GROUP BY fetch_status"
echo ""

echo "Done: $(date -Iseconds)"
