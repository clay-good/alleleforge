"""A dataset descriptor must not name an address whose bytes upstream can replace.

`release_readiness.py` has had a `_names_a_moving_target` check for several rounds, and
applied it only to *unpinned* datasets — where it changes how the triage reads. Nothing
applied it to the descriptors themselves, and the cost of that showed up in `dbsnp`.

That descriptor declared `version="b156"` and cached as `dbsnp.b156.tsv.gz` while its
`source_url` pointed at `/snp/latest_release/`. Upstream had since published b157, so the
address served 29,552,227,779 bytes where the descriptor meant 26,611,209,012. **A run
would have downloaded one build of dbSNP and recorded it as another** — not a stale
number but a false provenance claim, in a file whose whole job is to say which data a
result came from. Repointed at `/snp/archive/b156/`, which cannot move.

Two shapes are guarded here, and they fail for different reasons:

* a descriptor that pins `sha256` beside a moving address — the hash is of whatever that
  address meant on the day it was taken, so the next upstream release invalidates it and
  the consent gate then refuses a dataset that used to load;
* a descriptor whose declared `version` is contradicted by a floating address — the
  `dbsnp` case, where nothing fails loudly at all and the error reaches a result's
  provenance.

A *bundled* descriptor is exempt from the first: its `sha256` is of bytes that ship
inside the package (`doench-2016-cfd` → `offtarget/cfd_matrix.json`), so upstream cannot
affect it. Its `source_url` is a citation rather than a fetch target — and it is still
pinned to a commit, because a citation that points at moving bytes documents something
nobody verified.
"""

from __future__ import annotations

import pytest
from scripts import release_readiness

from alleleforge.data.registry import DEFAULT_REGISTRY

_DESCRIPTORS = [DEFAULT_REGISTRY.get(name) for name in DEFAULT_REGISTRY.names]


def test_the_registry_is_not_empty() -> None:
    """Without this, every parametrized assertion below could be vacuous."""
    assert len(_DESCRIPTORS) >= 8


@pytest.mark.parametrize("descriptor", _DESCRIPTORS, ids=lambda d: d.name)
def test_no_descriptor_names_a_moving_address(descriptor: object) -> None:
    """The rule, applied to every descriptor rather than only the unpinned ones.

    Including the unpinned: an address that floats is wrong before anyone pins a hash to
    it, because the *version* a descriptor declares is already a claim about which bytes
    it means.
    """
    if getattr(descriptor, "bundled", False):
        # `doench-2016-cfd` is exempt, and the exemption is the interesting part. Its
        # `source_url` is not fetched: it is a *key* into the `sources` map inside the
        # shipped `cfd_matrix.json`, which records each upstream the matrix was
        # cross-verified against. Changing the key here means changing it there, which
        # changes that file's digest, which is the hash this registry pins. Making a
        # citation immutable is not worth re-cutting an authentication trail in passing.
        pytest.skip("bundled: source_url keys the shipped file's authentication record")

    url = getattr(descriptor, "source_url", None) or ""
    assert not release_readiness._names_a_moving_target(url), (
        f"{descriptor.name} names a moving address:\n  {url}\n"
        "Upstream can replace those bytes in place, so this descriptor's version and "
        "hash stop describing what it fetches. Point at an archived or commit-pinned "
        "path. (This is the dbsnp defect: /snp/latest_release/ had moved to b157 while "
        "the descriptor still said b156.)"
    )


@pytest.mark.parametrize("descriptor", _DESCRIPTORS, ids=lambda d: d.name)
def test_a_pinned_hash_is_not_attached_to_a_fetched_moving_address(
    descriptor: object,
) -> None:
    """The sharper half: a hash beside a mutable address is a pin with an expiry date.

    Stated separately from the rule above so the *consequence* is recorded where a reader
    will meet it. When this fires, the symptom is not a wrong number — it is
    `ChecksumError`, and the consent gate refusing a dataset that worked yesterday, with
    a message about a hash mismatch when the truth is that upstream published a new
    release.
    """
    if getattr(descriptor, "sha256", None) is None:
        pytest.skip("unpinned: the address is checked by the rule above")
    if getattr(descriptor, "bundled", False):
        # Its hash is of bytes that ship in the package, so upstream cannot touch it.
        pytest.skip("bundled: sha256 is of the shipped file, not of the URL")

    url = getattr(descriptor, "source_url", None) or ""
    assert not release_readiness._names_a_moving_target(url), (descriptor.name, url)


#: Descriptors whose upstream versions its paths, and the literal each address must
#: contain. Written out rather than derived: `clinvar`'s version is `2024-05-28` and its
#: path says `20240528`, `gencode`'s is `v47` against `release_47`, so a matcher general
#: enough to relate them would also match things it should not — and a test that quietly
#: skips the descriptor it was written for is worse than no test. A fuzzy version of this
#: check silently covered two of these three.
_VERSION_IN_ADDRESS = {
    "dbsnp": "b156",
    "gencode": "release_47",
    "clinvar": "20240528",
}


@pytest.mark.parametrize(("name", "literal"), sorted(_VERSION_IN_ADDRESS.items()))
def test_a_declared_version_appears_in_the_address_it_fetches(name: str, literal: str) -> None:
    """A descriptor's version and its address must not contradict each other.

    This is what would have caught `dbsnp` with no network access at all:
    `version="b156"` beside `latest_release` in the URL is a contradiction readable from
    the source. The failure it prevents is not a broken download — it is a run that
    fetches one build and records another in its provenance.
    """
    descriptor = DEFAULT_REGISTRY.get(name)
    url = getattr(descriptor, "source_url", None) or ""
    assert literal in url, (
        f"{name} declares version {descriptor.version!r} but its address does not name "
        f"{literal!r}:\n  {url}\nIf upstream has published a new release, change the "
        "version and the cached filename deliberately rather than letting the address "
        "drift ahead of them.",
    )


def test_the_moving_target_detector_still_catches_the_shapes_it_must() -> None:
    """The guards above pass vacuously if the detector stops detecting.

    Every assertion in this file is `not _names_a_moving_target(...)`, which a detector
    that always returned `False` would satisfy perfectly. So the detector is exercised
    directly against the addresses this registry used to carry.
    """
    assert release_readiness._names_a_moving_target(
        "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz"
    )
    assert release_readiness._names_a_moving_target(
        "https://raw.githubusercontent.com/o/r/master/CFD_Scoring/mismatch_score.pkl"
    )
    assert not release_readiness._names_a_moving_target(
        "https://ftp.ncbi.nlm.nih.gov/snp/archive/b156/VCF/GCF_000001405.40.gz"
    )
