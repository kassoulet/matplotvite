"""The hash-pinned CI requirements have to stay complete and reproducible."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / ".github" / "requirements"
WORKFLOWS = ROOT / ".github" / "workflows"

FLOOR = re.compile(r"^# python-floor: \d+\.\d+$", re.MULTILINE)
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^;\s]+)(?:\s*;.*)?$")
HASH = re.compile(r"--hash=sha256:[0-9a-f]{64}\b")
NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
WORKFLOW_PIN = re.compile(r"\.github/requirements/([a-z]+)\.txt")


def _blocks(path: Path) -> list[str]:
    """Split a compiled file into one block per resolved requirement."""
    blocks: list[str] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line[0].isspace() and not line.startswith("#"):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _names(text: str) -> set[str]:
    """Normalised project names of the top-level requirements in a `.in` file."""
    names = set()
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = NAME.match(line.strip())
        assert match is not None, line
        names.add(match.group(1).lower().replace("-", "_"))
    return names


def _compiled(path: Path) -> dict[str, str]:
    entries = {}
    for block in _blocks(path):
        first = block.splitlines()[0].rstrip(" \\")
        match = PIN.match(first)
        assert match is not None, f"{path.name}: not a pinned requirement: {first}"
        entries[match.group(1).lower().replace("-", "_")] = block
    return entries


def test_every_entry_is_hash_pinned() -> None:
    for path in sorted(REQUIREMENTS.glob("*.txt")):
        entries = _compiled(path)
        assert entries, path.name
        for name, block in entries.items():
            assert HASH.search(block), f"{path.name}: {name} has no sha256 hash"


def test_every_source_requirement_is_resolved() -> None:
    for source in sorted(REQUIREMENTS.glob("*.in")):
        compiled = _compiled(source.with_suffix(".txt"))
        missing = _names(source.read_text(encoding="utf-8")) - set(compiled)
        assert not missing, f"{source.name} pins {sorted(missing)} but the .txt does not"


def test_sources_name_a_python_floor() -> None:
    sources = sorted(REQUIREMENTS.glob("*.in"))
    assert sources
    for source in sources:
        assert FLOOR.search(source.read_text(encoding="utf-8")), source.name


def test_compiled_files_have_one_source_each() -> None:
    sources = {path.stem for path in REQUIREMENTS.glob("*.in")}
    compiled = {path.stem for path in REQUIREMENTS.glob("*.txt")}
    assert sources == compiled


def test_workflows_only_reference_checked_in_pins() -> None:
    referenced = set()
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        referenced.update(WORKFLOW_PIN.findall(workflow.read_text(encoding="utf-8")))
    assert referenced
    for name in sorted(referenced):
        assert (REQUIREMENTS / f"{name}.txt").exists(), name
