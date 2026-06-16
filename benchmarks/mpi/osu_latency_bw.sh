#!/bin/bash
# benchmarks/mpi/osu_latency.sh
# Point-to-point latency between two nodes over EFA
# Equivalent to `ib_send_lat` on physical InfiniBand

set -euo pipefail

HOSTFILE="${HOSTFILE:-$HOME/hostfile}"
RESULTS_DIR="$(dirname "$0")/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$RESULTS_DIR"

echo "============================================"
echo "OSU MPI Latency Benchmark (EFA)"
echo "============================================"

mpirun \
  --hostfile "$HOSTFILE" \
  --np 2 \
  --map-by node \
  --mca btl_base_warn_component_unused 0 \
  --mca osc pt2pt \
  osu_latency \
  2>&1 | tee "$RESULTS_DIR/latency_${TIMESTAMP}.txt"

echo ""
echo "============================================"
echo "OSU MPI Bandwidth Benchmark (EFA)"
echo "Equivalent to: ib_send_bw on InfiniBand"
echo "============================================"

mpirun \
  --hostfile "$HOSTFILE" \
  --np 2 \
  --map-by node \
  osu_bw \
  2>&1 | tee "$RESULTS_DIR/bandwidth_${TIMESTAMP}.txt"

echo ""
echo "Results in: $RESULTS_DIR"

# Upload to S3
if [ -n "${RESULTS_BUCKET:-}" ]; then
  aws s3 sync "$RESULTS_DIR/" "s3://$RESULTS_BUCKET/results/mpi/"
  echo "Uploaded to S3"
fi
