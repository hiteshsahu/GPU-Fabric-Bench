#!/usr/bin/env python3
"""
analysis/parse_results.py
Parse nccl-tests output and generate bandwidth curves

Usage:
    python parse_results.py results/allreduce_20240615_120000.txt
    python parse_results.py results/  # parse all files in dir
"""

import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class NCCLResult:
    size_bytes: int
    count: int
    dtype: str
    redop: str
    root: int
    out_of_place_time_us: float
    out_of_place_alg_bw_gbps: float
    out_of_place_bus_bw_gbps: float
    in_place_time_us: float
    in_place_alg_bw_gbps: float
    in_place_bus_bw_gbps: float


def parse_nccl_output(filepath: str) -> list[NCCLResult]:
    """Parse nccl-tests output format."""
    results = []
    # nccl-tests output line pattern:
    # size    count    type    redop    root    time    algbw    busbw    #wrong    time    algbw    busbw
    pattern = re.compile(
        r'^\s*(\d+)\s+(\d+)\s+(\w+)\s+(\w+)\s+(\d+)'
        r'\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)'
        r'\s+\S+'
        r'\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)'
    )

    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                results.append(NCCLResult(
                    size_bytes=int(m.group(1)),
                    count=int(m.group(2)),
                    dtype=m.group(3),
                    redop=m.group(4),
                    root=int(m.group(5)),
                    out_of_place_time_us=float(m.group(6)),
                    out_of_place_alg_bw_gbps=float(m.group(7)),
                    out_of_place_bus_bw_gbps=float(m.group(8)),
                    in_place_time_us=float(m.group(9)),
                    in_place_alg_bw_gbps=float(m.group(10)),
                    in_place_bus_bw_gbps=float(m.group(11)),
                ))

    return results


def parse_osu_bandwidth(filepath: str) -> list[tuple[int, float]]:
    """Parse OSU bandwidth output: (size_bytes, bandwidth_mbps)"""
    results = []
    pattern = re.compile(r'^\s*(\d+)\s+([\d.]+)\s*$')
    with open(filepath) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                results.append((int(m.group(1)), float(m.group(2))))
    return results


def summarize_nccl(results: list[NCCLResult]) -> dict:
    if not results:
        return {}

    bus_bws = [r.out_of_place_bus_bw_gbps for r in results]
    peak_idx = bus_bws.index(max(bus_bws))

    return {
        "total_data_points": len(results),
        "min_size_bytes": results[0].size_bytes,
        "max_size_bytes": results[-1].size_bytes,
        "peak_bus_bw_gbps": max(bus_bws),
        "peak_at_size_bytes": results[peak_idx].size_bytes,
        "peak_at_size_human": _human_size(results[peak_idx].size_bytes),
        "min_latency_us": min(r.out_of_place_time_us for r in results),
    }


def _human_size(n: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return f"{n:.0f}{unit}"
        n //= 1024
    return f"{n:.0f}TB"


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_results.py <file_or_dir>")
        sys.exit(1)

    target = Path(sys.argv[1])
    files = list(target.glob("*.txt")) if target.is_dir() else [target]

    for f in sorted(files):
        print(f"\n{'='*50}")
        print(f"File: {f.name}")

        if "allreduce" in f.name or "nccl" in f.name.lower():
            results = parse_nccl_output(str(f))
            if results:
                summary = summarize_nccl(results)
                print(json.dumps(summary, indent=2))
                print(f"\nPeak bus bandwidth: {summary['peak_bus_bw_gbps']:.2f} GB/s "
                      f"at {summary['peak_at_size_human']}")
            else:
                print("No NCCL results parsed — check file format")

        elif "bandwidth" in f.name or "bw" in f.name:
            bw_data = parse_osu_bandwidth(str(f))
            if bw_data:
                peak = max(bw_data, key=lambda x: x[1])
                print(f"Peak bandwidth: {peak[1]:.2f} MB/s at {_human_size(peak[0])}")
            else:
                print("No OSU bandwidth data parsed")


if __name__ == "__main__":
    main()
