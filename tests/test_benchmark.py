"""Tests validating the benchmark suite and data integrity."""

import json
from pathlib import Path
from tools.benchmark import measure_callable
from tools.build_pages import build_pages

ROOT = Path(__file__).resolve().parent.parent


def test_measure_callable():
    """Verify that measure_callable measures execution time correctly."""
    counter = 0

    def sample_work():
        nonlocal counter
        counter += 1

    elapsed = measure_callable(sample_work, iters=10, warmup=2)
    assert elapsed >= 0.0
    assert counter == 12


def test_benchmark_data_structure():
    """Verify the structure and contents of the benchmark reference data."""
    data_path = ROOT / "tools" / "benchmarks_data.json"
    assert data_path.exists(), "tools/benchmarks_data.json not found"

    data = json.loads(data_path.read_text(encoding="utf-8"))
    assert "system" in data
    assert "results" in data

    sys_info = data["system"]
    assert "os" in sys_info
    assert "python_version" in sys_info
    assert "plt_rs_version" in sys_info

    results = data["results"]
    assert len(results) >= 5

    for item in results:
        assert "name" in item
        assert "rs_ms" in item
        assert "mpl_ms" in item
        assert "speedup" in item
        assert item["rs_ms"] > 0
        assert item["mpl_ms"] > 0
        assert item["speedup"] >= 1.0, f"Expected speedup >= 1.0 for {item['name']}"


def test_build_pages_generation(tmp_path):
    """Verify that build_pages generates both the gallery and the benchmark page."""
    build_pages(tmp_path)

    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "benchmarks.html").exists()
    assert (tmp_path / "benchmark_scaling.png").exists()
    assert (tmp_path / ".nojekyll").exists()

    bench_html = (tmp_path / "benchmarks.html").read_text(encoding="utf-8")
    assert "Engineered for Extreme Speed" in bench_html
    assert "Head-to-Head Latency Comparison" in bench_html
    assert "FASTER" in bench_html
