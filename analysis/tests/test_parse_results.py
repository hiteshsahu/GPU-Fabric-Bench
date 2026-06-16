from parse_results import (
    parse_nccl_output,
    parse_osu_bandwidth,
    summarize_nccl,
    _human_size,
)


# ── _human_size ───────────────────────────────────────────────────────────────

def test_human_size():
    assert _human_size(1023) == "1023B"
    assert _human_size(1024) == "1.0KB"
    assert _human_size(1536) == "1.5KB"
    assert _human_size(1024 * 1024) == "1.0MB"

def test_human_size_gb():
    assert _human_size(1024**3) == "1.0GB"

def test_human_size_tb():
    assert _human_size(1024**4) == "1.0TB"


# ── parse_nccl_output — inline ────────────────────────────────────────────────

def test_nccl_single_result(tmp_path):
    f = tmp_path / "single.txt"
    f.write_text("1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0\n")

    results = parse_nccl_output(str(f))
    summary = summarize_nccl(results)

    assert summary["total_data_points"] == 1
    assert summary["peak_bus_bw_gbps"] == 11.8


def test_parse_nccl_header_comments_ignored(tmp_path):
    sample = (
        "# size count type redop root time algbw busbw #wrong time algbw busbw\n"
        "1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0\n"
        "2048 512 float sum 0 11.0 13.5 12.9 0 10.8 13.7 13.1\n"
    )
    f = tmp_path / "allreduce.txt"
    f.write_text(sample)

    results = parse_nccl_output(str(f))

    assert len(results) == 2
    assert results[0].size_bytes == 1024
    assert results[0].dtype == "float"
    assert results[0].redop == "sum"
    assert results[0].out_of_place_bus_bw_gbps == 11.8
    assert results[1].out_of_place_bus_bw_gbps == 12.9


def test_parse_nccl_negative_root(tmp_path):
    # nccl-tests uses -1 for non-rooted collectives (AllReduce, AllGather)
    f = tmp_path / "allreduce.txt"
    f.write_text("536870912 134217728 float sum -1 18432.0 29.13 54.62 0 18401.0 29.18 54.71\n")

    results = parse_nccl_output(str(f))

    assert len(results) == 1
    assert results[0].root == -1
    assert results[0].out_of_place_bus_bw_gbps == 54.62


def test_parse_nccl_empty_file(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")
    assert parse_nccl_output(str(f)) == []


def test_ignore_invalid_lines(tmp_path):
    sample = (
        "garbage\n"
        "another invalid line\n"
        "1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0\n"
    )
    f = tmp_path / "mixed.txt"
    f.write_text(sample)

    results = parse_nccl_output(str(f))

    assert len(results) == 1
    assert results[0].size_bytes == 1024


# ── parse_nccl_output — fixture files ────────────────────────────────────────

def test_parse_allreduce_fixture(allreduce_file):
    results = parse_nccl_output(str(allreduce_file))

    assert len(results) == 23
    assert results[0].size_bytes == 1024
    assert results[-1].size_bytes == 4294967296
    assert all(r.dtype == "float" for r in results)
    assert all(r.redop == "sum" for r in results)
    assert all(r.root == -1 for r in results)


def test_allreduce_fixture_peak_busbw(allreduce_file):
    results = parse_nccl_output(str(allreduce_file))
    summary = summarize_nccl(results)

    assert summary["peak_bus_bw_gbps"] == 55.97
    assert summary["peak_at_size_human"] == "4.0GB"
    assert summary["min_latency_us"] == 28.43


def test_parse_allgather_fixture(allgather_file):
    results = parse_nccl_output(str(allgather_file))

    assert len(results) == 23
    assert results[0].size_bytes == 1024
    # AllGather has no reduction op
    assert all(r.redop == "none" for r in results)


def test_allgather_busbw_lower_than_allreduce(allreduce_file, allgather_file):
    ar = summarize_nccl(parse_nccl_output(str(allreduce_file)))
    ag = summarize_nccl(parse_nccl_output(str(allgather_file)))

    # AllGather busbw < AllReduce busbw — no reduction means lower bus utilization
    assert ag["peak_bus_bw_gbps"] < ar["peak_bus_bw_gbps"]


# ── parse_osu_bandwidth — inline ──────────────────────────────────────────────

def test_parse_osu_bandwidth_inline(tmp_path):
    f = tmp_path / "osu_bw.txt"
    f.write_text("1 100.0\n2 200.0\n4 400.0\n")

    results = parse_osu_bandwidth(str(f))

    assert len(results) == 3
    assert results[0] == (1, 100.0)
    assert results[2] == (4, 400.0)


# ── parse_osu_bandwidth — fixture files ──────────────────────────────────────

def test_parse_osu_bandwidth_fixture(osu_bandwidth_file):
    results = parse_osu_bandwidth(str(osu_bandwidth_file))

    assert len(results) == 23
    assert results[0][0] == 1           # smallest size
    assert results[-1][0] == 4194304    # largest size
    # bandwidth increases with message size up to saturation
    assert results[-1][1] > results[0][1]


def test_osu_bandwidth_fixture_peak(osu_bandwidth_file):
    results = parse_osu_bandwidth(str(osu_bandwidth_file))
    peak = max(results, key=lambda x: x[1])

    # peak should be at a large message size (saturation)
    assert peak[0] >= 1048576
    # ~11 GB/s on c5n.18xlarge EFA (100 Gb/s link)
    assert peak[1] > 10_000_000  # MB/s


def test_parse_osu_latency_fixture_skips_header(osu_latency_file):
    # osu_latency output uses same two-column format as osu_bandwidth
    results = parse_osu_bandwidth(str(osu_latency_file))

    assert len(results) == 22
    assert results[0] == (0, 17.32)     # 0-byte message, ~17 µs on EFA
    assert results[-1][0] == 1048576


# ── summarize_nccl ────────────────────────────────────────────────────────────

def test_summarize_nccl_inline(tmp_path):
    sample = (
        "1024 256 float sum 0 10.5 12.3 11.8 0 10.1 12.7 12.0\n"
        "2048 512 float sum 0 11.0 13.5 12.9 0 10.8 13.7 13.1\n"
        "4096 1024 float sum 0 12.0 14.5 15.2 0 11.5 14.7 15.0\n"
    )
    f = tmp_path / "allreduce.txt"
    f.write_text(sample)

    summary = summarize_nccl(parse_nccl_output(str(f)))

    assert summary["total_data_points"] == 3
    assert summary["peak_bus_bw_gbps"] == 15.2
    assert summary["peak_at_size_bytes"] == 4096
    assert summary["min_latency_us"] == 10.5


def test_summarize_nccl_empty():
    assert summarize_nccl([]) == {}
