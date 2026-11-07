"""Render each case with matplotlib and plt_rs, write a side-by-side HTML gallery.

usage: python tools/visual_compare.py [outdir=visual]   (dev tool: needs matplotlib)
Add cases to CASES: code runs with `plt` and `np` bound to either library.
Unsupported features show up as failures (AttributeError/TypeError) in the gallery.
"""
import html, pathlib, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as mpl
import matplotlib.image as mimg
import plt_rs

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
}

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "visual"); out.mkdir(exist_ok=True)

def run(name, code, lib, tag):
    path = out / f"{name}.{tag}.png"
    try:
        mpl.close("all")
        exec(code, {"plt": lib, "np": np, "x": x, "OUT": str(path)})
        return path, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

rows = []
for name, code in CASES.items():
    (a, ea), (b, eb) = run(name, code, mpl, "mpl"), run(name, code, plt_rs, "rs")
    rms = ""
    if a and b:
        ia, ib = mimg.imread(a)[..., :3], mimg.imread(b)[..., :3]
        rms = f"{np.sqrt(((ia - ib) ** 2).mean()):.3f}" if ia.shape == ib.shape else f"size {ia.shape[:2]} vs {ib.shape[:2]}"
    cell = lambda p, e: f'<img src="{p.name}">' if p else f'<pre style="color:#c00">{html.escape(e or "")}</pre>'
    rows.append(f"<tr><td><b>{name}</b><br>rms: {rms or 'n/a'}</td><td>{cell(a, ea)}</td><td>{cell(b, eb)}</td></tr>")
    print(f"{name:24} {'OK ' if b else 'FAIL'} {rms or eb}")
(out / "index.html").write_text(
    "<table border=1 cellpadding=6><tr><th>case</th><th>matplotlib</th><th>plt_rs</th></tr>"
    + "".join(rows) + "</table><style>img{max-width:480px}</style>")
