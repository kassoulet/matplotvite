"""Run repository-owned snippets in one reviewed place.

The gallery tools all execute checked-in snippets. The `exec`, the process
isolation and the timeout live here, so the security-sensitive pattern is
reviewed once and cannot drift between the renderers.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import warnings

SNIPPET_TIMEOUT = 90
ROOT = pathlib.Path(__file__).resolve().parent.parent

_CHILD_DRIVER = r'''
import importlib
import json
import pathlib
import sys

entry, snippet_path, options_path, result_path = sys.argv[1:5]
module_name, _, attr = entry.rpartition(".")
func = getattr(importlib.import_module(module_name), attr)
snippet = pathlib.Path(snippet_path).read_text(encoding="utf-8")
options = json.loads(pathlib.Path(options_path).read_text(encoding="utf-8"))
result = func(snippet, options)
pathlib.Path(result_path).write_text(json.dumps(result), encoding="utf-8")
'''


def execute(code: str, namespace: dict) -> None:
    """Run one repository-owned snippet in this interpreter.

    Only pinned, checked-in snippets reach this function; the caller is
    responsible for state cleanup. Runtime warnings are gallery noise.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        exec(code, namespace)  # nosec B102


def run_isolated(entry: str, snippet: str, options: dict | None = None,
                 timeout: float = SNIPPET_TIMEOUT, label: str = "snippet") -> dict:
    """Run `entry(snippet, options)` in a fresh interpreter.

    `entry` is the dotted path of a module-level function returning a JSON
    payload. Its cwd, rcParams, sys.path and imports are discarded with the
    process, and a crash or timeout becomes an error payload instead of
    aborting the caller's run.
    """
    options = dict(options or {})
    with tempfile.TemporaryDirectory(prefix="matplotvite-snippet-") as scratch:
        scratch = pathlib.Path(scratch)
        snippet_path = scratch / "snippet.py"
        options_path = scratch / "options.json"
        result_path = scratch / "result.json"
        snippet_path.write_text(snippet, encoding="utf-8")
        options_path.write_text(json.dumps(options), encoding="utf-8")
        env = dict(os.environ, MPLBACKEND="Agg")
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(ROOT), env.get("PYTHONPATH", "")) if part)
        command = [
            sys.executable, "-c", _CHILD_DRIVER, entry,
            str(snippet_path), str(options_path), str(result_path),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=scratch,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"TimeoutError: {label} did not finish in {timeout}s"}
        if completed.returncode != 0 or not result_path.exists():
            stderr = completed.stderr.strip().splitlines()
            return {"error": stderr[-1] if stderr
                    else f"snippet exited with status {completed.returncode}"}
        try:
            return json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"error": f"invalid snippet result: {exc}"}
