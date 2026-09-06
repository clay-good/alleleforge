"""The README's design principles, checked as claims rather than read as prose.

A principle is a specification with no test behind it, which is how principle 2
("never a bare float") came to be true on every render except the cohort triage line,
and how principle 3 came to claim population-aware search "by default" when the scan
is reference-only unless the user supplies a frequency source — a claim the same
README contradicts in its own CLI section.

These pin the mechanically checkable ones. A principle that cannot be checked here is
not thereby true; it just needs a different kind of evidence.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_every_registry_dataset_and_model_is_cited_and_versioned() -> None:
    """Principle 8: cite everything — for everything the project itself ships.

    A *user-supplied* input has no literature to cite and is pinned by content hash
    instead; the principle now says so. This covers what the registries vendor, which
    is the part the project is actually making a promise about.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.model_zoo.registry import default_registry

    datasets = [DEFAULT_REGISTRY.get(name) for name in DEFAULT_REGISTRY.names]
    assert datasets, "no datasets registered — the check below would be vacuous"
    for descriptor in datasets:
        assert descriptor.citation, f"dataset {descriptor.name} has no citation"
        assert descriptor.version, f"dataset {descriptor.name} has no version"

    zoo = default_registry()
    cards = [zoo.get(name) for name in zoo.names]
    assert cards, "no model cards registered"
    for card in cards:
        assert card.citation, f"model {card.name} has no citation"
        assert card.version, f"model {card.name} has no version"


def test_the_principles_do_not_claim_population_awareness_by_default() -> None:
    """Principle 3, as stated, was false, and contradicted the same README's CLI section.

    Without `--gnomad` / `--haplotypes` / `--patient-vcf` the scan is reference-only.
    The tool says so at every surface; the headline principle said the opposite. This
    guards the specific overclaim rather than the wording around it.
    """
    # `openspec/project.md` is included because it is the file `_stated_principles`
    # calls the source of truth — and it was the one still saying "by default" after
    # the README and the docs had been corrected. A guard that reads every surface
    # except the canonical one is the shape this project keeps finding.
    prose = "".join(
        (_ROOT / name).read_text() for name in ("README.md", "docs/index.md", "openspec/project.md")
    )
    lowered = prose.lower()
    for overclaim in (
        "population-aware by default",
        "searches population variation by default",
        "ancestry-stratified by default",
    ):
        assert overclaim not in lowered, (
            f"the prose claims {overclaim!r}, but the scan is reference-only unless a "
            "frequency source is supplied"
        )
    # ...and the honest form is present, so this cannot be satisfied by deleting the claim.
    assert "reference-only" in lowered


def test_every_scoring_function_is_cited_in_the_output() -> None:
    """Principle 8's third clause: "in code **and in output provenance**".

    Datasets and models were covered; scoring functions were not. The published
    references for CFD and MIT lived in `offtarget/scoring.py`'s module docstring, and
    a report named its scorer `CFD` with weights `doench-2016-cfd` and carried no
    reference at all — while the heuristic efficiency and outcome models each shipped
    one through their registry cards. The off-target score is the number a reviewer is
    most likely to ask the provenance of, and it was the one attribution that did not
    travel with the result.
    """
    from alleleforge.offtarget.scoring import SCORER_CITATIONS, scorer_citation
    from alleleforge.types.offtarget import ScoreMethod

    # Every scorer the engine can be configured with, not just the ones we remembered.
    for method in ScoreMethod:
        assert scorer_citation(method), f"scoring method {method.value} has no citation"
    assert set(SCORER_CITATIONS) == set(ScoreMethod)

    # ...and by the display name an OffTargetReport actually records, which is what
    # the first version of this got wrong: it resolved the enum only, so every real
    # report looked uncited.
    from alleleforge.offtarget.scoring import Cas12aCfdScorer, CfdScorer, MitScorer

    for cls in (CfdScorer, MitScorer, Cas12aCfdScorer):
        assert scorer_citation(cls.name), f"scorer display name {cls.name!r} resolves to nothing"

    # An unknown scorer reads as uncited rather than as a citation-shaped placeholder.
    assert scorer_citation("not-a-scorer") is None


#: How each principle is evidenced, keyed by number and carrying the *title* it was
#: written against. Every principle in the source of truth must appear here — with the
#: test that checks it, or with the reason it cannot be checked mechanically. The
#: alternative is what R153 found: a test file whose name promises coverage of "the
#: principles" while silently covering some of them.
#:
#: The title is recorded, not just the number, because a number is an index and an
#: index is not the thing. Principle 3's evidence is a test about that principle's
#: exact wording; reword the principle and the evidence is stale while a
#: number-keyed check stays green — the same defect R237 found in the CI mirror,
#: which compared job *names* to target *names*.
_PRINCIPLE_EVIDENCE: dict[int, tuple[str, str]] = {
    1: (
        "Variant-first",
        "structural: `design()` and every CLI/web entry point take a variant, not a guide",
    ),
    2: (
        "Honest uncertainty",
        "structural: `Prediction` requires interval + method and defaults the two flags; "
        "`ensure_prediction`/`BareFloatError` reject a bare float at the scorer boundary",
    ),
    3: (
        "Population-aware, and explicit when it cannot be",
        "test_the_principles_do_not_claim_population_awareness_by_default",
    ),
    4: (
        "Wrap, don't rebuild",
        "not mechanically checkable: 'wrap, don't rebuild' is a judgement about whether a "
        "new model fills a genuine coverage gap, and no assertion decides that",
    ),
    5: (
        "Reproducible to the byte",
        "scripts/reproduce.py, gated in CI, plus the benchmark reproducibility digest",
    ),
    6: (
        "Three audiences, one core",
        "not mechanically checkable as stated; the closest evidence is the cross-surface "
        "parity checks (the CLI/web/library must agree), which live with each surface",
    ),
    7: ("Typed and tested", "make ci: mypy --strict, ruff, and the suite itself"),
    8: (
        "Cite everything",
        "test_every_registry_dataset_and_model_is_cited_and_versioned and "
        "test_every_scoring_function_is_cited_in_the_output — one per noun the principle names",
    ),
}


def _stated_principles() -> dict[int, str]:
    """Return the numbered principles from `openspec/project.md`, the source of truth."""
    import re

    text = (_ROOT / "openspec" / "project.md").read_text()
    section = text.split("## Non-negotiable design principles")[1].split("\n## ")[0]
    return {int(n): title for n, title in re.findall(r"^(\d+)\. \*\*(.+?)\.?\*\*", section, re.M)}


def test_every_stated_principle_has_named_evidence() -> None:
    """A principle with no evidence recorded is a specification nobody is checking.

    This does not assert the principles hold — several cannot be asserted. It asserts
    that for each one we have written down *how* we know, so a principle cannot quietly
    join the list with nothing behind it, and a test cannot quietly cover a subset.
    """
    stated = _stated_principles()
    assert len(stated) >= 8, f"only parsed {len(stated)} principles — the parser is wrong"

    unevidenced = sorted(set(stated) - set(_PRINCIPLE_EVIDENCE))
    assert not unevidenced, (
        f"principles with no recorded evidence: "
        f"{ {n: stated[n] for n in unevidenced} }. Add a test, or record why it cannot "
        "be checked mechanically."
    )
    stale = sorted(set(_PRINCIPLE_EVIDENCE) - set(stated))
    assert not stale, f"evidence recorded for principles that no longer exist: {stale}"

    # ...and the evidence must still be attached to the principle it was written for.
    reworded = {
        number: (recorded, stated[number])
        for number, (recorded, _) in _PRINCIPLE_EVIDENCE.items()
        if number in stated and stated[number] != recorded
    }
    assert not reworded, (
        f"principles whose wording changed since their evidence was recorded: "
        f"{reworded}. The evidence may no longer be about what the principle now says "
        "— re-read it, then update the recorded title."
    )

    # A test named as evidence must actually exist in this module.
    named = [
        (n, e)
        for n, (_, e) in _PRINCIPLE_EVIDENCE.items()
        if "test_" in e and "not mechanically" not in e
    ]
    for number, evidence in named:
        for token in evidence.split():
            name = token.strip(",")
            if name.startswith("test_"):
                assert name in globals(), (
                    f"principle {number} names {name!r} as its evidence, and no such "
                    "test exists in this module"
                )


def test_the_two_statements_of_the_principles_agree() -> None:
    """The principles are written out twice; two copies of a claim can disagree.

    `openspec/project.md` is the declared source of truth and the README restates the
    list for readers. Principle 3 was corrected in the README — "not on by default,
    because AlleleForge vendors no gnomAD data" — and left as "Population-aware by
    default" in the source of truth, where the overclaim guard above did not read.
    """
    import re

    def titles(path: str, header: str) -> dict[int, str]:
        section = (_ROOT / path).read_text().split(header)[1].split("\n## ")[0]
        return {int(n): t for n, t in re.findall(r"^(\d+)\. \*\*(.+?)\.?\*\*", section, re.M)}

    spec = titles("openspec/project.md", "## Non-negotiable design principles")
    readme = titles("README.md", "## Design principles")
    assert len(spec) >= 8, spec
    differing = {
        n: (spec.get(n), readme.get(n))
        for n in set(spec) | set(readme)
        if spec.get(n) != readme.get(n)
    }
    assert not differing, (
        f"the principles disagree between their two statements: {differing}. "
        "openspec/project.md is the source of truth; the README restates it."
    )
