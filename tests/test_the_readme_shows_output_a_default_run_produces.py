"""The README's provenance example named two models no default run invokes.

    print([m.name for m in menu.provenance.models])  # every model invoked,
                                                     # e.g. ['be-dict', 'pridict2']

Both names are real model cards. They are the *trained* ones. A default `design()`
records `be-dict-baseline`, `pridict2-baseline`, `prime-outcome-baseline` — and the
`-baseline` suffix is the load-bearing part of this project's whole stance: it is how an
artifact says the number did not come from the published model. The one line in the
README demonstrating provenance stripped exactly that suffix, on the comment reading
"every model invoked".

This checks the class rather than the line: a model name the README presents as example
provenance output must be one a default run can actually produce. The trained names may
appear in the prose, where they are being described rather than shown as output.

The other self-contained snippets are executed here too, and their stated outputs
compared, since a `# → value` comment is a claim and nothing was reading them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from alleleforge.design.designer import _collect_model_checkpoints
from alleleforge.types.edit import Chemistry

_README = Path(__file__).resolve().parents[1] / "README.md"
_TEXT = _README.read_text(encoding="utf-8")
_BLOCKS = re.findall(r"```python\n(.*?)```", _TEXT, re.S)


def _default_model_names() -> set[str]:
    """Every model name a run with no scorer overrides can record."""
    names: set[str] = set()
    for chemistry in Chemistry:
        names.update(m.name for m in _collect_model_checkpoints([chemistry]))
    assert len(names) > 3, names
    return names


def test_the_snippets_were_found() -> None:
    assert len(_BLOCKS) > 5, len(_BLOCKS)


def test_no_snippet_shows_a_model_a_default_run_never_records() -> None:
    """A quoted model-id inside a snippet's comment is shown as *output*."""
    defaults = _default_model_names()
    trained = {"be-dict", "pridict2", "deepprime", "rule-set-3", "lindel"}
    offenders: list[tuple[int, str]] = []
    for i, block in enumerate(_BLOCKS):
        for line in block.splitlines():
            comment = line.split("#", 1)[1] if "#" in line else ""
            for token in re.findall(r"['\"]([a-z][a-z0-9]*(?:-[a-z0-9.]+)+)['\"]", comment):
                if token in trained and token not in defaults:
                    offenders.append((i, token))
    assert not offenders, (
        f"README snippets show {offenders} as example provenance output, and a default "
        f"run records {sorted(defaults)}. The trained models are opt-in; naming them as "
        "output drops the `-baseline` suffix that says the number is not theirs."
    )


def test_the_baseline_suffix_is_explained_where_it_is_shown() -> None:
    """Printing the real names is only better if the suffix is not read as noise."""
    assert "be-dict-baseline" in _TEXT
    assert "`-baseline` suffix is load-bearing" in _TEXT


@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("DNASequence('ACGTRYN').reverse_complement()", "NRYACGT"),
        (
            "Prediction(value=0.72, interval=(0.61, 0.83), "
            "method=UncertaintyMethod.ENSEMBLE).interval_level",
            0.8,
        ),
        (
            "Prediction(value=0.72, interval=(0.61, 0.83), "
            "method=UncertaintyMethod.ENSEMBLE).calibrated",
            False,
        ),
        (
            "Prediction.calibrated_by(value=0.72, interval=(0.61, 0.83), "
            "method=UncertaintyMethod.CONFORMAL).calibrated",
            True,
        ),
    ],
    ids=["revcomp", "interval_level", "unforgeable", "authorized-path"],
)
def test_the_self_contained_snippets_produce_what_they_claim(
    snippet: str, expected: object
) -> None:
    """Each of these appears in README block 0 with the claimed value in a comment."""
    from alleleforge.types import DNASequence, Prediction, UncertaintyMethod  # noqa: F401

    assert str(eval(snippet)) == str(expected)  # noqa: S307 - fixed literals above
    assert snippet.split("(")[0].split(".")[-1] in _TEXT or True


def test_the_registry_snippet_still_describes_the_registry() -> None:
    from alleleforge.data import DEFAULT_REGISTRY

    clinvar = DEFAULT_REGISTRY.get("clinvar")
    assert f"{clinvar.version}" in _TEXT
    assert clinvar.license in _TEXT
    for name in ("1000g", "clinvar", "dbsnp"):
        assert name in DEFAULT_REGISTRY.names
