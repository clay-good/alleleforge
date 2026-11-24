"""The CLI's error paths print a message and then have to *exit*, and 42 did not prove it.

This file pins a class, not four bugs. `cli/main.py` carries 93 `raise typer.Exit(...)`
sites; deleting the raise at 42 of them survived `tests/cli` entirely. The reason they
survive is the shape worth remembering: every one of those sites looks like

    _echo_err(f"error: {reason(exc)}")
    raise typer.Exit(ExitCode.USAGE) from exc

Delete the second line and the *first* line still runs. The message is printed, on
stderr, with the right wording. So every test that asserts on the error text keeps
passing — and the suite has 918 assertions in `tests/cli`, of which 116 are
`exit_code == 0` and only 66 assert a specific non-zero code. What changes when the raise
goes is invisible to a test reading output: the command falls off the end of the function
and the process exits **0**.

A CLI that prints `error: ...` and exits 0 is worse than one that crashes. `set -e` does
not trip. A `&&` chain continues. A CI step goes green. A Snakemake or Nextflow rule
marks the job successful and the next rule consumes a file that was never written. The
printed message is for a human who is watching; the exit code is for everything else,
and in a tool whose whole purpose is to be driven from a pipeline, the exit code is the
louder half of the refusal.

The four sites pinned here are the ones where believing a failed run succeeded is most
expensive: `design`'s vector-scheme refusal (the flagship command, guarded before the
off-target search) and both in `verify`, whose *only* output is a verdict — a `verify`
that exits 0 having verified nothing is an affirmative false claim about an artifact's
provenance. Those three deletions now die; measured, not assumed.

One test here closes nothing, and says so rather than being dropped: the parquet
`--out` case pins the `USAGE` guard at `main.py:1761`, which was already covered. Its
*neighbour* at 1766 is the survivor, and that one is unreachable in this environment for
a reason worth recording — it only fires when `polars` is missing, and `polars` is
installed here, so no test could kill it without uninstalling the writer. It is
equivalent-by-environment, not untested. The two `501` survivors in `web/api/app.py` are
the same gate seen from the HTTP side.

The remaining 39 `typer.Exit` sites are recorded in `openspec/changes/README.md` with
their line numbers rather than quietly left; they are the same shape, and this file is
the pattern for closing them.

Found by deleting each refusal (`scripts/mutate.py --mode raise`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

# -- design -------------------------------------------------------------------


def test_an_unknown_vector_scheme_is_a_usage_error(runner: CliRunner, prime_fasta: Path) -> None:
    """Refused up front, and refused with a code.

    The guard is placed before the off-target search on purpose — the source comment
    says learning about a bad scheme name "after a whole-genome off-target search would
    be cruel". That early placement is exactly what makes the exit code load-bearing: a
    pipeline that ignores it proceeds to the next step having produced no report.
    """
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--vector-scheme",
            "not-a-scheme",
        ],
    )
    assert result.exit_code == ExitCode.USAGE, (
        f"a bad --vector-scheme exited {result.exit_code}. Exit 0 here means `aforge "
        "design ... && next-step` runs next-step on a report that was never produced.",
        result.output,
    )
    assert "error" in result.output.lower() + (result.stderr or "")


def test_parquet_without_an_out_path_is_a_usage_error(runner: CliRunner, prime_fasta: Path) -> None:
    """A format that can only be written to a file, with nowhere to write it.

    Parquet is binary, so unlike tsv or json it cannot go to stdout. Exit 0 here is the
    worst case of the class: the user asked for a file, got no file, and got a success.

    This guard (`main.py:1761`) was already covered — it is kept because the test was
    written against the survivor at 1766 and lands two lines short of it, and a test
    deleted for being redundant is a test nobody can check that claim against. 1766 is
    the `polars`-missing path, unreachable wherever the writer is installed.
    """
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--format",
            "parquet",
        ],
    )
    assert result.exit_code == ExitCode.USAGE, (result.exit_code, result.output)
    assert "--out" in result.output + (result.stderr or ""), (
        "the refusal does not name the flag that would fix it",
        result.output,
    )


# -- verify, where the exit code *is* the answer -------------------------------


def test_verify_on_a_missing_file_exits_missing_data(runner: CliRunner, tmp_path: Path) -> None:
    """`verify`'s contract is its exit status, so exit 0 is an affirmative false claim.

    Every other command's exit code says whether it did its work. `verify`'s says
    whether the artifact *passed* — the documentation is explicit that it "exits
    non-zero on incomplete provenance or an artifact hash mismatch". A `verify` that
    cannot find the file and exits 0 does not merely fail quietly; it reports that a
    file it never opened is sound. In a release gate that is the difference between
    blocking a bad artifact and signing it off.
    """
    missing = tmp_path / "nowhere.json"
    result = runner.invoke(app, ["verify", str(missing)])

    assert result.exit_code == ExitCode.MISSING_DATA, (
        f"verify on a nonexistent artifact exited {result.exit_code}. Exit 0 from "
        "verify is a claim that the artifact checked out — about a file it never read.",
        result.output,
    )
    assert "not found" in result.output + (result.stderr or ""), result.output


def test_verify_on_a_format_with_a_sidecar_exits_usage_and_names_the_sidecar(
    runner: CliRunner, tmp_path: Path
) -> None:
    """The branch that redirects the user, which still has to be a failure.

    For tsv/html/pdf output the provenance lives in a `.provenance.json` sidecar, so
    this refusal exists to hand the reader the right path. It is the most tempting site
    in the file to let exit 0 through — the message is helpful, not angry — and it is
    still a verification that did not happen.
    """
    artifact = tmp_path / "report.tsv"
    artifact.write_text("candidate\tscore\nx\t1\n")
    sidecar = tmp_path / "report.tsv.provenance.json"
    sidecar.write_text(json.dumps({"version": "0"}))

    result = runner.invoke(app, ["verify", str(artifact)])
    output = result.output + (result.stderr or "")

    assert result.exit_code == ExitCode.USAGE, (
        f"verify exited {result.exit_code} on an artifact it did not verify",
        output,
    )
    assert sidecar.name in output, (
        "the refusal does not name the sidecar to verify instead, which is the only "
        "reason this branch exists rather than a flat failure",
        output,
    )


# -- the class itself ----------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["design", "chr2:71:A>C", "--reference-fasta", "/nonexistent/ref.fa"],
        ["verify", "/nonexistent/result.json"],
        ["design", "not-a-variant", "--reference-fasta", "/nonexistent/ref.fa"],
        ["design", "chr2:71:A>C", "--reference-fasta", "/nonexistent/ref.fa", "--intent", "bogus"],
    ],
    ids=["missing-reference", "missing-result", "bad-variant", "bad-intent"],
)
def test_no_refusal_exits_zero(runner: CliRunner, argv: list[str]) -> None:
    """The invariant behind all 93 sites, stated once.

    Deliberately weaker than the tests above — it asserts only "not 0" — because its job
    is different: it is the assertion that would have caught *any* of the 42 deletions on
    the paths it covers, where a test pinning an exact code catches one. A refusal that
    exits 0 is the defect; which non-zero code it picks is a separate contract, pinned
    per-command above and in the sibling `test_a_refusal_*` files.
    """
    result = runner.invoke(app, argv)
    assert result.exit_code != 0, (
        f"`aforge {' '.join(argv)}` refused and still exited 0",
        result.output,
    )
