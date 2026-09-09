"""The only check that catches a same-length index tamper was reachable from Python alone.

Two on-disk stores hold work a run reuses instead of recomputing, and a run trusts both:
the cross-run off-target report cache (`--cache`) and the persistent FM-index cache
(`--genome-index`). Each knows how to detect a corrupted entry. Neither could be *asked*.

* The report cache re-checks a checksum sidecar — but only when a design happens to read
  that entry, so a damaged cache announces itself in the middle of the run that needed it.
* The FM-index gets constant-time structural checks on load, and those are honest about
  their reach: a flipped byte keeps every structural fact intact. `FMIndex.verify()` is
  what catches that, by reconstructing the text and re-hashing it, and
  `test_a_corrupt_index_cache_is_refused` measures what it prevents — a tampered index
  drops a real occurrence *and* reports positions that are not occurrences at all, so a
  scan nominates off-target loci that do not exist. It is `O(n)`, so it cannot run on
  every load, which makes it exactly the kind of thing a *command* is for. There was no
  command. It was a Python method, in a tool whose users are told to use a CLI.

`aforge cache verify` sweeps them. Four stores under the cache dir hold bytes a run
trusts — two hold *work* (the report cache, the index cache) and two hold *artifacts* it
was given (the dataset cache and the checkpoint cache, plus the datasets that ship inside
the package). The artifact halves are re-hashed on every resolve, which is stricter than
the work halves and just as reactive: a damaged file announces itself in the middle of the
run that needed it. The first version of this command swept two of the four, which is the
same defect it was written to fix.

`--deep` adds the index reconstruction, and the run without it says in so many words what
it did not check rather than printing "ok". So does a pinned artifact that is not on this
disk, and an unpinned one: "nothing was checked" is not a pass and is counted apart from
one.

The content-addressed namespaces are read off disk rather than named in the command. The
first version named `offtarget` and walked straight past the **embeddings** cache sitting
beside it — the store that had checksum sidecars first, and the one whose existence is the
reason the off-target cache was found to be missing them. A sweep with a hand-written
population checks the caches someone remembered.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import ExitCode, app

runner = CliRunner()

_SPACER = "ACGTAACGTTACGTAACGT"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    rng = random.Random(7)
    seq = "".join(rng.choice("ACGT") for _ in range(4000))
    seq = seq[:100] + _SPACER + "AGG" + seq[122:]
    path = tmp_path / "ref.fa"
    path.write_text(f">chr1\n{seq}\n", encoding="utf-8")
    return path


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # `get_settings()` is a process-wide singleton loaded once, so setting the variable
    # is not enough — without dropping the singleton these tests share whichever cache
    # dir the first one loaded, which is the developer's real cache.
    import alleleforge.config as config

    root = tmp_path / "cache"
    monkeypatch.setattr(config, "_SETTINGS", None)
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(root))
    return root


@pytest.fixture
def warm(fasta: Path, cache_dir: Path) -> Path:
    """Fill both stores by running the command that writes them."""
    result = runner.invoke(
        app,
        [
            "offtarget",
            _SPACER,
            "--reference-fasta",
            str(fasta),
            "--cache",
            "--genome-index",
            "--json",
        ],
    )
    assert result.exit_code == ExitCode.OK, result.output
    return cache_dir


def _verify(*args: str) -> tuple[int, dict[str, object]]:
    result = runner.invoke(app, ["cache", "verify", "--json", *args])
    return result.exit_code, json.loads(result.stdout)


def test_a_clean_cache_verifies(warm: Path) -> None:
    """The premise: both stores are populated and both come back ok."""
    code, payload = _verify()
    checks = payload["checks"]
    assert isinstance(checks, list) and checks, payload
    kinds = {check["kind"] for check in checks}
    # The content-addressed namespaces are read off disk, not named here, so the kind is
    # whatever the store called itself.
    assert {"fm-index", "dataset", "checkpoint"} <= kinds, kinds
    assert any(kind.startswith("offtarget/") for kind in kinds), kinds
    assert not [c for c in checks if c["status"] in {"CORRUPT", "UNREADABLE", "MISMATCH"}], checks
    assert code == ExitCode.OK


def test_an_edited_report_entry_is_named(warm: Path) -> None:
    """The sweep is proactive: today this is found only when a run reads that entry."""
    entry = next(
        path
        for path in (warm / "caches").rglob("*")
        if path.is_file() and not path.name.endswith(".sum")
    )
    doc = json.loads(entry.read_text())
    doc["sites"] = []
    entry.write_text(json.dumps(doc))

    code, payload = _verify()
    corrupt = [c for c in payload["checks"] if c["status"] == "CORRUPT"]  # type: ignore[union-attr]
    assert [c["kind"] for c in corrupt] == ["offtarget/v2"], payload
    assert code == ExitCode.UNAVAILABLE


def test_a_same_length_index_tamper_needs_deep_and_says_so(warm: Path) -> None:
    """The whole reason `--deep` exists, and the reason the shallow run must not say ok."""
    bwt = sorted((warm / "fm_index").glob("*/bwt.bin"))[0]
    data = bytearray(bwt.read_bytes())
    for position in range(0, len(data), 11):
        if data[position] in b"ACGT":
            data[position] = ord("A") if data[position] != ord("A") else ord("C")
    bwt.write_bytes(bytes(data))

    shallow_code, shallow = _verify()
    indexes = [c for c in shallow["checks"] if c["kind"] == "fm-index"]  # type: ignore[union-attr]
    assert all(c["status"] == "ok (structure only)" for c in indexes), indexes
    assert shallow_code == ExitCode.OK

    deep_code, deep = _verify("--deep")
    corrupt = [c for c in deep["checks"] if c["status"] == "CORRUPT"]  # type: ignore[union-attr]
    assert [c["kind"] for c in corrupt] == ["fm-index"], deep
    assert deep_code == ExitCode.UNAVAILABLE


def test_the_shallow_run_states_what_it_did_not_check(warm: Path) -> None:
    """ "ok" for a check that did not run is the failure mode this command is about."""
    result = runner.invoke(app, ["cache", "verify"])
    assert result.exit_code == ExitCode.OK, result.output
    assert "--deep" in result.stdout, result.stdout
    assert "structural checks only" in result.stdout, result.stdout


def test_an_empty_cache_is_not_a_silent_pass(cache_dir: Path) -> None:
    """Nothing checked is not the same sentence as everything checked.

    An empty cache dir is not an empty sweep: the bundled dataset ships inside the
    package and is hashed wherever the run happens, and everything else is reported as
    not checked with a count, rather than as a clean bill of health.
    """
    result = runner.invoke(app, ["cache", "verify"])
    assert result.exit_code == ExitCode.OK, result.output
    assert "were not checked" in result.stdout, result.stdout
    assert "doench-2016-cfd" in result.stdout, result.stdout


def test_a_tampered_checkpoint_is_named(warm: Path) -> None:
    """The artifact half of the sweep, on the store whose bytes decide a score."""
    models = warm / "models"
    models.mkdir(parents=True, exist_ok=True)
    (models / "rule-set-3.1.0.ckpt").write_bytes(b"not the weights that were pinned")

    code, payload = _verify()
    mismatched = [c for c in payload["checks"] if c["status"] == "MISMATCH"]  # type: ignore[union-attr]
    assert [c["kind"] for c in mismatched] == ["checkpoint"], payload
    assert "expected" in mismatched[0]["origin"], mismatched
    assert code == ExitCode.UNAVAILABLE


def test_the_bundled_dataset_is_checked_where_it_actually_lives(warm: Path) -> None:
    """Bundled bytes are in the installed package, never in the cache.

    Looking for them under the cache dir is how the one dataset that is always present
    came to be reported unavailable once already — so the sweep must find and hash the
    shipped file, not report it as absent.
    """
    _, payload = _verify()
    row = next(
        c
        for c in payload["checks"]  # type: ignore[union-attr]
        if c["kind"] == "dataset" and c["artifact"] == "doench-2016-cfd"
    )
    assert row["status"] == "ok", row


def test_an_unchecked_artifact_is_not_reported_as_a_pass(warm: Path) -> None:
    """ "unpinned" and "not cached" are neither passes nor failures, and are counted apart."""
    code, payload = _verify()
    statuses = {c["status"] for c in payload["checks"]}  # type: ignore[union-attr]
    assert "unpinned" in statuses, statuses
    assert code == ExitCode.OK

    result = runner.invoke(app, ["cache", "verify"])
    assert "were not checked" in result.stdout, result.stdout


def test_every_namespace_on_disk_is_swept(warm: Path, tmp_path: Path) -> None:
    """A namespace this command has never heard of must still be checked."""
    from alleleforge.cache import ContentAddressedCache

    ContentAddressedCache("embeddings/v2/stub-0", root=warm, verify=True).put_text("a" * 64, "[]")
    invented = ContentAddressedCache("something/nobody/named/yet", root=warm, verify=True)
    invented.put_text("b" * 64, "{}")

    _, payload = _verify()
    kinds = {c["kind"] for c in payload["checks"]}  # type: ignore[union-attr]
    assert "embeddings/v2/stub-0" in kinds, kinds
    assert "something/nobody/named/yet" in kinds, kinds


def test_a_corrupt_entry_in_any_namespace_fails_the_sweep(warm: Path) -> None:
    """The point of sweeping them: the check does not depend on knowing the store."""
    from alleleforge.cache import ContentAddressedCache

    store = ContentAddressedCache("embeddings/v2/stub-0", root=warm, verify=True)
    store.put_text("c" * 64, "[0.5]")
    payload = warm / "caches" / "embeddings" / "v2" / "stub-0" / "cc" / ("c" * 64)
    payload.write_text("[0.9]")

    code, body = _verify()
    corrupt = [c for c in body["checks"] if c["status"] == "CORRUPT"]  # type: ignore[union-attr]
    assert [c["kind"] for c in corrupt] == ["embeddings/v2/stub-0"], body
    assert code == ExitCode.UNAVAILABLE


def test_a_namespace_that_stores_no_checksum_is_not_a_failure(warm: Path) -> None:
    """A `verify=False` store writes no sidecar; its absence there is not corruption.

    The sweep cannot tell which namespace an on-disk directory belonged to, so it must
    not treat "no sidecar" as the read path of a verifying store does. It is counted as
    unchecked, which is the honest third answer.
    """
    from alleleforge.cache import ContentAddressedCache

    ContentAddressedCache("legacy/v1", root=warm).put_text("d" * 64, "{}")

    code, payload = _verify()
    rows = [c for c in payload["checks"] if c["kind"] == "legacy/v1"]  # type: ignore[union-attr]
    assert [c["status"] for c in rows] == ["unverifiable"], rows
    assert code == ExitCode.OK
