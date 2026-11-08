# Sentinel journal

## 2026-11-08 - Prism assets loaded without Subresource Integrity

**Vulnerability:** `index.html` and `comparison.html` loaded Prism's CSS and
JavaScript from cdnjs without `integrity`/`crossorigin` attributes, so a
compromised CDN or tampered response could execute arbitrary script on the
published documentation site.
**Learning:** Supply-chain review had focused on GitHub Actions pins; the
browser-side CDN references hid inside Python template strings in
`tools/build_pages.py`, where no linter or dependency scanner looks.
**Prevention:** Keep third-party CDN references in `prism_stylesheet()` and
`prism_scripts()` with a pinned version plus SRI digests, and regenerate the
digests when `PRISM_VERSION` changes. The generation test asserts every page
emits exactly three SRI-protected Prism tags.
