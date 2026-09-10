"""A tampered cache told the user their tool was broken.

The off-target cache verifies an entry's bytes on read and **refuses** rather than
recomputing, deliberately: recomputing gives the right answer and hides that a store the
run trusted has been altered. That refusal reached the user as

    prime: ERROR — unexpected CacheIntegrityError: ... (a defect, not 'no design')
    error: a chemistry failed with an unexpected error and contributed no candidates

which is two wrong things. Nothing in AlleleForge failed — an entry on the user's disk is
not the bytes that were written to it — and the message names no remedy, so the reader's
next step is to file a bug about their own cache.

It was in the defect bucket because the alternative bucket is worse: `skipped`, the
graceful-degradation path, would let a design continue past a store whose contents
changed, undoing the fail-closed gate. The answer is a third category. The behaviour is
unchanged — the chemistry contributes nothing, the menu is written, the command exits
`UNAVAILABLE`, which this CLI documents as "unavailable dependency **or a failed integrity
check**" — and what changes is what the run says happened, and what to do about it.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app
from alleleforge.design.designer import DEFECT_NOTE, INTEGRITY_NOTE

SPACER_LOCUS = 1500


@pytest.fixture
def genome(tmp_path: Path) -> tuple[Path, str]:
    rng = random.Random(23)
    sequence = "".join(rng.choices("ACGT", k=4000))
    fasta = tmp_path / "store.fa"
    fasta.write_text(">chr1\n" + sequence + "\n")
    ref_base = sequence[SPACER_LOCUS]
    variant = f"chr1:{SPACER_LOCUS + 1}:{ref_base}>{'A' if ref_base != 'A' else 'G'}"
    return fasta, variant


def _design(cache: Path, fasta: Path, variant: str, out: Path) -> object:
    return CliRunner().invoke(
        app,
        [
            "--cache-dir",
            str(cache),
            "design",
            variant,
            "--reference-fasta",
            str(fasta),
            "--cache",
            "--format",
            "json",
            "--out",
            str(out),
        ],
    )


def test_an_altered_entry_is_named_as_a_store_problem_with_its_remedy(
    genome: tuple[Path, str], tmp_path: Path
) -> None:
    fasta, variant = genome
    cache = tmp_path / "cache"
    warm = _design(cache, fasta, variant, tmp_path / "warm.json")
    assert warm.exit_code == 0, warm.output + warm.stderr

    entries = [p for p in (cache / "caches").rglob("*") if p.is_file() and p.suffix != ".sum"]
    assert entries, "the run cached nothing; this check would be vacuous"
    altered = entries[0]
    payload = json.loads(altered.read_text())
    payload["sites"] = []  # the finding itself, removed — the case this gate exists for
    altered.write_text(json.dumps(payload))

    result = _design(cache, fasta, variant, tmp_path / "tampered.json")
    assert result.exit_code == ExitCode.UNAVAILABLE, result.output + result.stderr

    menu = json.loads((tmp_path / "tampered.json").read_text())
    rationale = menu["rationale"]
    assert INTEGRITY_NOTE in rationale, rationale
    assert DEFECT_NOTE not in rationale, "an altered store is not a defect in this tool"
    assert altered.name in rationale, "the note must name the entry to delete"
    assert "content-addressed" in rationale and "safe" in rationale, (
        "the note must say what to do: deleting the entry is safe, the next run recomputes"
    )
    assert "aforge cache verify" in rationale

    stderr = result.stderr
    assert "integrity check" in stderr, stderr
    assert "unexpected error" not in stderr, stderr


def test_a_real_defect_is_still_called_one(genome: tuple[Path, str], tmp_path: Path) -> None:
    """The other bucket must not have been widened: a genuine bug still says so."""
    fasta, variant = genome
    # Patched on the *designer*, which imported the name at module load: patching it on
    # `design.prime` leaves the designer holding its own reference, and the first draft of
    # this test did exactly that and asserted on a run that never failed.
    from alleleforge.design import designer as designer_module

    original = designer_module.design_prime

    def explode(*args: object, **kwargs: object) -> object:
        raise ZeroDivisionError("a genuine defect")

    designer_module.design_prime = explode  # type: ignore[assignment]
    try:
        result = _design(tmp_path / "cache2", fasta, variant, tmp_path / "defect.json")
    finally:
        designer_module.design_prime = original  # type: ignore[assignment]

    assert result.exit_code == ExitCode.UNAVAILABLE
    rationale = json.loads((tmp_path / "defect.json").read_text())["rationale"]
    assert DEFECT_NOTE in rationale and INTEGRITY_NOTE not in rationale
