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
    prose = (_ROOT / "README.md").read_text() + (_ROOT / "docs" / "index.md").read_text()
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
