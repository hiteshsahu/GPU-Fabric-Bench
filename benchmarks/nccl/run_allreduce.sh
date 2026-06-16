#!/bin/bash
# benchmarks/nccl/run_allreduce.sh
# NCCL AllReduce benchmark across all nodes
#
# AllReduce is THE critical collective op in distributed training
# (gradient synchronization after each backward pass)
# This is what NVIDIA interviewers mean when they ask about NCCL performance

set -euo pipefail

HOSTFILE="${HOSTFILE:-$HOME/hostfile}"
RESULTS_DIR="$(dirname "$0")/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="$RESULTS_DIR/allreduce_${TIMESTAMP}.txt"

mkdir -p "$RESULTS_DIR"

# Count total GPUs (8 per p4d node)
NUM_NODES=$(wc -l < "$HOSTFILE")
GPUS_PER_NODE=${GPUS_PER_NODE:-8}
TOTAL_PROCS=$((NUM_NODES * GPUS_PER_NODE))

echo "============================================"
echo "NCCL AllReduce Benchmark"
echo "Nodes: $NUM_NODES | GPUs/node: $GPUS_PER_NODE | Total: $TOTAL_PROCS"
echo "Timestamp: $TIMESTAMP"
echo "============================================"

# Source NCCL environment
source /etc/profile.d/nccl.sh

# Run AllReduce sweep: 1KB to 4GB message sizes
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
  all_reduce_perf \
    --minbytes 1K \
    --maxbytes 4G \
    --stepfactor 2 \
    --ngpus "$GPUS_PER_NODE" \
    --check 1 \
    --iters 20 \
    --warmup_iters 5 \
  2>&1 | tee "$RESULTS_FILE"

echo ""
echo "Results saved: $RESULTS_FILE"

# Upload to S3 if bucket configured
if [ -n "${RESULTS_BUCKET:-}" ]; then
  aws s3 cp "$RESULTS_FILE" "s3://$RESULTS_BUCKET/results/nccl/allreduce_${TIMESTAMP}.txt"
  echo "Uploaded to s3://$RESULTS_BUCKET/results/nccl/"
fi
