import sys
import pytest
from pathlib import Path

# Make analysis/ importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def allreduce_file():
    return FIXTURES / "allreduce_sample.txt"


@pytest.fixture
def allgather_file():
    return FIXTURES / "allgather_sample.txt"


@pytest.fixture
def osu_latency_file():
    return FIXTURES / "osu_latency_sample.txt"


@pytest.fixture
def osu_bandwidth_file():
    return FIXTURES / "osu_bandwidth_sample.txt"
