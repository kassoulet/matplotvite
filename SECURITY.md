# Security policy

## Supported versions

Matplotvite is pre-1.0. Security fixes are made on the latest minor release;
older minors are not maintained.

| Version | Supported |
| --- | --- |
| 0.6.x | Yes |
| < 0.6 | No |

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's
private vulnerability reporting form:

<https://github.com/kassoulet/matplotvite/security/advisories/new>

Include the affected version, the output format and platform, a minimal
reproduction, and any relevant traceback or sample file. If the issue is in a
dependency, include the dependency name and version as well.

The maintainer will acknowledge the report, investigate it, and coordinate a
fix and disclosure through the advisory. This is a volunteer project, so no
response-time guarantee is implied.

## Scope

The Python package ships a compiled Rust extension. The crate forbids
`unsafe` code, but it uses PyO3 and NumPy FFI and links third-party Rust and C
dependencies, including the bundled WebP encoder. Reports about those
boundaries and about malicious or malformed input are in scope. The optional
harvested-gallery tools execute third-party example scripts and are development
tools, not part of the installed runtime.

General dependency advisories are tracked with `cargo audit` and `pip-audit`
in CI. If you are unsure whether something is a vulnerability, use the private
form rather than a public issue.
