"""The resume refusal renders each header field as its own kind, or not at all.

:func:`~alleleforge.design.cohort._render` exists because a mismatched-resume refusal is
a message a human has to act on: dumped as `repr`, one differing ClinVar release filled
three lines with ``None``s and buried the two hashes that actually differ. Two fields get
a shape of their own — a list of dataset descriptors and a reference dict — and every
other field falls through to `repr`.

Each of those two tests is a *conjunction*: the right key **and** the right type. The
suite had one case, a `reference` dict differing from another `reference` dict, which
satisfies both arms at once and so measures neither. Dropping either arm left the suite
green:

* without the key check, any list is rendered as a dataset list and any dict as a
  genome shape — so an unrelated structured field is described as something it is not;
* without the type check, the renderer *crashes* on the value a real run hands it. A
  manifest written against a run-wide reference, resumed by a run that builds one per
  worker, carries ``reference: None`` on this side — ``None.get("contigs")`` raises, and
  the exception replacing the refusal says nothing about the mismatch it was raised to
  report.

The `or "nothing"` fallback had no case either: a run whose inputs are empty rendered as
the empty string, which reads as a truncated message rather than as "no inputs".
"""

from __future__ import annotations

import pytest

from alleleforge.design.cohort import _render

_DATASETS = [{"name": "clinvar", "version": "2026-01"}]
_REFERENCE = {"contigs": 1, "sha256": "abcdef0123456789"}


def test_a_dataset_list_is_rendered_as_names_and_versions() -> None:
    assert _render("inputs", _DATASETS) == "clinvar 2026-01"


def test_a_genome_shape_is_rendered_as_contigs_and_a_short_sha() -> None:
    assert _render("reference", _REFERENCE) == "1 contig(s), sha abcdef01"


@pytest.mark.parametrize("key", ["seed", "intent", "alleleforge_version"])
def test_a_list_under_another_key_is_not_a_dataset_list(key: str) -> None:
    """Drop the key arm and every list is announced as datasets it does not hold."""
    rendered = _render(key, _DATASETS)
    assert rendered == repr(_DATASETS)
    assert "clinvar 2026-01" not in rendered


@pytest.mark.parametrize("key", ["seed", "intent", "alleleforge_version"])
def test_a_dict_under_another_key_is_not_a_genome_shape(key: str) -> None:
    """Drop the key arm and every dict is announced as a genome of some shape."""
    rendered = _render(key, _REFERENCE)
    assert rendered == repr(_REFERENCE)
    assert "contig(s)" not in rendered


@pytest.mark.parametrize("value", [None, "clinvar 2026-01", 7])
def test_inputs_that_are_not_a_list_fall_through_rather_than_crash(value: object) -> None:
    """The refusal must survive a side that has no structured inputs at all."""
    assert _render("inputs", value) == repr(value)


@pytest.mark.parametrize("value", [None, "hg38", 7])
def test_a_reference_that_is_not_a_dict_falls_through_rather_than_crash(
    value: object,
) -> None:
    """A per-worker run records no run-wide reference; the refusal still has to print."""
    assert _render("reference", value) == repr(value)


def test_an_empty_input_list_says_nothing_rather_than_nothing_at_all() -> None:
    """Without the fallback the line reads `inputs: manifest has , this run has ...`."""
    assert _render("inputs", []) == "nothing"
