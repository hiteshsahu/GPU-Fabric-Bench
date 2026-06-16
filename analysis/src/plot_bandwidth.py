#!/usr/bin/env python3
"""
analysis/plot_bandwidth.py
Plot busbw vs message size from one or more NCCL / OSU result files.

Usage:
    # Single file
    python plot_bandwidth.py benchmarks/nccl/results/allreduce_20260616.txt

    # Compare Ring vs Tree from a sweep directory
    python plot_bandwidth.py benchmarks/nccl/results/sweep_20260616/

    # Multiple explicit files overlaid on one chart
    python plot_bandwidth.py results/allreduce_Ring_Simple.txt results/allreduce_Tree_LL.txt

    # Save to specific path instead of auto-naming next to the input
    python plot_bandwidth.py results/ --out charts/bw.png
"""

import sys
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless — no display required on cluster nodes
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from parse_results import parse_nccl_output, parse_osu_bandwidth, _human_size

# EFA theoretical peaks for reference lines
_EFA_PEAK_GBPS = 50.0          # per direction, per NIC (400 Gb/s / 8)
_EFA_4NIC_PEAK_GBPS = 200.0    # p4d.24xlarge: 4x EFA NICs unidirectional


def _label_from_path(p: Path) -> str:
    name = p.stem
    for prefix in ("allreduce_", "allgather_", "reducescatter_", "latency_", "bandwidth_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name or p.stem


def plot_nccl_files(files: list[Path], out: Path, title: str, peak_gbps: float | None):
    fig, ax = plt.subplots(figsize=(11, 6))

    for f in files:
        results = parse_nccl_output(str(f))
        if not results:
            print(f"  skip {f.name}: no NCCL data")
            continue

        sizes = [r.size_bytes for r in results]
        busbws = [r.out_of_place_bus_bw_gbps for r in results]

        ax.plot(sizes, busbws, marker="o", markersize=4, linewidth=1.5,
                label=_label_from_path(f))

        peak_val = max(busbws)
        peak_sz = sizes[busbws.index(peak_val)]
        ax.annotate(f"{peak_val:.1f}",
                    xy=(peak_sz, peak_val),
                    xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8)

    if peak_gbps:
        ax.axhline(peak_gbps, color="red", linestyle="--", linewidth=1,
                   label=f"EFA peak {peak_gbps:.0f} GB/s")

    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(
        lambda x, _: _human_size(int(x))
    ))
    plt.xticks(rotation=30, ha="right")

    ax.set_xlabel("Message size")
    ax.set_ylabel("Bus bandwidth (GB/s)")
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close(fig)


def plot_osu_file(f: Path, out: Path, title: str):
    data = parse_osu_bandwidth(str(f))
    if not data:
        print(f"  skip {f.name}: no OSU bandwidth data")
        return

    sizes, bws_mbps = zip(*data)
    bws_gbps = [b / 1000 for b in bws_mbps]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(sizes, bws_gbps, marker="o", markersize=4, linewidth=1.5, color="steelblue")

    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(
        lambda x, _: _human_size(int(x))
    ))
    plt.xticks(rotation=30, ha="right")

    ax.set_xlabel("Message size")
    ax.set_ylabel("Bandwidth (GB/s)")
    ax.set_title(title)
    ax.grid(True, which="both", linestyle=":", alpha=0.5)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"Saved: {out}")
    plt.close(fig)


def _collect_files(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        if p.is_dir():
            out.extend(sorted(p.glob("*.txt")))
        else:
            out.append(p)
    return out


def main():
    parser = argparse.ArgumentParser(description="Plot NCCL/OSU bandwidth curves")
    parser.add_argument("inputs", nargs="+", type=Path,
                        help="Result file(s) or directory")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output PNG path (default: next to first input)")
    parser.add_argument("--peak", type=float, default=None,
                        help="Draw a reference line at this GB/s (default: auto from file names)")
    args = parser.parse_args()

    files = _collect_files([Path(p) for p in args.inputs])
    if not files:
        print("No result files found.")
        sys.exit(1)

    nccl_files = [f for f in files if not ("osu" in f.name or "bandwidth" in f.name and "allreduce" not in f.name)]
    osu_files  = [f for f in files if "osu" in f.name or ("bandwidth" in f.name and "allreduce" not in f.name)]

    if nccl_files:
        out = args.out or (nccl_files[0].parent / "bandwidth_curve.png")
        title = "NCCL Bus Bandwidth vs Message Size"
        if len(nccl_files) > 1:
            title += " — algorithm comparison"
        peak = args.peak if args.peak is not None else _EFA_4NIC_PEAK_GBPS
        plot_nccl_files(nccl_files, out, title, peak)

    for f in osu_files:
        out = args.out or f.with_suffix(".png")
        plot_osu_file(f, out, f"OSU Bandwidth — {f.stem}")


if __name__ == "__main__":
    main()
