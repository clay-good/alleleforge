"""`verify --cache-dir` said "verified" over three unmeasured artifacts.

The command already refused to call a run verified when it had re-hashed *nothing*: that
note exists, with a comment saying reporting "verified" for a run that hashed nothing is
"not measured" printed as "clean", and worst here because checking is the whole purpose.

The partial case was not written. A real run pins two baseline models with no checkpoint
hash and two datasets, one of which is a user-supplied ClinVar release that lives on the
caller's disk and can never be in the registry cache. That verify re-hashed one artifact
of four, printed a four-row list, and finished with the same sentence as a run that
re-hashed everything. The reader has to add the rows up — and the rows all began with the
word "checkpoint", including the datasets, while the line above them counted models and
datasets separately.

The shape recurs: the total absence of a measurement gets a note, and the partial one
does not, because whoever wrote the note was looking at the case that had none.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app
from alleleforge.data.registry import DEFAULT_REGISTRY
from alleleforge.types.provenance import DatasetVersion, ModelCheckpoint, Provenance


def _bundled_dataset() -> DatasetVersion:
    """The vendored CFD matrix: the one artifact whose bytes always hash here.

    Taken from the registry rather than written out, so the fixture cannot pin a stale
    hash and quietly become a MISMATCH test.
    """
    return DEFAULT_REGISTRY.get("doench-2016-cfd").dataset_version()


def _sidecar(tmp_path: Path, **kwargs: object) -> Path:
    provenance = Provenance(
        alleleforge_version="0.0.0",
        reference_build="hg38",
        seed=1,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        # Present so the completeness check passes and the *coverage* statement is what
        # these cases are about; verify refuses a sidecar with no config snapshot.
        config_snapshot={"intent": "correct"},
        **kwargs,  # type: ignore[arg-type]
    )
    path = tmp_path / "x.provenance.json"
    path.write_text(provenance.model_dump_json())
    return path


def _run(path: Path, cache: Path) -> tuple[int, str, dict[str, object]]:
    result = CliRunner().invoke(app, ["verify", str(path), "--cache-dir", str(cache), "--json"])
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    text = CliRunner().invoke(app, ["verify", str(path), "--cache-dir", str(cache)]).output
    return result.exit_code, text, payload


def test_a_partial_check_says_so_and_names_what_it_missed(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    sidecar = _sidecar(
        tmp_path,
        models=(ModelCheckpoint(name="baseline", version="0.1"),),
        datasets=(
            _bundled_dataset(),
            DatasetVersion(name="clinvar", version="sha256:abc", sha256="a" * 64),
        ),
    )
    code, text, payload = _run(sidecar, cache)
    assert code == 0, text
    assert "re-hashed 1 of 3" in text, text
    # Naming them, not only counting: "2 unchecked" sends a reader back to the rows.
    assert "baseline.0.1 (unpinned)" in text and "clinvar" in text, text
    assert payload["artifacts_rehashed"] == 1
    assert payload["artifacts_checkable"] == 3


def test_each_row_says_whether_it_is_a_model_or_a_dataset(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    sidecar = _sidecar(
        tmp_path,
        models=(ModelCheckpoint(name="baseline", version="0.1"),),
        datasets=(_bundled_dataset(),),
    )
    _, text, payload = _run(sidecar, cache)
    assert "  model baseline.0.1:" in text, text
    assert "  dataset doench-2016-cfd.2016:" in text, text
    assert {c["kind"] for c in payload["checkpoint_checks"]} == {"model", "dataset"}  # type: ignore[union-attr]


def test_a_complete_check_adds_no_note(tmp_path: Path) -> None:
    """The note must fire on partial coverage, not on every run with a cache dir."""
    cache = tmp_path / "cache"
    cache.mkdir()
    sidecar = _sidecar(tmp_path, datasets=(_bundled_dataset(),))
    _, text, payload = _run(sidecar, cache)
    assert payload["artifacts_rehashed"] == payload["artifacts_checkable"] == 1
    assert "re-hashed" not in text, text
    assert "Nothing was established" not in text, text


@pytest.mark.parametrize("with_cache", [False, True])
def test_a_run_that_hashed_nothing_still_says_nothing_was_established(
    with_cache: bool, tmp_path: Path
) -> None:
    """The case that already worked, kept working — the note it prints is different."""
    cache = tmp_path / "cache"
    cache.mkdir()
    sidecar = _sidecar(tmp_path, models=(ModelCheckpoint(name="baseline", version="0.1"),))
    argv = ["verify", str(sidecar)] + (["--cache-dir", str(cache)] if with_cache else [])
    text = CliRunner().invoke(app, argv).output
    assert "NOTE" in text, text
    assert "re-hashed 1 of" not in text, text
