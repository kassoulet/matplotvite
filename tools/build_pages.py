#!/usr/bin/env python3
"""Build the static documentation and benchmark site for matplotvite."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# The in-tree sources are only a fallback: when a matplotvite is installed (the
# wheel test job installs one) it must win, because the checkout has no compiled
# extension to import from `python/`.
if importlib.util.find_spec("matplotvite") is None and str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))


def _check_compiled_extension():
    """Refuse to let an in-tree extension silently shadow a newer Rust build."""
    extensions = [
        path
        for pattern in ("_core*.so", "_core*.pyd", "_core*.dylib")
        for path in (ROOT / "python" / "matplotvite").glob(pattern)
    ]
    if not extensions:
        return
    newest_input = max(
        [
            path
            for path in [ROOT / "Cargo.toml", ROOT / "Cargo.lock",
                         *list((ROOT / "src").rglob("*.rs")),
                         *list((ROOT / "assets").rglob("*"))]
            if path.is_file()
        ],
        key=lambda path: path.stat().st_mtime,
        default=None,
    )
    if newest_input is None:
        return
    newest_mtime = max(path.stat().st_mtime for path in extensions)
    if newest_mtime < newest_input.stat().st_mtime:
        raise SystemExit(
            "stale compiled extension in python/matplotvite; run "
            "`maturin develop --release` before building pages"
        )


if __name__ == "__main__":
    _check_compiled_extension()


from tools.gallery_render import (
    format_bytes,
    load_render_data,
    render_gallery,
)
from tools.pages_benchmarks import generate_benchmarks_html
from tools.pages_common import coverage_stats
from tools.pages_gallery import (
    generate_comparison_html,
    generate_galleries_html,
    generate_gallery_html,
    generate_svg_comparison_html,
)
from tools.pages_karios import write_karios_page


def write_galleries_page(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_page = generate_svg_comparison_html(out_dir)
    if svg_page is not None:
        svg_path = out_dir / "svg-comparison.html"
        svg_path.write_text(svg_page, encoding="utf-8")
        print(f"Wrote SVG comparison page -> {svg_path}")
    path = out_dir / "galleries.html"
    body = generate_galleries_html(out_dir)
    path.write_text(body, encoding="utf-8")
    return path


def build_pages(out_dir: Path) -> None:
    """Render the site assets and write every HTML page into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    font_dir = out_dir / "assets" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    for font_name in (
        "Geist-Regular.ttf",
        "GeistSerif-Regular.ttf",
        "GeistMono-Regular.ttf",
        "LICENSE_GEIST_OFL.txt",
    ):
        shutil.copyfile(ROOT / "assets" / "fonts" / font_name, font_dir / font_name)
    render_gallery(out_dir)
    build_pages_from_data(out_dir)


def build_pages_from_data(out_dir: Path,
                          data: dict[str, object] | None = None) -> None:
    """Write the HTML pages from the metadata left by the render step."""
    if data is None:
        data = load_render_data(out_dir)
    samples_info: list[dict[str, object]] = list(data["samples"])  # type: ignore[arg-type]

    gallery_html = generate_gallery_html(samples_info, coverage_stats(out_dir))
    index_path = out_dir / "index.html"
    index_path.write_text(gallery_html, encoding="utf-8")
    gallery_size = format_bytes(len(gallery_html.encode("utf-8")))
    print(f"Wrote gallery page -> {index_path} ({gallery_size})")

    comparison_html = generate_comparison_html(samples_info, bool(data["mpl_available"]))
    comparison_path = out_dir / "comparison.html"
    comparison_path.write_text(comparison_html, encoding="utf-8")
    comparison_size = format_bytes(len(comparison_html.encode("utf-8")))
    print(f"Wrote comparison page -> {comparison_path} ({comparison_size})")

    bench_data = data["benchmark"]
    benchmarks_html = generate_benchmarks_html(bench_data)  # type: ignore[arg-type]
    bench_path = out_dir / "benchmarks.html"
    bench_path.write_text(benchmarks_html, encoding="utf-8")
    print(f"Wrote benchmarks page -> {bench_path} ({format_bytes(len(benchmarks_html.encode('utf-8')))})")

    galleries_path = write_galleries_page(out_dir)
    print(f"Wrote galleries page -> {galleries_path}")

    karios_path = write_karios_page(out_dir)
    print(f"Wrote KARIOS page -> {karios_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Matplotvite example gallery and benchmark site.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="Output directory (default: dist)")
    parser.add_argument("--render-only", action="store_true",
                        help="Only render images and samples.json (see tools/gallery_render.py)")
    parser.add_argument("--html-only", action="store_true",
                        help="Only rewrite the HTML from an existing samples.json")
    parser.add_argument("--galleries-only", action="store_true",
                        help="Only refresh galleries.html from existing manifests")
    args = parser.parse_args()
    modes = [args.render_only, args.html_only, args.galleries_only]
    if sum(modes) > 1:
        parser.error("--render-only, --html-only and --galleries-only are mutually exclusive")
    if args.render_only:
        render_gallery(args.out)
    elif args.html_only:
        build_pages_from_data(args.out)
    elif args.galleries_only:
        print(f"Wrote galleries page -> {write_galleries_page(args.out)}")
    else:
        build_pages(args.out)


if __name__ == "__main__":
    main()
