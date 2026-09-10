"""`--no-resume` is the remedy three messages name, and it corrupted the file it ran into.

    $ aforge batch c.txt --reference-fasta g.fa --manifest m.jsonl              # 12 items
    $ aforge batch c.txt --reference-fasta g.fa --manifest m.jsonl --no-resume  # 12 again
    24 item records, two per id, under the `_run` header the *first* run wrote

The file then describes one run and contains two. That is not merely untidy:
`_read_done_ids` reads ids into a set, so a later resume skips every one of them, choosing
between two stored summaries by never looking at either. Re-running under changed inputs and
then resuming is exactly the "silently a mixture of two runs" that the mismatched-resume
refusal exists to prevent — reached through a door with no guard on it, and reached by
following the advice the refusal itself gave.

Refused, not truncated: this project does not delete a caller's file to make its own life
easier, and which run to keep is the operator's call. The three messages that named
`--no-resume` now name a fresh `--manifest` with it, which is the pairing that works.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alleleforge.design.cohort import design_many
from alleleforge.genome.reference import ReferenceGenome

_ALT = {"A": "G", "G": "A", "C": "T", "T": "C"}


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    import random

    random.seed(5)
    body = "".join(random.choice("ACGT") for _ in range(3000))
    path = tmp_path / "ref.fa"
    path.write_text(
        ">chr11\n" + "\n".join(body[i : i + 60] for i in range(0, len(body), 60)) + "\n"
    )
    return path


def _variants(fasta: Path) -> list[str]:
    import pyfaidx

    handle = pyfaidx.Fasta(str(fasta))
    out = []
    for pos in (1010, 1050):
        base = str(handle["chr11"][pos - 1 : pos]).upper()
        out.append(f"chr11:{pos}:{base}>{_ALT[base]}")
    return out


def _run(fasta: Path, manifest: Path, *, resume: bool = True) -> object:
    return design_many(
        _variants(fasta),
        reference=ReferenceGenome(fasta, build="hg38"),
        manifest_path=manifest,
        resume=resume,
        run_offtarget=False,
    )


def _records(manifest: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in manifest.read_text().splitlines()
        if line.strip() and "item_id" in line
    ]


def test_a_rerun_into_an_existing_manifest_is_refused(fasta: Path, tmp_path: Path) -> None:
    manifest = tmp_path / "m.jsonl"
    _run(fasta, manifest)
    before = _records(manifest)
    with pytest.raises(ValueError) as excinfo:
        _run(fasta, manifest, resume=False)
    message = str(excinfo.value)
    assert "a second record for every item" in message
    # Both ways forward, because deleting the file is the operator's call and not ours.
    assert "new file" in message and "move this one aside" in message
    # And nothing was written or removed by the refusal.
    assert _records(manifest) == before


def test_a_fresh_manifest_is_the_remedy(fasta: Path, tmp_path: Path) -> None:
    """The half a refusal-only test cannot see."""
    _run(fasta, tmp_path / "first.jsonl")
    fresh = tmp_path / "second.jsonl"
    _run(fasta, fresh, resume=False)
    ids = [record["item_id"] for record in _records(fresh)]
    assert len(ids) == len(set(ids)) == 2


def test_a_manifest_that_does_not_exist_yet_is_not_a_refusal(fasta: Path, tmp_path: Path) -> None:
    _run(fasta, tmp_path / "new.jsonl", resume=False)


def test_a_manifest_killed_before_its_first_write_is_not_a_refusal(
    fasta: Path, tmp_path: Path
) -> None:
    """An interrupted run leaves exactly this, and it holds no records to duplicate."""
    manifest = tmp_path / "empty.jsonl"
    manifest.write_text("")
    _run(fasta, manifest, resume=False)


def test_every_message_that_names_the_flag_names_a_fresh_manifest() -> None:
    """A remedy that is now refused would be worse than none.

    Three messages recommended `--no-resume`: the mismatched-resume refusal, the
    unverified-resume warning, and the partial-table note. Each has to name the pairing
    that works.

    Only *messages* — the strings a user is shown. The first version of this grepped the
    source and failed on the new refusal's own docstring, which names the flag in order to
    explain what it used to do. A comment explaining a fix is not a remedy being offered.
    """
    import ast

    from alleleforge.design import cohort, cohort_summary

    def messages(module: object) -> list[str]:
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))  # type: ignore[attr-defined]
        out: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in {"ValueError", "warn", "append", "RuntimeError"}:
                continue
            text = "".join(
                literal.value
                for argument in node.args
                for literal in ast.walk(argument)
                if isinstance(literal, ast.Constant) and isinstance(literal.value, str)
            )
            if text:
                out.append(text)
        return out

    offering = [
        text
        for module in (cohort, cohort_summary)
        for text in messages(module)
        if "--no-resume" in text
    ]
    assert offering, "no message names the flag any more, so this check is vacuous"
    for text in offering:
        assert "new file" in text or "fresh" in text, (
            f"this message offers --no-resume without a fresh manifest, which is now "
            f"refused: {text[:160]}"
        )
