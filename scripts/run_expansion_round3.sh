#!/usr/bin/env bash
# Round 3 data expansion: fetch from newly-reachable sources + retry blocked ones.
#
# Targets:
#   1. ChIP-Atlas target genes (human + mouse) — massive TF binding dataset
#   2. TFLink small-scale experiments (human + mouse)
#   3. PlantTFDB regulatory edges (arabidopsis, rice, tomato)
#   4. GRASSIUS TF data (maize/rice — probe + fetch if available)
#   5. Retry OmniPath (CollecTRI/SIGNOR) for sign expansion
#   6. Retry GTRD bulk downloads
#
# Usage: nohup bash scripts/run_expansion_round3.sh > /tmp/expansion_round3.log 2>&1 &

set -o pipefail
cd /home/kjanik/grn-atlas

VENV="backend/venv/bin/activate"
DB="backend/data/grn.sqlite3"
TIMESTAMP() { date -Iseconds; }

echo "=================================================="
echo "Round 3 Data Expansion — started $(TIMESTAMP)"
echo "=================================================="

if [ -f "$VENV" ]; then
    source "$VENV"
    PYTHON=python
else
    PYTHON=python3
fi

if [ -f ~/.secrets.env ]; then
    source ~/.secrets.env 2>/dev/null || true
fi


# ============================================================
# STEP 1: ChIP-Atlas target genes (existing loader)
# ============================================================
echo ""
echo "=== STEP 1: ChIP-Atlas target genes — $(TIMESTAMP) ==="
$PYTHON backend/scripts/load_chip_atlas.py --db "$DB" 2>&1 || echo "  [WARN] ChIP-Atlas had errors"

echo "  ChIP-Atlas evidence count:"
sqlite3 "$DB" "SELECT source_name, COUNT(*) FROM regulatory_evidence WHERE source_name='ChIP-Atlas'" 2>/dev/null || echo "  (not in regulatory_evidence)"
echo "  Interactions with ChIP-Atlas:"
sqlite3 "$DB" "SELECT COUNT(*) FROM interactions WHERE sources LIKE '%ChIP-Atlas%'" 2>/dev/null || echo "  0"


# ============================================================
# STEP 2: TFLink small-scale (existing loader)
# ============================================================
echo ""
echo "=== STEP 2: TFLink small-scale — $(TIMESTAMP) ==="
$PYTHON backend/scripts/load_tflink.py --db "$DB" 2>&1 || echo "  [WARN] TFLink had errors"

echo "  TFLink evidence count:"
sqlite3 "$DB" "SELECT source_name, COUNT(*) FROM regulatory_evidence WHERE source_name='TFLink small-scale'" 2>/dev/null || echo "  (not in regulatory_evidence)"


# ============================================================
# STEP 3: PlantTFDB / PlantRegMap regulatory edges
# ============================================================
echo ""
echo "=== STEP 3: PlantTFDB regulatory edges — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_planttfdb_edges.py --db "$DB" 2>&1 || echo "  [WARN] PlantTFDB had errors"


# ============================================================
# STEP 4: GRASSIUS
# ============================================================
echo ""
echo "=== STEP 4: GRASSIUS TF data — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_grassius.py --db "$DB" 2>&1 || echo "  [WARN] GRASSIUS had errors"


# ============================================================
# STEP 5: Retry OmniPath (CollecTRI/SIGNOR sign expansion)
# ============================================================
echo ""
echo "=== STEP 5: OmniPath retry (CollecTRI + SIGNOR) — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_collectri_signor.py --db "$DB" 2>&1 || echo "  [WARN] OmniPath still down"


# ============================================================
# STEP 6: Retry GTRD
# ============================================================
echo ""
echo "=== STEP 6: GTRD retry — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_gtrd.py human mouse 2>&1 || echo "  [WARN] GTRD still down"

# If GTRD produced files, load them
for species in human mouse; do
    TSV="backend/data/direct_binding/gtrd_${species}.tsv"
    if [ -f "$TSV" ] && [ -s "$TSV" ]; then
        echo "  Loading GTRD $species edges..."
        $PYTHON backend/scripts/load_direct_binding.py --db "$DB" 2>&1 || echo "  [WARN] GTRD load failed"
    fi
done


# ============================================================
# FINAL REPORT
# ============================================================
echo ""
echo "=================================================="
echo "Round 3 Expansion Complete — $(TIMESTAMP)"
echo "=================================================="
echo ""

echo "=== Atlas Statistics ==="
echo "Total interactions: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM interactions')"
echo "Signed edges: $(sqlite3 "$DB" "SELECT COUNT(*) FROM interactions WHERE sign IS NOT NULL AND sign != ''")"
echo ""
echo "Sign evidence breakdown:"
sqlite3 "$DB" "
    SELECT COALESCE(sign_evidence, 'unsigned'), COUNT(*)
    FROM interactions
    GROUP BY sign_evidence
    ORDER BY COUNT(*) DESC
"
echo ""
echo "Evidence by source:"
sqlite3 "$DB" "
    SELECT source_name, COUNT(*)
    FROM regulatory_evidence
    GROUP BY source_name
    ORDER BY COUNT(*) DESC
"
echo "Total evidence rows: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM regulatory_evidence')"
echo ""
echo "Structural predictions: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM structural_binding_predictions')"
echo "ESM2 embeddings: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM esm2_embeddings')"
echo "AlphaFold features: $(sqlite3 "$DB" "SELECT COUNT(*) FROM alphafold_features WHERE fetch_status='found'")"
echo ""
echo "Done."
