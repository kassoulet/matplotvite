# Shared golden images

These PNGs are the common reference for both front ends. `scenes.txt` names each
scene, its pixel size and the maximum RMS error:

- `tests/test_golden_images.py` renders each scene through the Python facade.
- `crates/matplotvite/tests` runs `tests/golden.rs` through the native Rust builder.

Both compare against the committed PNG, so a change that updates only one front
end fails the other suite.

The labelled artists, fonts, figure size and DPI are deliberately identical on
both sides. Keep new scenes inside the surface the native builder exposes.

Regenerate after an intentional rendering change:

```sh
.venv/bin/python tests/golden_scenes.py
```

Then run both suites and update a tolerance in `scenes.txt` only when the
difference is understood.
