#!/usr/bin/env bash
# Round 2 data expansion: structural predictions restart, data source retries,
# sign expansion, AlphaFold features.
#
# Designed to run unattended. Each step is independent and failure-tolerant.
# Usage: nohup bash scripts/run_expansion_round2.sh > /tmp/expansion_round2.log 2>&1 &

set -o pipefail
cd /home/kjanik/grn-atlas

VENV="backend/venv/bin/activate"
DB="backend/data/grn.sqlite3"
LOG="/tmp/expansion_round2.log"
TIMESTAMP() { date -Iseconds; }

echo "=================================================="
echo "Round 2 Data Expansion — started $(TIMESTAMP)"
echo "=================================================="

# ---- Activate venv ----
if [ -f "$VENV" ]; then
    source "$VENV"
    PYTHON=python
else
    PYTHON=python3
fi

# ---- Load API key for structural predictions ----
if [ -f ~/.secrets.env ]; then
    source ~/.secrets.env
fi


# ============================================================
# STEP 1: Sign expansion — CollecTRI + SIGNOR via OmniPath
# ============================================================
echo ""
echo "=== STEP 1: Sign expansion (CollecTRI + SIGNOR) — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_collectri_signor.py --db "$DB" || echo "  [WARN] CollecTRI/SIGNOR had errors"

echo "  Sign stats after expansion:"
sqlite3 "$DB" "
    SELECT sign_evidence, COUNT(*)
    FROM interactions
    WHERE sign IS NOT NULL AND sign != ''
    GROUP BY sign_evidence
    ORDER BY COUNT(*) DESC
"
echo "  Total signed: $(sqlite3 "$DB" "SELECT COUNT(*) FROM interactions WHERE sign IS NOT NULL AND sign != ''")"
echo "  Total interactions: $(sqlite3 "$DB" "SELECT COUNT(*) FROM interactions")"


# ============================================================
# STEP 2: Retry blocked data sources
# ============================================================
echo ""
echo "=== STEP 2: Retry blocked data sources — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_plantregmap_retry.py || echo "  [WARN] Some sources still down"


# ============================================================
# STEP 3: Try GTRD bulk download
# ============================================================
echo ""
echo "=== STEP 3: GTRD fetch — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_gtrd.py human mouse || echo "  [WARN] GTRD fetch had errors"

# If GTRD produced files, load them
for species in human mouse; do
    TSV="backend/data/direct_binding/gtrd_${species}.tsv"
    if [ -f "$TSV" ] && [ -s "$TSV" ]; then
        echo "  Loading GTRD $species edges..."
        $PYTHON backend/scripts/load_direct_binding.py --db "$DB" || echo "  [WARN] GTRD load failed"
    fi
done


# ============================================================
# STEP 4: AlphaFold structural features
# ============================================================
echo ""
echo "=== STEP 4: AlphaFold features — $(TIMESTAMP) ==="
$PYTHON backend/scripts/fetch_alphafold_features.py --db "$DB" --delay 0.3 || echo "  [WARN] AlphaFold fetch had errors"


# ============================================================
# STEP 5: Restart structural binding predictions
# ============================================================
echo ""
echo "=== STEP 5: Structural binding predictions — $(TIMESTAMP) ==="

# Check remaining candidates (supported from edge_candidates + cycle-closing from candidate_impacts)
REMAINING=$(sqlite3 "$DB" "
    SELECT COUNT(*) FROM (
        SELECT species, source_id, target_id FROM regulatory_edge_candidates
        WHERE evidence_tier = 'supported'
        UNION
        SELECT species, source_id, target_id FROM regulatory_candidate_impacts
        WHERE closes_cycle = 1
    ) c
    WHERE NOT EXISTS (
        SELECT 1 FROM structural_binding_predictions sbp
        WHERE sbp.species = c.species
        AND sbp.source_id = c.source_id
        AND sbp.target_id = c.target_id
        AND sbp.binding_class NOT IN ('error', 'no_sequence')
    )
")
echo "  $REMAINING candidate edges remaining for structural prediction"

if [ "$REMAINING" -gt 0 ] && [ -n "$NVIDIA_NIM_API_KEY" ]; then
    # Run species sequentially to avoid concurrent writes
    for species in human mouse arabidopsis tomato rice petunia; do
        SP_REMAINING=$(sqlite3 "$DB" "
            SELECT COUNT(*) FROM (
                SELECT species, source_id, target_id FROM regulatory_edge_candidates
                WHERE species = '$species' AND evidence_tier = 'supported'
                UNION
                SELECT species, source_id, target_id FROM regulatory_candidate_impacts
                WHERE species = '$species' AND closes_cycle = 1
            ) c
            WHERE NOT EXISTS (
                SELECT 1 FROM structural_binding_predictions sbp
                WHERE sbp.species = c.species
                AND sbp.source_id = c.source_id
                AND sbp.target_id = c.target_id
                AND sbp.binding_class NOT IN ('error', 'no_sequence')
            )
        ")
        if [ "$SP_REMAINING" -gt 0 ]; then
            echo "  [$species] $SP_REMAINING remaining — starting predictions..."
            $PYTHON backend/scripts/predict_structural_binding.py \
                --db "$DB" \
                --species "$species" \
                --tier all \
                --max-edges 500 \
                --rate-limit 1.5 || echo "  [WARN] $species structural predictions had errors"
            echo "  [$species] Done at $(TIMESTAMP)"
        fi
    done
else
    if [ -z "$NVIDIA_NIM_API_KEY" ]; then
        echo "  NVIDIA_NIM_API_KEY not set, skipping structural predictions"
    else
        echo "  No remaining candidates"
    fi
fi


# ============================================================
# FINAL REPORT
# ============================================================
echo ""
echo "=================================================="
echo "Round 2 Expansion Complete — $(TIMESTAMP)"
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
echo "ESM2 embeddings: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM esm2_embeddings')"
echo "Protein sequences: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM protein_sequences')"
echo "Motifs: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM motifs')"
echo "Motif hits: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM motif_hits')"
echo ""
echo "Structural predictions:"
sqlite3 "$DB" "
    SELECT species, binding_class, COUNT(*)
    FROM structural_binding_predictions
    GROUP BY species, binding_class
    ORDER BY species, binding_class
"
echo "Total: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM structural_binding_predictions')"
echo ""

# AlphaFold features
AF_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM alphafold_features WHERE fetch_status='found'" 2>/dev/null || echo "0")
echo "AlphaFold features: $AF_COUNT"
sqlite3 "$DB" "
    SELECT species, COUNT(*), ROUND(AVG(mean_plddt),1), ROUND(AVG(disorder_fraction),3)
    FROM alphafold_features
    WHERE fetch_status='found'
    GROUP BY species
" 2>/dev/null

echo ""
echo "Done."
