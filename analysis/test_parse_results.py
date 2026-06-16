
from parse_results import (
    parse_nccl_output,
    parse_osu_bandwidth,
    summarize_nccl,
    _human_size,
)


def test_human_size():
    assert _human_size(1023) == "1023B"
    assert _human_size(1024) == "1.0KB"
    assert _human_size(1536) == "1.5KB"
    assert _human_size(1024 * 1024) == "1.0MB"

def test_human_size_gb():
    assert _human_size(1024**3) == "1.0GB"

def test_human_size_tb():
    assert _human_size(1024**4) == "1.0TB"

def test_nccl_single_result(tmp_path):
    sample = """
1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0
"""
    f = tmp_path / "single.txt"
    f.write_text(sample)

    results = parse_nccl_output(str(f))
    summary = summarize_nccl(results)

    assert summary["total_data_points"] == 1
    assert summary["peak_bus_bw_gbps"] == 11.8

def test_parse_nccl_output(tmp_path):
    sample = """
# size count type redop root time algbw busbw #wrong time algbw busbw
1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0
2048 512 float sum 0 11.0 13.5 12.9 0 10.8 13.7 13.1
"""

    f = tmp_path / "allreduce.txt"
    f.write_text(sample)

    results = parse_nccl_output(str(f))

    assert len(results) == 2

    assert results[0].size_bytes == 1024
    assert results[0].dtype == "float"
    assert results[0].redop == "sum"

    assert results[0].out_of_place_bus_bw_gbps == 11.8
    assert results[1].out_of_place_bus_bw_gbps == 12.9


def test_parse_nccl_empty_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")

    results = parse_nccl_output(str(f))

    assert results == []


def test_parse_osu_bandwidth(tmp_path):
    sample = """
1 100.0
2 200.0
4 400.0
"""

    f = tmp_path / "osu_bw.txt"
    f.write_text(sample)

    results = parse_osu_bandwidth(str(f))

    assert len(results) == 3
    assert results[0] == (1, 100.0)
    assert results[2] == (4, 400.0)


def test_summarize_nccl(tmp_path):
    sample = """
1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0
2048 512 float sum 0 11.0 13.5 12.9 0 10.8 13.7 13.1
4096 1024 float sum 0 12.0 14.5 15.2 0 11.5 14.7 15.0
"""

    f = tmp_path / "allreduce.txt"
    f.write_text(sample)

    results = parse_nccl_output(str(f))
    summary = summarize_nccl(results)

    assert summary["total_data_points"] == 3
    assert summary["peak_bus_bw_gbps"] == 15.2
    assert summary["peak_at_size_bytes"] == 4096
    assert summary["min_latency_us"] == 10.5


def test_ignore_invalid_lines(tmp_path):
    sample = """
garbage
another invalid line
1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0
"""

    f = tmp_path / "mixed.txt"
    f.write_text(sample)

    results = parse_nccl_output(str(f))

    assert len(results) == 1
    assert results[0].size_bytes == 1024
