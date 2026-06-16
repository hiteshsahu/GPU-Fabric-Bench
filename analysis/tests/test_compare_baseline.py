import pytest

from compare_baseline import theoretical_peak_busbw, compare


NCCL_SAMPLE = """\
1024 256 float sum -1 28.4 0.04 0.07 0 27.9 0.04 0.07
16777216 4194304 float sum -1 892.1 18.81 35.27 0 889.4 18.87 35.38
536870912 134217728 float sum -1 18432.0 29.13 54.62 0 18401.0 29.18 54.71
"""


# ── theoretical_peak_busbw ────────────────────────────────────────────────────

def test_peak_p4d_two_nodes():
    # 2 nodes × 4 NICs × 50 GB/s × ring_factor(2) = 2*(2-1)/2 = 1.0 → 200 GB/s
    peak = theoretical_peak_busbw(nodes=2, nics_per_node=4, nic_bw_gbps=50.0)
    assert peak == pytest.approx(200.0)


def test_peak_c5n_two_nodes():
    # c5n.18xlarge: 1 NIC, 100 Gb/s = 12.5 GB/s per direction
    peak = theoretical_peak_busbw(nodes=2, nics_per_node=1, nic_bw_gbps=12.5)
    assert peak == pytest.approx(12.5)


def test_peak_four_nodes():
    # ring_factor(4) = 2*3/4 = 1.5
    peak = theoretical_peak_busbw(nodes=4, nics_per_node=4, nic_bw_gbps=50.0)
    assert peak == pytest.approx(4 * 50.0 * 1.5)


def test_peak_single_node_no_divide_by_zero():
    # 1 node: ring_factor = 1.0 by definition
    peak = theoretical_peak_busbw(nodes=1, nics_per_node=4, nic_bw_gbps=50.0)
    assert peak == pytest.approx(200.0)


def test_peak_approaches_2x_as_nodes_grow():
    # ring_factor → 2 as N → ∞
    large = theoretical_peak_busbw(nodes=1000, nics_per_node=1, nic_bw_gbps=50.0)
    assert large == pytest.approx(2 * 50.0, rel=0.01)


# ── compare ───────────────────────────────────────────────────────────────────

@pytest.fixture
def nccl_file(tmp_path):
    f = tmp_path / "allreduce_Ring_Simple.txt"
    f.write_text(NCCL_SAMPLE)
    return f


def test_compare_returns_one_row_per_data_point(nccl_file):
    rows = compare(str(nccl_file), peak_gbps=200.0)
    assert len(rows) == 3


def test_compare_util_pct_correct(nccl_file):
    rows = compare(str(nccl_file), peak_gbps=200.0)
    # row 0: 0.07 / 200.0 * 100 = 0.035%
    assert rows[0]["util_pct"] == pytest.approx(0.07 / 200.0 * 100)
    # row 2: 54.62 / 200.0 * 100 = 27.31%
    assert rows[2]["util_pct"] == pytest.approx(54.62 / 200.0 * 100)


def test_compare_warn_flag_set_below_threshold(nccl_file):
    rows = compare(str(nccl_file), peak_gbps=200.0)
    # all rows measure << 70% of 200 GB/s, so all should warn
    assert all(r["warn"] for r in rows)


def test_compare_warn_flag_clear_when_above_threshold(tmp_path):
    # Row with 80 GB/s measured vs 100 GB/s peak = 80% util → no warn
    content = "536870912 134217728 float sum -1 1000.0 50.0 80.0 0 1000.0 50.0 80.0\n"
    f = tmp_path / "allreduce_good.txt"
    f.write_text(content)

    rows = compare(str(f), peak_gbps=100.0)
    assert len(rows) == 1
    assert not rows[0]["warn"]


def test_compare_label_defaults_to_filename(nccl_file):
    rows = compare(str(nccl_file), peak_gbps=200.0)
    assert rows[0]["label"] == nccl_file.stem


def test_compare_empty_file_returns_empty(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")
    rows = compare(str(f), peak_gbps=200.0)
    assert rows == []


def test_compare_size_and_time_fields(nccl_file):
    rows = compare(str(nccl_file), peak_gbps=200.0)
    assert rows[0]["size"] == 1024
    assert rows[0]["time_us"] == pytest.approx(28.4)
    assert rows[1]["size"] == 16777216
    assert rows[2]["size"] == 536870912


# ── fixture file tests ────────────────────────────────────────────────────────

def test_compare_allreduce_fixture_row_count(allreduce_file):
    rows = compare(str(allreduce_file), peak_gbps=200.0)
    assert len(rows) == 23


def test_compare_allreduce_fixture_peak_util(allreduce_file):
    # p4d peak: 200 GB/s; measured peak busbw: 55.97 GB/s → ~28% util
    rows = compare(str(allreduce_file), peak_gbps=200.0)
    peak_row = max(rows, key=lambda r: r["measured_gbps"])

    assert peak_row["measured_gbps"] == pytest.approx(55.97)
    assert peak_row["util_pct"] == pytest.approx(55.97 / 200.0 * 100)


def test_compare_allreduce_fixture_realistic_peak(allreduce_file):
    # Compared against realistic single-NIC EFA peak (50 GB/s) → ~100% util at large sizes
    rows = compare(str(allreduce_file), peak_gbps=50.0)
    large_rows = [r for r in rows if r["size"] >= 536870912]

    assert all(r["util_pct"] > 50 for r in large_rows)


def test_compare_allgather_lower_util_than_allreduce(allreduce_file, allgather_file):
    ar_rows = compare(str(allreduce_file), peak_gbps=200.0)
    ag_rows = compare(str(allgather_file), peak_gbps=200.0)

    ar_peak = max(r["measured_gbps"] for r in ar_rows)
    ag_peak = max(r["measured_gbps"] for r in ag_rows)

    assert ag_peak < ar_peak


def test_compare_all_fixture_sizes_ascending(allreduce_file):
    rows = compare(str(allreduce_file), peak_gbps=200.0)
    sizes = [r["size"] for r in rows]
    assert sizes == sorted(sizes)
