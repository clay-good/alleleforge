"""The reproducibility gate had been failing, and only a separate CI job knew.

`scripts/reproduce.py` re-derives the canonical run and diffs it against a golden
manifest. It is the check behind "reproducible to the byte", it exits 1 on drift, and it
runs as its own `make ci` target and its own GitHub Actions job — not as a test.

So when three legitimate improvements changed the canonical output — a new
`on_target_excluded_placements` field, the CFD matrix appearing in `provenance.datasets`,
and a reworded rationale — the golden was not regenerated, the full test suite stayed
green, and the drift was visible only to whoever read that one job's log. Every local
signal a developer looks at said the project was fine.

Running it from the suite costs a second and makes the drift fail where people look. The
separate target stays: `--update` is how a legitimate change is accepted, and this test is
what makes someone notice they need to run it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "reproduce.py"
_GOLDEN = _ROOT / "scripts" / "reproduce_golden.json"


def test_the_canonical_run_still_matches_its_golden() -> None:
    assert _SCRIPT.is_file() and _GOLDEN.is_file()
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": Path(sys.executable).parent.as_posix()},
    )
    assert result.returncode == 0, (
        "the canonical run no longer reproduces its golden manifest.\n"
        "If the change is intended, accept it with `python scripts/reproduce.py --update` "
        "and say in the commit what changed and why.\n\n" + result.stdout + result.stderr
    )
    assert "matches golden" in result.stdout, result.stdout


def test_the_check_actually_fails_on_drift(tmp_path: Path) -> None:
    """A gate that cannot fail is the thing this round found; prove this one can."""
    import json

    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    tampered = tmp_path / "reproduce_golden.json"
    body = golden.get("body", golden)
    assert isinstance(body, dict) and body, "the golden carries no body to perturb"
    golden["sha256"] = "0" * 64
    tampered.write_text(json.dumps(golden), encoding="utf-8")

    script = (tmp_path / "reproduce.py").resolve()
    script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=_ROOT,
        env={"PYTHONPATH": str(_ROOT / "src"), "PATH": Path(sys.executable).parent.as_posix()},
    )
    assert result.returncode == 1, (
        "a golden with the wrong digest was accepted; the gate reports drift it cannot "
        f"fail on.\n{result.stdout}{result.stderr}"
    )
