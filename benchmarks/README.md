# Benchmarks

Two suites — **MPI/OSU** for fabric-level testing (no GPU required), **NCCL** for GPU collective performance.

```
benchmarks/
├── mpi/
│   └── osu_latency_bw.sh    # point-to-point latency + bandwidth over EFA
└── nccl/
    ├── run_allreduce.sh      # AllReduce sweep 1K → 4G
    └── nccl-tuning.md        # env vars, algorithm selection, debug playbook
```

---

## Which suite to run first

| Goal | Suite | Instance | Cost |
|------|-------|----------|------|
| Verify EFA fabric is working, no GPU spend | MPI / OSU | `c5n.18xlarge` | ~$7.76/hr |
| Measure GPU collective performance (LLM training proxy) | NCCL | `p4d.24xlarge` | ~$64/hr |

Run MPI first. If latency is sane there, move to NCCL. A broken NCCL result almost always has a fabric root cause that OSU would have caught cheaper.

---

## Prerequisites

Both suites read a hostfile and an optional `RESULTS_BUCKET` env var:

```bash
# Hostfile — one line per node, slots = GPU count (8 for p4d, 72 for c5n)
cat ~/hostfile
# 10.0.1.10 slots=8
# 10.0.1.11 slots=8

# Optional: upload results to S3
export RESULTS_BUCKET=gpu-fabric-bench-results-<account-id>
```

NCCL also needs EFA env vars (set automatically by user data, or source manually):
```bash
source /etc/profile.d/nccl-efa.sh
```

---

## MPI / OSU — [docs](mpi/README.md)

Tests raw EFA fabric: point-to-point latency and unidirectional bandwidth between two nodes. No GPU involved.

```bash
HOSTFILE=~/hostfile benchmarks/mpi/osu_latency_bw.sh
```

**Pass criteria on EFA (`c5n.18xlarge`):**

| Metric | Expected | Investigate if |
|--------|----------|----------------|
| Latency at 1 B | ~15–25 µs | > 100 µs (TCP fallback) |
| Bandwidth at 1 MB | ~10–12 GB/s | < 5 GB/s |

---

## NCCL — [docs](nccl/README.md)

Runs `all_reduce_perf` across all GPUs on all nodes. This is the direct proxy for gradient sync performance in distributed LLM training.

```bash
HOSTFILE=~/hostfile benchmarks/nccl/run_allreduce.sh
```

**Pass criteria on EFA (`p4d.24xlarge`, 2 nodes / 16 GPUs):**

| Metric | Expected | Investigate if |
|--------|----------|----------------|
| `busbw` at 512 MB | ~40–48 GB/s | < 30 GB/s |
| `#wrong` | `0` | Any non-zero |
| `Avg bus bandwidth` | sweep-dependent | plateau < 40 GB/s |

Results are saved to `benchmarks/nccl/results/` and optionally uploaded to S3.

---

## Tuning

See [nccl/nccl-tuning.md](nccl/nccl-tuning.md) for environment variable reference, Ring vs Tree algorithm selection, EFA plugin setup, and the debugging playbook.
