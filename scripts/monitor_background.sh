#!/usr/bin/env bash
# Monitor background processes and report status
DB="backend/data/grn.sqlite3"

echo "=== Background Process Monitor ==="
echo "Time: $(date -Iseconds)"
echo ""

# Structural predictions
echo "--- Structural Binding Predictions ---"
if pgrep -f "predict_structural_binding\|run_structural_predictions" > /dev/null; then
    echo "Status: RUNNING"
    pgrep -f "predict_structural_binding" | while read pid; do
        ps -o pid=,etime=,rss= -p $pid 2>/dev/null
    done
else
    echo "Status: NOT RUNNING"
fi
sqlite3 "$DB" "
  SELECT species, binding_class, COUNT(*)
  FROM structural_binding_predictions
  GROUP BY species, binding_class
  ORDER BY species, binding_class
" 2>/dev/null
echo "Total predictions: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM structural_binding_predictions' 2>/dev/null)"
echo ""

# ESM2 embeddings
echo "--- ESM2 Embeddings ---"
if pgrep -f "generate_esm2" > /dev/null; then
    echo "Status: RUNNING"
    pgrep -f "generate_esm2" | while read pid; do
        ps -o pid=,etime=,rss= -p $pid 2>/dev/null
    done
else
    echo "Status: NOT RUNNING"
fi
sqlite3 "$DB" "SELECT species, COUNT(*) FROM esm2_embeddings GROUP BY species" 2>/dev/null || echo "No embeddings yet"
echo "Protein sequences: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM protein_sequences' 2>/dev/null)"
echo ""

# Overall stats
echo "--- Atlas Stats ---"
echo "Total interactions: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM interactions')"
echo "Signed edges: $(sqlite3 "$DB" "SELECT COUNT(*) FROM interactions WHERE sign IS NOT NULL AND sign != ''")"
echo "Motifs: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM motifs')"
echo "Motif hits: $(sqlite3 "$DB" 'SELECT COUNT(*) FROM motif_hits')"
echo ""
