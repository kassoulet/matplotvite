"""Render each case with matplotlib and matplotvite, write a side-by-side HTML gallery.

usage: python tools/visual_compare.py [outdir=visual] [--json metrics.json]
Add cases to CASES: code runs with `plt` and `np` bound to either library.
Unsupported features show up as failures (AttributeError/TypeError) in the gallery.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import tempfile

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as mpl
import matplotlib.image as mimg
import matplotvite

x = np.linspace(0, 10, 200)
CASES = {
    "lines_legend": """
plt.figure(figsize=(6.4, 4.8))
plt.plot(x, np.sin(x), label="sin", color="red")
plt.plot(x, np.cos(x), label="cos")
plt.xlabel("x"); plt.ylabel("y"); plt.title("Demo"); plt.legend()
plt.savefig(OUT)""",
    "single_line_default": "plt.plot(x, x**2); plt.savefig(OUT)",
    "y_only": "plt.plot([3, 1, 2]); plt.savefig(OUT)",
    "linestyle": "plt.plot(x, x, linestyle='--'); plt.savefig(OUT)",
    "scatter": "plt.scatter(x, np.sin(x)); plt.savefig(OUT)",
    "subplots": "fig, ax = plt.subplots(); ax.plot(x, x); ax.set_xlim(0, 5); fig.savefig(OUT)",
    "step_pre": "plt.step(x, np.sin(x), where='pre'); plt.savefig(OUT)",
    "step_post": "plt.step(x, np.sin(x), where='post'); plt.savefig(OUT)",
    "step_mid": "plt.step(x, np.sin(x), where='mid'); plt.savefig(OUT)",
    "stairs": "plt.stairs([1, 2, 3], edges=[0, 1, 2, 3], fill=True); plt.savefig(OUT)",
    "hist_step": "plt.hist(np.random.randn(100), bins=10, histtype='step'); plt.savefig(OUT)",
    "hist_stepfilled": "plt.hist(np.random.randn(100), bins=10, histtype='stepfilled'); plt.savefig(OUT)",
    "broken_barh": "plt.broken_barh([(0, 1), (2, 0.5)], (2, 0.5), facecolors='blue'); plt.savefig(OUT)",
    "errorbar_markers": "plt.errorbar([1, 2, 3], [1, 4, 9], yerr=[0.5, 1.0, 1.5], fmt='ro', capsize=3); plt.savefig(OUT)",
    "imshow_alpha": "plt.imshow(np.linspace(0, 1, 256).reshape(16, 16), cmap='viridis', alpha=0.5); plt.savefig(OUT)",
    "contour_style": "X, Y = np.meshgrid(np.linspace(-2, 2, 40), np.linspace(-2, 2, 40)); Z = np.exp(-(X**2 + Y**2)); plt.contour(X, Y, Z, levels=5, linewidths=3, alpha=0.6); plt.savefig(OUT)",
}


_VECTOR_SUFFIXES = (".pdf", ".svg", ".eps")
_RASTER_CACHE = pathlib.Path(tempfile.mkdtemp(prefix="matplotvite-compare-"))


def rasterise(path: pathlib.Path, like: pathlib.Path) -> pathlib.Path:
    """Return a PNG version of a vector baseline, sized like `like`.

    Matplotlib keeps some baselines as PDF/SVG (and a few EPS); those cannot be
    read by `matplotlib.image.imread`. Convert them with an optional converter at
    the rendered image's pixel size so the same RMS metric still applies.
    `like` may be a raster image or another vector file.
    """
    if path.suffix.lower() not in _VECTOR_SUFFIXES:
        return path
    if like.suffix.lower() in _VECTOR_SUFFIXES:
        like = _rasterise_vector(like, _RASTER_CACHE / f"like-{like.stem}.png")
    height, width = mimg.imread(like).shape[:2]
    target = _RASTER_CACHE / f"{path.parent.name}-{path.stem}.png"
    return _rasterise_vector(path, target, width, height)


def _rasterise_vector(path: pathlib.Path, target: pathlib.Path,
                      width: int | None = None,
                      height: int | None = None) -> pathlib.Path:
    """Convert a PDF/SVG/EPS file to PNG, optionally at a fixed pixel size."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pypdfium2 as pdfium
        page = pdfium.PdfDocument(str(path))[0]
        page_width, _ = page.get_size()
        scale = 1.0 if width is None else width / page_width
        page.render(scale=scale).to_pil().save(target)
    elif suffix == ".svg":
        import cairosvg
        cairosvg.svg2png(url=str(path), write_to=str(target),
                         output_width=width, output_height=height)
    else:
        from PIL import Image
        with Image.open(path) as image:  # EPS needs Ghostscript on PATH
            out = image.convert("RGB")
            if width is not None:
                out = out.resize((width, height))
            out.save(target)
    if width is not None:
        # Converters round page sizes differently; the pixel metric needs equal shapes.
        from PIL import Image
        with Image.open(target) as image:
            if image.size != (width, height):
                image.resize((width, height)).save(target)
    return target


def compare_images(path_a: pathlib.Path, path_b: pathlib.Path) -> dict[str, float | bool | None]:
    """Per-snippet pixel metrics: RMS error and percent of visibly different pixels."""
    # Either side may be a vector file (matplotlib baselines, or both sides
    # when --format svg compares the two exporters). Rasterise one side first
    # so the other can be sized to it.
    a = rasterise(path_a, path_b)
    b = rasterise(path_b, a)
    ia, ib = mimg.imread(a)[..., :3], mimg.imread(b)[..., :3]
    if ia.shape != ib.shape:
        return {"shape_match": False, "rms": None, "mismatch_pct": None}
    diff = np.abs(ia - ib)
    rms = float(np.sqrt(((ia - ib) ** 2).mean()))
    mismatch = float((diff.max(axis=2) > (8.0 / 255.0)).mean() * 100.0)
    return {"shape_match": True, "rms": round(rms, 4),
            "mismatch_pct": round(mismatch, 3)}


def run(name: str, code: str, lib, tag: str, out: pathlib.Path, fmt: str = "png"):
    path = out / f"{name}.{tag}.{fmt}"
    try:
        lib.close("all")
        # Keep random gallery cases comparable between the two libraries.
        np.random.seed(0)
        exec(code, {"plt": lib, "np": np, "x": x, "OUT": str(path)})
        return path, None
    except Exception as exc:  # noqa: BLE001 - the gallery records every failure
        return None, f"{type(exc).__name__}: {exc}"


def _row(name: str, result: dict[str, object], a: pathlib.Path | None,
         ea: str | None, b: pathlib.Path | None, eb: str | None) -> str:
    rms = result.get("rms")
    rms_text = "n/a" if rms is None else f"{float(rms):.3f}"
    pct = result.get("mismatch_pct")
    pct_text = "n/a" if pct is None else f"{float(pct):.1f}%"

    def cell(path: pathlib.Path | None, error: str | None) -> str:
        if path:
            return f'<img src="{html.escape(path.name)}" loading="lazy">'
        return f'<pre class="error">{html.escape(error or "")}</pre>'

    return (f"<tr><td class=\"case\"><b>{html.escape(name)}</b>"
            f"<span>rms {rms_text} · {pct_text} different</span></td>"
            f"<td>{cell(a, ea)}</td><td>{cell(b, eb)}</td></tr>")


def _page(title: str, subtitle: str, rows: list[str],
          metrics: dict[str, dict[str, object]], fmt: str) -> str:
    failures = sum(1 for result in metrics.values() if result.get("error"))
    rms_values = [float(result["rms"]) for result in metrics.values()
                  if result.get("rms") is not None]
    median = sorted(rms_values)[len(rms_values) // 2] if rms_values else None
    summary = f"{len(metrics)} cases · {failures} failures"
    if median is not None:
        summary += f" · median rms {median:.3f}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ margin: 0; padding: 2rem clamp(1rem, 4vw, 3rem); font: 15px/1.5 system-ui, sans-serif; }}
    h1 {{ font-size: 1.6rem; margin: 0 0 .35rem; }}
    .subtitle {{ color: #666; margin: 0 0 .5rem; max-width: 70ch; }}
    .summary {{ font: 12px/1.5 ui-monospace, monospace; color: #666; margin: 0 0 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d8d8d8; padding: .6rem; text-align: left; vertical-align: top; }}
    th {{ font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: #666; }}
    td.case {{ font: 12px/1.6 ui-monospace, monospace; white-space: nowrap; width: 1%; }}
    td.case span {{ display: block; color: #666; }}
    img {{ display: block; width: 100%; max-width: 460px; height: auto; background: #fff; }}
    .error {{ color: #b00020; white-space: pre-wrap; max-width: 46ch; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="subtitle">{html.escape(subtitle)}</p>
  <p class="summary">{html.escape(summary)}</p>
  <table>
    <thead><tr><th>case</th><th>matplotlib {fmt.upper()}</th><th>matplotvite {fmt.upper()}</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", nargs="?", default="visual", type=pathlib.Path)
    parser.add_argument("--json", type=pathlib.Path, dest="json_out",
                        help="write per-snippet mismatch metrics here "
                             "(default: <outdir>/metrics.json)")
    parser.add_argument("--format", choices=("png", "svg"), default="png",
                        help="save both libraries with this format before comparing "
                             "(svg exercises the vector export path)")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    metrics: dict[str, dict[str, object]] = {}
    for name, code in CASES.items():
        (a, ea), (b, eb) = (run(name, code, mpl, "mpl", args.outdir, args.format),
                            run(name, code, matplotvite, "rs", args.outdir, args.format))
        result: dict[str, object] = {"error": eb}
        if a and b:
            result.update(compare_images(a, b))
        elif ea:
            result["error"] = f"matplotlib: {ea}"
        rows.append(_row(name, result, a, ea, b, eb))
        metrics[name] = result
        print(f"{name:24} {'OK ' if b else 'FAIL'} {result.get('rms')} {eb or ''}".rstrip())

    noun = "SVG export" if args.format == "svg" else "rendered output"
    page = _page(
        f"Matplotlib vs matplotvite — {noun}",
        "The same script runs against both libraries; each image is the file the "
        f"library wrote in {args.format.upper()} format. RMS and differing-pixel "
        "share are measured after rasterising the pair to a common size.",
        rows, metrics, args.format)
    (args.outdir / "index.html").write_text(page, encoding="utf-8")
    json_out = args.json_out or (args.outdir / "metrics.json")
    json_out.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    return 1 if any(v.get("error") for v in metrics.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
