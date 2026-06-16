#!/bin/bash
# benchmarks/nccl/run_allgather.sh
# NCCL AllGather benchmark across all nodes
#
# AllGather is the ZeRO-3 param-gather collective: each rank holds a shard
# of a tensor; after AllGather every rank has the full tensor.
# Inter-node AllGather saturates EFA differently from AllReduce —
# it is purely a scatter/copy with no reduction, so busbw == algbw * N/(N-1).

set -euo pipefail

HOSTFILE="${HOSTFILE:-$HOME/hostfile}"
RESULTS_DIR="$(dirname "$0")/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="$RESULTS_DIR/allgather_${TIMESTAMP}.txt"

mkdir -p "$RESULTS_DIR"

NUM_NODES=$(wc -l < "$HOSTFILE")
GPUS_PER_NODE=${GPUS_PER_NODE:-8}
TOTAL_PROCS=$((NUM_NODES * GPUS_PER_NODE))

echo "============================================"
echo "NCCL AllGather Benchmark"
echo "Nodes: $NUM_NODES | GPUs/node: $GPUS_PER_NODE | Total: $TOTAL_PROCS"
echo "Timestamp: $TIMESTAMP"
echo "============================================"

source /etc/profile.d/nccl-efa.sh

{
  echo "# Timestamp: $TIMESTAMP"
  echo "# Nodes: $NUM_NODES"
  echo "# GPUs per node: $GPUS_PER_NODE"
  echo "# Total GPUs: $TOTAL_PROCS"
  echo "# Hostfile:"
  cat "$HOSTFILE"
  echo
} > "$RESULTS_FILE"

mpirun \
  --hostfile "$HOSTFILE" \
  --np "$TOTAL_PROCS" \
  --bind-to none \
  -x NCCL_SOCKET_IFNAME \
  -x NCCL_IB_DISABLE \
  -x NCCL_IB_HCA \
  -x NCCL_DEBUG \
  -x FI_EFA_USE_DEVICE_RDMA \
  -x FI_PROVIDER \
  -x LD_LIBRARY_PATH \
  all_gather_perf \
    --minbytes 1K \
    --maxbytes 4G \
    --stepfactor 2 \
    --ngpus "$GPUS_PER_NODE" \
    --check 1 \
    --iters 20 \
    --warmup_iters 5 \
  2>&1 | tee -a "$RESULTS_FILE"

echo ""
echo "Results saved: $RESULTS_FILE"

if [ -n "${RESULTS_BUCKET:-}" ]; then
  aws s3 cp "$RESULTS_FILE" "s3://$RESULTS_BUCKET/results/nccl/allgather_${TIMESTAMP}.txt"
  echo "Uploaded to s3://$RESULTS_BUCKET/results/nccl/"
fi
