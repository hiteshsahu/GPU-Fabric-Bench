from pathlib import Path
import pytest

from plot_bandwidth import plot_nccl_files, plot_osu_file, _label_from_path, _collect_files


NCCL_SAMPLE = """\
1024 256 float sum -1 28.4 0.04 0.07 0 27.9 0.04 0.07
16777216 4194304 float sum -1 892.1 18.81 35.27 0 889.4 18.87 35.38
536870912 134217728 float sum -1 18432.0 29.13 54.62 0 18401.0 29.18 54.71
"""

OSU_SAMPLE = """\
# OSU MPI Bandwidth Test
# Size      Bandwidth (MB/s)
1           100.0
1024        5000.0
1048576     11000.0
"""


@pytest.fixture
def nccl_file(tmp_path):
    f = tmp_path / "allreduce_20260616.txt"
    f.write_text(NCCL_SAMPLE)
    return f


@pytest.fixture
def osu_file(tmp_path):
    f = tmp_path / "osu_bandwidth_20260616.txt"
    f.write_text(OSU_SAMPLE)
    return f


def test_plot_nccl_creates_png(nccl_file, tmp_path):
    out = tmp_path / "out.png"
    plot_nccl_files([nccl_file], out, title="Test", peak_gbps=50.0)
    assert out.exists()
    assert out.stat().st_size > 0


def test_plot_nccl_multiple_files(tmp_path):
    f1 = tmp_path / "allreduce_Ring_Simple.txt"
    f2 = tmp_path / "allreduce_Tree_LL.txt"
    f1.write_text(NCCL_SAMPLE)
    f2.write_text(NCCL_SAMPLE)
    out = tmp_path / "comparison.png"

    plot_nccl_files([f1, f2], out, title="Ring vs Tree", peak_gbps=100.0)
    assert out.exists()


def test_plot_nccl_no_peak_line(nccl_file, tmp_path):
    out = tmp_path / "out.png"
    plot_nccl_files([nccl_file], out, title="No peak", peak_gbps=None)
    assert out.exists()


def test_plot_nccl_empty_file(tmp_path):
    empty = tmp_path / "allreduce_empty.txt"
    empty.write_text("")
    out = tmp_path / "out.png"
    # should not raise, just print a skip message
    plot_nccl_files([empty], out, title="Empty", peak_gbps=50.0)


def test_plot_osu_creates_png(osu_file, tmp_path):
    out = tmp_path / "osu.png"
    plot_osu_file(osu_file, out, title="OSU BW")
    assert out.exists()
    assert out.stat().st_size > 0


def test_plot_osu_empty_file(tmp_path):
    empty = tmp_path / "osu_bw_empty.txt"
    empty.write_text("")
    out = tmp_path / "osu.png"
    plot_osu_file(empty, out, title="Empty OSU")
    assert not out.exists()


def test_label_from_path_strips_prefix():
    assert _label_from_path(Path("allreduce_Ring_Simple.txt")) == "Ring_Simple"
    assert _label_from_path(Path("allgather_20260616.txt")) == "20260616"
    assert _label_from_path(Path("custom.txt")) == "custom"


def test_collect_files_from_dir(tmp_path):
    (tmp_path / "a.txt").write_text(NCCL_SAMPLE)
    (tmp_path / "b.txt").write_text(NCCL_SAMPLE)
    (tmp_path / "skip.csv").write_text("")

    files = _collect_files([tmp_path])
    assert len(files) == 2
    assert all(f.suffix == ".txt" for f in files)


def test_collect_files_explicit(tmp_path):
    f = tmp_path / "allreduce.txt"
    f.write_text(NCCL_SAMPLE)
    files = _collect_files([f])
    assert files == [f]


# ── fixture file tests ────────────────────────────────────────────────────────

def test_plot_allreduce_fixture(allreduce_file, tmp_path):
    out = tmp_path / "allreduce.png"
    plot_nccl_files([allreduce_file], out, title="AllReduce fixture", peak_gbps=200.0)
    assert out.exists()
    assert out.stat().st_size > 0


def test_plot_allgather_fixture(allgather_file, tmp_path):
    out = tmp_path / "allgather.png"
    plot_nccl_files([allgather_file], out, title="AllGather fixture", peak_gbps=200.0)
    assert out.exists()


def test_plot_allreduce_vs_allgather(allreduce_file, allgather_file, tmp_path):
    out = tmp_path / "comparison.png"
    plot_nccl_files(
        [allreduce_file, allgather_file], out,
        title="AllReduce vs AllGather", peak_gbps=200.0
    )
    assert out.exists()


def test_plot_osu_bandwidth_fixture(osu_bandwidth_file, tmp_path):
    out = tmp_path / "osu_bw.png"
    plot_osu_file(osu_bandwidth_file, out, title="OSU bandwidth fixture")
    assert out.exists()


def test_collect_files_from_fixtures_dir(fixtures_dir):
    files = _collect_files([fixtures_dir])
    names = {f.name for f in files}
    assert "allreduce_sample.txt" in names
    assert "allgather_sample.txt" in names
    assert "osu_bandwidth_sample.txt" in names
    assert "osu_latency_sample.txt" in names
