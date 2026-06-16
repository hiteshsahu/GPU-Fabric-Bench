#!/bin/bash
# benchmarks/nccl/sweep_msgsize.sh
# Fine-grained message size sweep across all NCCL collectives
#
# Runs AllReduce, AllGather, and ReduceScatter at fixed message sizes
# to find the crossover point where Ring outperforms Tree and where
# the fabric transitions from latency-bound to bandwidth-bound.
# Use this to validate NCCL_ALGO and NCCL_PROTO overrides.

set -euo pipefail

HOSTFILE="${HOSTFILE:-$HOME/hostfile}"
RESULTS_DIR="$(dirname "$0")/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SWEEP_DIR="$RESULTS_DIR/sweep_${TIMESTAMP}"

mkdir -p "$SWEEP_DIR"

NUM_NODES=$(wc -l < "$HOSTFILE")
GPUS_PER_NODE=${GPUS_PER_NODE:-8}
TOTAL_PROCS=$((NUM_NODES * GPUS_PER_NODE))

# Fine-grained sweep: powers of 2 from 1KB to 1GB
MIN_BYTES="${MIN_BYTES:-1K}"
MAX_BYTES="${MAX_BYTES:-1G}"

echo "============================================"
echo "NCCL Message Size Sweep"
echo "Nodes: $NUM_NODES | GPUs/node: $GPUS_PER_NODE | Total: $TOTAL_PROCS"
echo "Range: $MIN_BYTES → $MAX_BYTES (stepfactor 2)"
echo "Timestamp: $TIMESTAMP"
echo "============================================"

source /etc/profile.d/nccl-efa.sh

_run() {
  local collective="$1"
  local binary="$2"
  local algo="${3:-}"
  local proto="${4:-}"

  local label="${collective}"
  [ -n "$algo" ] && label="${label}_${algo}"
  [ -n "$proto" ] && label="${label}_${proto}"
  local outfile="$SWEEP_DIR/${label}.txt"

  echo ""
  echo "--- $label ---"

  {
    echo "# collective: $collective"
    echo "# algo: ${algo:-auto}"
    echo "# proto: ${proto:-auto}"
    echo "# nodes: $NUM_NODES  gpus_per_node: $GPUS_PER_NODE"
    echo
  } > "$outfile"

  NCCL_ALGO="${algo:-}" NCCL_PROTO="${proto:-}" \
  mpirun \
    --hostfile "$HOSTFILE" \
    --np "$TOTAL_PROCS" \
    --bind-to none \
    -x NCCL_SOCKET_IFNAME \
    -x NCCL_IB_DISABLE \
    -x NCCL_IB_HCA \
    -x NCCL_DEBUG \
    -x NCCL_ALGO \
    -x NCCL_PROTO \
    -x FI_EFA_USE_DEVICE_RDMA \
    -x FI_PROVIDER \
    -x LD_LIBRARY_PATH \
    "$binary" \
      --minbytes "$MIN_BYTES" \
      --maxbytes "$MAX_BYTES" \
      --stepfactor 2 \
      --ngpus "$GPUS_PER_NODE" \
      --check 0 \
      --iters 20 \
      --warmup_iters 5 \
    2>&1 | tee -a "$outfile"
}

# AllReduce: Ring vs Tree — find the crossover
_run allreduce all_reduce_perf Ring  Simple
_run allreduce all_reduce_perf Tree  LL
_run allreduce all_reduce_perf       # NCCL auto-select baseline

# AllGather: ZeRO-3 param gather
_run allgather all_gather_perf

# ReduceScatter: ZeRO-3 gradient scatter
_run reducescatter reduce_scatter_perf

echo ""
echo "============================================"
echo "Sweep complete. Results in: $SWEEP_DIR"
echo "Files:"
ls "$SWEEP_DIR"
echo "============================================"

if [ -n "${RESULTS_BUCKET:-}" ]; then
  aws s3 sync "$SWEEP_DIR/" "s3://$RESULTS_BUCKET/results/nccl/sweep_${TIMESTAMP}/"
  echo "Uploaded to s3://$RESULTS_BUCKET/results/nccl/sweep_${TIMESTAMP}/"
fi
