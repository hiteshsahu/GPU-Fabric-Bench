#!/usr/bin/env python3
"""
analysis/compare_baseline.py
Compare measured NCCL busbw against theoretical fabric peak.

Prints a table showing utilization % at each message size and flags
rows below the warning threshold.

Usage:
    # Single file vs default EFA p4d baseline
    python compare_baseline.py benchmarks/nccl/results/allreduce_20260616.txt

    # Specify node/NIC counts explicitly
    python compare_baseline.py results/allreduce.txt --nodes 4 --nics-per-node 4

    # Compare two runs (e.g. before/after tuning)
    python compare_baseline.py results/before.txt results/after.txt

    # Override peak bandwidth (e.g. for c5n.18xlarge: 100 Gb/s = 12.5 GB/s)
    python compare_baseline.py results/allreduce.txt --nic-bw-gbps 12.5 --nics-per-node 1
"""

import sys
import argparse
from pathlib import Path

from parse_results import parse_nccl_output, _human_size

# Warn when utilization drops below this threshold
_WARN_UTIL_PCT = 70.0

# EFA defaults (p4d.24xlarge)
_DEFAULT_NIC_BW_GBPS   = 50.0   # 400 Gb/s / 8 = 50 GB/s per NIC per direction
_DEFAULT_NICS_PER_NODE = 4
_DEFAULT_NODES         = 2


def theoretical_peak_busbw(nodes: int, nics_per_node: int, nic_bw_gbps: float) -> float:
    """
    AllReduce Ring bus bandwidth ceiling:
        peak_busbw = total_unidirectional_bw * 2(N-1)/N
    where N = total GPU count (all nodes * GPUs per node).

    For the fabric layer (inter-node), total unidirectional bandwidth is
    all EFA NICs across all nodes running in one direction.
    """
    total_nic_bw = nics_per_node * nic_bw_gbps  # per node, one direction
    # Ring factor approaches 1 as N → ∞; for 2 nodes it is exactly 1.0
    n = nodes
    ring_factor = 2 * (n - 1) / n if n > 1 else 1.0
    return total_nic_bw * ring_factor


def compare(filepath: str, peak_gbps: float, label: str | None = None,
            warn_pct: float = _WARN_UTIL_PCT) -> list[dict]:
    results = parse_nccl_output(filepath)
    if not results:
        print(f"  No results parsed from {filepath}")
        return []

    label = label or Path(filepath).stem
    rows = []
    for r in results:
        measured = r.out_of_place_bus_bw_gbps
        util_pct = (measured / peak_gbps * 100) if peak_gbps else 0
        rows.append({
            "label":        label,
            "size":         r.size_bytes,
            "size_human":   _human_size(r.size_bytes),
            "time_us":      r.out_of_place_time_us,
            "measured_gbps": measured,
            "peak_gbps":    peak_gbps,
            "util_pct":     util_pct,
            "warn":         util_pct < warn_pct,
        })
    return rows


def print_table(rows: list[dict], show_label: bool):
    col_label  = 14 if show_label else 0
    col_size   = 10
    col_time   = 10
    col_meas   = 14
    col_peak   = 12
    col_util   = 10

    header = (
        (f"{'Label':<{col_label}}" if show_label else "") +
        f"{'Size':>{col_size}}"
        f"{'Time(µs)':>{col_time}}"
        f"{'Measured(GB/s)':>{col_meas}}"
        f"{'Peak(GB/s)':>{col_peak}}"
        f"{'Util%':>{col_util}}"
        f"  {'':}"
    )
    print(header)
    print("-" * len(header))

    for r in rows:
        warn_flag = " ⚠" if r["warn"] else ""
        line = (
            (f"{r['label']:<{col_label}}" if show_label else "") +
            f"{r['size_human']:>{col_size}}"
            f"{r['time_us']:>{col_time}.1f}"
            f"{r['measured_gbps']:>{col_meas}.2f}"
            f"{r['peak_gbps']:>{col_peak}.2f}"
            f"{r['util_pct']:>{col_util}.1f}"
            f"{warn_flag}"
        )
        print(line)


def print_summary(rows: list[dict], label: str):
    if not rows:
        return
    peak_row  = max(rows, key=lambda r: r["measured_gbps"])
    avg_util  = sum(r["util_pct"] for r in rows) / len(rows)
    warn_rows = [r for r in rows if r["warn"]]

    print(f"\n  {label}")
    print(f"  Peak busbw : {peak_row['measured_gbps']:.2f} GB/s "
          f"at {peak_row['size_human']} "
          f"({peak_row['util_pct']:.1f}% of {peak_row['peak_gbps']:.1f} GB/s)")
    print(f"  Avg util   : {avg_util:.1f}%")
    if warn_rows:
        sizes = ", ".join(r["size_human"] for r in warn_rows[:5])
        print(f"  ⚠  {len(warn_rows)} sizes below {_WARN_UTIL_PCT:.0f}% util: {sizes}")
    else:
        print(f"  ✓  All sizes above {_WARN_UTIL_PCT:.0f}% utilization")


def main():
    parser = argparse.ArgumentParser(description="Compare NCCL busbw against theoretical peak")
    parser.add_argument("inputs", nargs="+", type=Path,
                        help="Result file(s)")
    parser.add_argument("--nodes",          type=int,   default=_DEFAULT_NODES,
                        help=f"Number of nodes (default: {_DEFAULT_NODES})")
    parser.add_argument("--nics-per-node",  type=int,   default=_DEFAULT_NICS_PER_NODE,
                        help=f"EFA NICs per node (default: {_DEFAULT_NICS_PER_NODE})")
    parser.add_argument("--nic-bw-gbps",    type=float, default=_DEFAULT_NIC_BW_GBPS,
                        help=f"Per-NIC unidirectional bandwidth GB/s (default: {_DEFAULT_NIC_BW_GBPS})")
    parser.add_argument("--warn-pct",       type=float, default=_WARN_UTIL_PCT,
                        help=f"Warn threshold %% (default: {_WARN_UTIL_PCT})")
    args = parser.parse_args()

    warn_pct = args.warn_pct
    peak = theoretical_peak_busbw(args.nodes, args.nics_per_node, args.nic_bw_gbps)

    print(f"\nTheoretical peak busbw : {peak:.2f} GB/s")
    print(f"  {args.nodes} nodes × {args.nics_per_node} EFA NICs × {args.nic_bw_gbps:.1f} GB/s "
          f"× ring factor {2*(args.nodes-1)/args.nodes:.3f}")
    print(f"  Warn threshold : {warn_pct:.0f}%  ({peak * warn_pct / 100:.1f} GB/s)\n")

    all_rows = []
    for path in args.inputs:
        rows = compare(str(path), peak, warn_pct=warn_pct)
        all_rows.append((path.stem, rows))

    show_label = len(all_rows) > 1

    for label, rows in all_rows:
        if rows:
            print(f"\n=== {label} ===")
            print_table(rows, show_label=False)
            print_summary(rows, label)

    if show_label:
        best = max(all_rows, key=lambda x: max((r["measured_gbps"] for r in x[1]), default=0))
        print(f"\n→ Best: {best[0]}")


if __name__ == "__main__":
    main()
