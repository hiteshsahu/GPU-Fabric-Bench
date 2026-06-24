# Analysis

Parse, plot, and compare NCCL and OSU benchmark results.

```
analysis/
├── parse_results.py      # parse nccl-tests and OSU output into structured data
├── plot_bandwidth.py     # matplotlib bandwidth curves (busbw vs message size)
├── compare_baseline.py   # measured busbw vs theoretical EFA peak, utilization %
├── test_parse_results.py # pytest unit tests for parse_results.py
└── requirements.txt
```


### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Parsers

###  1. Parse Result: `parse_results.py`

Parses raw benchmark output into structured data and prints a JSON summary.

```bash
# Single NCCL file
python parse_results.py benchmarks/nccl/results/allreduce_20260616.txt

# All files in a directory
python parse_results.py benchmarks/nccl/results/
```

Output:
```json
{
  "total_data_points": 23,
  "peak_bus_bw_gbps": 55.97,
  "peak_at_size_human": "4.0GB",
  "min_latency_us": 28.43
}
Peak bus bandwidth: 55.97 GB/s at 4.0GB
```

> ℹ️ All example outputs on this page are produced from the synthetic test
> fixtures in `tests/fixtures/` (used to exercise the parsers/plotters). They
> are **not** measurements from a real cluster run.

---

### 2. Plot Bandwidth:  `plot_bandwidth.py`

Generates bandwidth-vs-message-size charts as PNG. Overlays multiple files on one chart — useful for comparing Ring vs Tree output from `sweep_msgsize.sh`.

```bash
# Single file
python plot_bandwidth.py benchmarks/nccl/results/allreduce_20260616.txt

# Sweep directory — all .txt files overlaid on one chart
python plot_bandwidth.py benchmarks/nccl/results/sweep_20260616/

# Explicit output path
python plot_bandwidth.py benchmarks/nccl/results/sweep_20260616/ --out charts/comparison.png

# Override the EFA peak reference line (e.g. c5n: 12.5 GB/s)
python plot_bandwidth.py results/allreduce.txt --peak 12.5
```

Saves PNG next to the input file by default. Works headless (no display required on cluster nodes).

---

### 3. Compare vs Theoretical Peak : `compare_baseline.py`



Computes the AllReduce Ring ceiling (`N_nics × nic_bw × 2(N−1)/N`) and prints per-message-size utilization. Flags sizes below 70% with `⚠`.

```bash
# Default: 2 nodes, 4 EFA NICs/node, 50 GB/s/NIC (p4d.24xlarge)
python compare_baseline.py benchmarks/nccl/results/allreduce_20260616.txt

# c5n.18xlarge (1 NIC, 100 Gb/s = 12.5 GB/s)
python compare_baseline.py results/allreduce.txt --nodes 2 --nics-per-node 1 --nic-bw-gbps 12.5

# Compare two runs — prints winner
python compare_baseline.py results/before.txt results/after.txt
```

Output:
```
Theoretical peak busbw : 100.00 GB/s
  2 nodes × 4 EFA NICs × 50.0 GB/s × ring factor 1.000
  Warn threshold : 70%  (70.0 GB/s)

=== allreduce_Ring_Simple ===
      Size  Time(µs)  Measured(GB/s)  Peak(GB/s)  Util%
      ...
    512MB    18432.1           54.62      100.00   54.6  ⚠
      4GB   143891.2           55.97      100.00   56.0  ⚠

Peak busbw : 55.97 GB/s at 4.0GB (56.0% of 100.0 GB/s)
```

---

## Tests

```bash
# Run All Tests
pytest tests -v

# Run specific test
pytest tests/test_parse_results.py -v
```
