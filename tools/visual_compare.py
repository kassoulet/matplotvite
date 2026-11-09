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
    "broken_barh": "plt.broken_barh([(0, 1), (2, 0.5)], (2, 0.5), colors='blue'); plt.savefig(OUT)",
    "errorbar_markers": "plt.errorbar([1, 2, 3], [1, 4, 9], yerr=[0.5, 1.0, 1.5], fmt='ro', capsize=3); plt.savefig(OUT)",
    "imshow_alpha": "plt.imshow(np.linspace(0, 1, 256).reshape(16, 16), cmap='viridis', alpha=0.5); plt.savefig(OUT)",
    "contour_style": "X, Y = np.meshgrid(np.linspace(-2, 2, 40), np.linspace(-2, 2, 40)); Z = np.exp(-(X**2 + Y**2)); plt.contour(X, Y, Z, levels=5, linewidths=3, alpha=0.6); plt.savefig(OUT)",
}


def compare_images(path_a: pathlib.Path, path_b: pathlib.Path) -> dict[str, float | bool | None]:
    """Per-snippet pixel metrics: RMS error and percent of visibly different pixels."""
    ia, ib = mimg.imread(path_a)[..., :3], mimg.imread(path_b)[..., :3]
    if ia.shape != ib.shape:
        return {"shape_match": False, "rms": None, "mismatch_pct": None}
    diff = np.abs(ia - ib)
    rms = float(np.sqrt(((ia - ib) ** 2).mean()))
    mismatch = float((diff.max(axis=2) > (8.0 / 255.0)).mean() * 100.0)
    return {"shape_match": True, "rms": round(rms, 4),
            "mismatch_pct": round(mismatch, 3)}


def run(name: str, code: str, lib, tag: str, out: pathlib.Path):
    path = out / f"{name}.{tag}.png"
    try:
        lib.close("all")
        # Keep random gallery cases comparable between the two libraries.
        np.random.seed(0)
        exec(code, {"plt": lib, "np": np, "x": x, "OUT": str(path)})
        return path, None
    except Exception as exc:  # noqa: BLE001 - the gallery records every failure
        return None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", nargs="?", default="visual", type=pathlib.Path)
    parser.add_argument("--json", type=pathlib.Path, dest="json_out",
                        help="write per-snippet mismatch metrics here")
    args = parser.parse_args()
    args.outdir.mkdir(exist_ok=True)

    rows = []
    metrics: dict[str, dict[str, object]] = {}
    for name, code in CASES.items():
        (a, ea), (b, eb) = (run(name, code, mpl, "mpl", args.outdir),
                            run(name, code, matplotvite, "rs", args.outdir))
        result: dict[str, object] = {"error": eb}
        if a and b:
            result.update(compare_images(a, b))
        elif ea:
            result["error"] = f"matplotlib: {ea}"
        rms = result.get("rms")
        rms_text = "n/a" if rms is None else f"{rms:.3f}"
        cell = lambda p, e: (f'<img src="{p.name}">' if p
                             else f'<pre style="color:#c00">{html.escape(e or "")}</pre>')
        rows.append(f"<tr><td><b>{name}</b><br>rms: {rms_text}</td>"
                    f"<td>{cell(a, ea)}</td><td>{cell(b, eb)}</td></tr>")
        metrics[name] = result
        print(f"{name:24} {'OK ' if b else 'FAIL'} {rms_text} {eb or ''}".rstrip())
    (args.outdir / "index.html").write_text(
        "<table border=1 cellpadding=6><tr><th>case</th><th>matplotlib</th>"
        "<th>matplotvite</th></tr>" + "".join(rows)
        + "</table><style>img{max-width:480px}</style>", encoding="utf-8")
    if args.json_out:
        args.json_out.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
    return 1 if any(v.get("error") for v in metrics.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
