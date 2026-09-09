"""A pinned digest beside a URL invites checking the URL. For one row that is wrong.

`doench-2016-cfd`'s provenance row pairs `source_url` — CRISPOR's upstream
`mismatch_score.pkl` — with `sha256`, the digest of the *vendored JSON conversion* that
ships in the package. The shipped file records both hashes itself, under
`_provenance.sources`, so the two being different is a documented fact of the vendoring,
not an accident.

A reader auditing a run from the provenance block does the obvious thing: fetch the URL,
hash it, compare. They get a mismatch, and the only conclusion the pin offers is
tampering — which is exactly the conclusion the pin exists to make impossible.

`DatasetVersion.bundled` answers the question `sha256` alone cannot: *what is this the
hash of?* It follows `caller_supplied`, added for the same kind of reason one row over —
that pin cannot be re-hashed by the tool because the bytes are on the caller's disk; this
one can, but not from the URL beside it.

Three surfaces say it, because a machine-readable record a human cannot read is half a
record: the provenance JSON carries the flag, the footer every render shares says
"(bundled; the hash is of the file that ships)", and `aforge verify --cache-dir` reports
`ok (bundled)` rather than a bare `ok` beside a URL it did not check.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alleleforge.data.registry import DEFAULT_REGISTRY
from alleleforge.report.builder import _dataset_origin, provenance_lines
from alleleforge.types.provenance import DatasetVersion, Provenance

_BUNDLED = "doench-2016-cfd"


def test_a_bundled_dataset_records_that_it_is_bundled() -> None:
    version = DEFAULT_REGISTRY.get(_BUNDLED).dataset_version()
    assert version.bundled is True
    assert version.caller_supplied is False


def test_a_dataset_that_is_not_bundled_does_not_claim_to_be() -> None:
    for name in sorted(DEFAULT_REGISTRY.names):
        descriptor = DEFAULT_REGISTRY.get(name)
        assert descriptor.dataset_version().bundled == descriptor.bundled, name


def test_the_flag_is_needed_because_the_two_artifacts_differ() -> None:
    """If a future vendoring made them identical this fails, and the wording above
    needs revisiting rather than quietly standing."""
    descriptor = DEFAULT_REGISTRY.get(_BUNDLED)
    path = descriptor.bundled_file()
    assert path is not None
    sources = json.loads(path.read_text())["_provenance"]["sources"]
    upstream = {entry["url"]: entry["sha256"] for entry in sources}
    assert descriptor.source_url in upstream
    assert upstream[descriptor.source_url] != descriptor.sha256


def test_the_footer_every_render_shares_says_where_the_bytes_are() -> None:
    provenance = Provenance(
        alleleforge_version="0.0.0",
        seed=1,
        timestamp=datetime(2024, 5, 1, tzinfo=UTC),
        config_snapshot={"k": "v"},
        datasets=(DEFAULT_REGISTRY.get(_BUNDLED).dataset_version(),),
    )
    line = next(line for line in provenance_lines(provenance) if line.startswith("datasets:"))
    assert "bundled" in line and "the file that ships" in line, line


@pytest.mark.parametrize(
    ("bundled", "caller_supplied", "expected"),
    [
        (True, False, "bundled"),
        (False, True, "supplied by the caller"),
        (False, False, ""),
    ],
)
def test_each_origin_reads_differently(bundled: bool, caller_supplied: bool, expected: str) -> None:
    """The three origins must not print identically; that was the original defect."""
    origin = _dataset_origin(
        DatasetVersion(name="x", version="1", bundled=bundled, caller_supplied=caller_supplied)
    )
    assert expected in origin
    if not expected:
        assert origin == ""


def test_verify_says_which_artifact_it_hashed(tmp_path: Path) -> None:
    """A bare `ok` beside a URL invites checking bytes the tool did not check."""
    from typer.testing import CliRunner

    from alleleforge.cli.main import ExitCode, app

    # A real contig, not a repeat: `ACGT * 500` contains no PAM, so nothing is scanned,
    # no matrix is recorded, and `verify` would have zero datasets to report on.
    rng = random.Random(7)
    sequence = "".join(rng.choice("ACGT") for _ in range(4000))
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(f">chr1\n{sequence}\n")
    out = tmp_path / "r.json"
    reference_base = sequence[1999]
    alternate = "A" if reference_base != "A" else "G"
    designed = CliRunner().invoke(
        app,
        [
            "design",
            f"chr1:2000:{reference_base}>{alternate}",
            "--reference-fasta",
            str(fasta),
            "--out",
            str(out),
        ],
    )
    assert designed.exit_code == ExitCode.OK, designed.output + designed.stderr
    result = CliRunner().invoke(app, ["verify", str(out), "--cache-dir", str(tmp_path / "cache")])
    assert result.exit_code == ExitCode.OK, result.output + result.stderr
    assert "ok (bundled)" in result.output, result.output
