"""Tests validating the benchmark suite and data integrity."""

import json
from pathlib import Path
from tools.benchmark import measure_callable
from tools.build_pages import build_pages
from tools.criterion_guard import load_estimates

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


def test_criterion_estimates_are_read_from_median(tmp_path):
    case = tmp_path / "rasterize_svg" / "640x480" / "new"
    case.mkdir(parents=True)
    (case / "estimates.json").write_text(
        '{"median": {"point_estimate": 123456.0}}', encoding="utf-8"
    )
    assert load_estimates(tmp_path) == {"rasterize_svg/640x480": 123456.0}


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
    assert "matplotvite_version" in sys_info

    results = data["results"]
    assert len(results) >= 5

    for item in results:
        assert "name" in item
        assert "rs_ms" in item
        assert "mpl_ms" in item
        assert "speedup" in item
        assert item["rs_ms"] > 0
        assert item["mpl_ms"] > 0
        assert item["speedup"] > 0, f"Expected a positive speedup for {item['name']}"


def test_build_pages_generation(tmp_path):
    """Verify that build_pages generates both the gallery and the benchmark page."""
    build_pages(tmp_path)

    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "benchmarks.html").exists()
    assert (tmp_path / "benchmark_scaling.png").exists()
    assert (tmp_path / ".nojekyll").exists()

    gallery_html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Examples" in gallery_html
    assert "Matplotlib-compatible" in gallery_html
    assert "histogram_density.png" in gallery_html

    bench_html = (tmp_path / "benchmarks.html").read_text(encoding="utf-8")
    assert "Static rendering benchmarks" in bench_html
    assert "End-to-end latency" in bench_html
    assert "faster" in bench_html
    assert "Engineered for Extreme Speed" not in bench_html

    # Every Prism asset must carry an SRI digest so a tampered CDN file is rejected.
    for page in ("index.html", "comparison.html"):
        page_html = (tmp_path / page).read_text(encoding="utf-8")
        assert page_html.count('integrity="sha384-') == 3
        assert page_html.count('crossorigin="anonymous"') == 3
        assert "cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/" in page_html
