#!/usr/bin/env bash
# Data expansion: fetch external TF-binding data and load into the atlas.
# Currently fetches from ConnecTF (Arabidopsis ChIP/DAP/TARGET).
# Other sources (GTRD, Cistrome, PlantTFDB, GRASSIUS) are blocked by API issues.
#
# Usage: bash scripts/run_data_expansion.sh 2>&1 | tee /tmp/data_expansion.log
set -euo pipefail

PYTHON="backend/venv/bin/python"
FETCH_CONNECTF="backend/scripts/fetch_connectf.py"
LOAD_BINDING="backend/scripts/load_direct_binding.py"
DB="backend/data/grn.sqlite3"

echo "=== Data Expansion Pipeline ==="
echo "Started: $(date -Iseconds)"
echo ""

# --- Phase 1: ConnecTF (Arabidopsis) ---
echo "============================================"
echo "Phase 1: ConnecTF — Arabidopsis TF-target binding"
echo "============================================"
echo ""

echo "Fetching all TF-target edges from ConnecTF API..."
echo "(424 TFs, ~0.5s delay between calls — expect ~4 minutes)"
echo ""
$PYTHON "$FETCH_CONNECTF" --delay 0.5
echo ""

TSV="backend/data/direct_binding/connectf_arabidopsis.tsv"
if [ -f "$TSV" ]; then
    LINES=$(wc -l < "$TSV")
    echo "ConnecTF fetch complete: $((LINES - 1)) edges in $TSV"
    echo ""

    echo "Loading ConnecTF edges into atlas..."
    $PYTHON "$LOAD_BINDING" --db "$DB"
    echo ""
else
    echo "WARNING: ConnecTF fetch produced no output file"
fi

# --- Phase 2: funRiceGenes (Rice) ---
echo "============================================"
echo "Phase 2: funRiceGenes — Rice gene annotations"
echo "============================================"
echo "funRiceGenes provides gene function annotations, not regulatory edges."
echo "Skipping — no TF-target edges to extract."
echo ""

# --- Phase 3: Report ---
echo "============================================"
echo "FINAL REPORT — $(date -Iseconds)"
echo "============================================"
echo ""
echo "Interactions table:"
sqlite3 "$DB" "
  SELECT COUNT(*) as total_edges,
    COUNT(DISTINCT source_id) as unique_tfs,
    COUNT(DISTINCT target_id) as unique_targets
  FROM interactions
"
echo ""
echo "Regulatory evidence by source:"
sqlite3 "$DB" "
  SELECT
    json_extract(metadata, '$.source') as source,
    COUNT(*) as rows
  FROM regulatory_evidence
  WHERE json_extract(metadata, '$.source') IS NOT NULL
  GROUP BY source
  ORDER BY rows DESC
  LIMIT 20
"
echo ""
echo "Total interactions: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM interactions')"
echo "Total regulatory_evidence: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM regulatory_evidence')"
echo ""
echo "Done: $(date -Iseconds)"
