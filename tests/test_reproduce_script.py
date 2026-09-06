"""The reproducibility gate must say what drifted, not just that something did."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import reproduce


def test_changed_paths_names_the_leaf_that_moved() -> None:
    golden = {"candidates": [{"rank": 1, "efficiency": 0.5, "flags": ["clean"]}]}
    current = {"candidates": [{"rank": 1, "efficiency": 0.7, "flags": ["clean"]}]}
    assert reproduce._changed_paths(golden, current) == ["candidates[0].efficiency: 0.5 -> 0.7"]


def test_changed_paths_reports_added_and_removed_keys() -> None:
    changes = reproduce._changed_paths({"a": 1, "b": 2}, {"a": 1, "c": 3})
    assert changes == ["b: removed (was 2)", "c: added (3)"]


def test_changed_paths_is_empty_when_nothing_moved() -> None:
    body = {"x": [1, 2, {"y": "z"}]}
    assert reproduce._changed_paths(body, json.loads(json.dumps(body))) == []


def test_a_drift_report_names_the_values_that_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gate failed with two 64-character hashes and nothing else.

    `make ci` runs this as a blocking job, so a developer whose change moved a score
    saw only that a hash differed — and the script held both bodies the whole time.
    """
    digest, body = reproduce._digest()
    drifted = json.loads(json.dumps(body))
    drifted["pareto_front"] = [*drifted["pareto_front"], 99]
    golden = tmp_path / "golden.json"
    golden.write_text(json.dumps({"sha256": "0" * 64, "n_candidates": 1, "body": drifted}))
    monkeypatch.setattr(reproduce, "GOLDEN", golden)

    assert reproduce.main([]) == 1
    err = capsys.readouterr().err
    assert "REPRODUCIBILITY DRIFT" in err
    assert "pareto_front: length" in err


def test_update_records_the_body_so_the_next_drift_is_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A golden holding only a hash makes drift invisible in review as well as in CI."""
    golden = tmp_path / "golden.json"
    monkeypatch.setattr(reproduce, "GOLDEN", golden)
    assert reproduce.main(["--update"]) == 0
    stored = json.loads(golden.read_text())
    assert stored["body"]["candidates"], "the golden must carry the result it pins"
    assert stored["sha256"] == reproduce._digest()[0]
