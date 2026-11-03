#!/bin/bash
# Run Evo2 and Enformer calibrations with retry logic.
# Survives session disconnects via nohup.
# Usage: nohup bash backend/scripts/run_calibrations.sh &

set -euo pipefail
VENV="/home/kjanik/grn-atlas/venv/bin/python3"
SCRIPTS="/home/kjanik/grn-atlas/backend/scripts"
DATA="/home/kjanik/grn-atlas/backend/data"
LOG_DIR="/home/kjanik/grn-atlas/backend/data"

# Set up CUDA for Enformer GPU
NVIDIA_LIB_DIRS=$(find /home/kjanik/grn-atlas/venv/lib/python3.12/site-packages/nvidia -name "lib" -type d 2>/dev/null | tr '\n' ':')
export LD_LIBRARY_PATH="${NVIDIA_LIB_DIRS}${LD_LIBRARY_PATH:-}"
export XLA_FLAGS="--xla_gpu_cuda_data_dir=/home/kjanik/grn-atlas/venv/lib/python3.12/site-packages/nvidia/cuda_nvcc"
export TF_CPP_MIN_LOG_LEVEL=2

echo "=== Starting calibrations at $(date) ===" | tee -a "$LOG_DIR/calibration_runner.log"

# --- Evo2 calibration ---
if [ ! -f "$DATA/evo2_binding_calibration.json" ] || ! grep -q '"mean_separation"' "$DATA/evo2_binding_calibration.json" 2>/dev/null; then
    echo "[$(date)] Running Evo2 calibration..." | tee -a "$LOG_DIR/calibration_runner.log"
    $VENV "$SCRIPTS/calibrate_evo2_binding.py" \
        --species arabidopsis --positives 20 --negatives 20 \
        2>&1 | tee "$LOG_DIR/evo2_calibration.log"
    echo "[$(date)] Evo2 calibration done." | tee -a "$LOG_DIR/calibration_runner.log"
else
    echo "[$(date)] Evo2 calibration already complete, skipping." | tee -a "$LOG_DIR/calibration_runner.log"
fi

# --- Enformer calibration ---
if [ ! -f "$DATA/enformer_binding_calibration.json" ] || ! grep -q '"mean_separation"' "$DATA/enformer_binding_calibration.json" 2>/dev/null; then
    echo "[$(date)] Running Enformer calibration..." | tee -a "$LOG_DIR/calibration_runner.log"
    $VENV "$SCRIPTS/calibrate_enformer_binding.py" \
        --species human --positives 20 --negatives 20 \
        2>&1 | tee "$LOG_DIR/enformer_calibration.log"
    echo "[$(date)] Enformer calibration done." | tee -a "$LOG_DIR/calibration_runner.log"
else
    echo "[$(date)] Enformer calibration already complete, skipping." | tee -a "$LOG_DIR/calibration_runner.log"
fi

echo "=== All calibrations finished at $(date) ===" | tee -a "$LOG_DIR/calibration_runner.log"
