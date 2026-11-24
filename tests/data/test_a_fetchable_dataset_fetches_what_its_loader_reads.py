"""Pinning a hash makes a dataset fetchable, so the fetch must produce a loadable file.

`dataset_status` computes `fetchable` as `bool(sha256 and source_url) and not bundled`.
So adding a `sha256` to a descriptor is not only a provenance improvement — it switches
the fetch path on, and the fetch saves whatever `source_url` serves under the
descriptor's `filename`.

This file exists because adding one looked like obvious progress and would have been a
defect. R0 lists `dbsnp` as "one fetch-and-hash away", and the hash was being computed —
26.6 GB streamed from NCBI's archive — when the check below became apparent. Upstream
publishes `GCF_000001405.40.gz`, a **VCF**. The descriptor's `filename` is
`dbsnp.b156.tsv.gz`, and `DbSnpDB` has exactly one reader, `from_tsv`, which wants an
`rsid chrom pos ref alt` table. Pinning the hash would have made the tool download 26.6 GB,
save it under a `.tsv.gz` name, and fail on the header — the refusal pinned in
`test_a_dbsnp_header_missing_its_core_columns_is_refused.py`. A criterion would have moved
from 3/8 to 4/8 while the dataset became *less* usable than when it was unpinned.

The rule is read off the descriptors that already work rather than invented: both
genuinely fetchable datasets (`clinvar`, `gencode`) name an upstream file whose basename
**is** their `filename`. The fetch saves exactly what upstream published and the loader
reads that form. Every descriptor whose `filename` differs names a *derived* table the
caller produces — which is why it is, correctly, not fetchable.
"""

from __future__ import annotations

import pytest

from alleleforge.data.registry import DEFAULT_REGISTRY

_DESCRIPTORS = [DEFAULT_REGISTRY.get(name) for name in DEFAULT_REGISTRY.names]


def _is_fetchable(descriptor: object) -> bool:
    """Mirror `dataset_status`'s own definition, deliberately duplicated.

    Importing the status helper would make this test pass whenever that helper changed
    its mind, which is the thing being guarded. The condition is three fields and is
    quoted from `registry.py` so a reader can compare them by eye.
    """
    return bool(
        getattr(descriptor, "sha256", None) and getattr(descriptor, "source_url", None)
    ) and not getattr(descriptor, "bundled", False)


def test_the_premise_some_datasets_are_fetchable_and_some_are_not() -> None:
    """Both halves must be non-empty or the assertions below prove nothing."""
    fetchable = [d for d in _DESCRIPTORS if _is_fetchable(d)]
    rest = [d for d in _DESCRIPTORS if not _is_fetchable(d)]
    assert fetchable, "nothing is fetchable; the rule below would be vacuous"
    assert rest, "everything is fetchable; the contrast this test draws is gone"


@pytest.mark.parametrize("descriptor", _DESCRIPTORS, ids=lambda d: d.name)
def test_a_fetchable_dataset_saves_the_file_upstream_actually_publishes(
    descriptor: object,
) -> None:
    """`filename` must be the basename of `source_url` wherever a fetch can happen.

    When they differ, the fetch writes upstream's artifact under a name that implies a
    different form, and the loader fails on content it was never meant to read. The
    failure arrives *after* the download, which for these datasets is tens of gigabytes.
    """
    if not _is_fetchable(descriptor):
        pytest.skip("not fetchable: no fetch happens, so nothing is saved under filename")

    upstream = (descriptor.source_url or "").rsplit("/", 1)[-1]
    assert descriptor.filename == upstream, (
        f"{descriptor.name} is fetchable but would save {upstream!r} as "
        f"{descriptor.filename!r}. The fetch path writes what `source_url` serves under "
        "`filename`, so these must name the same artifact. If `filename` is a *derived* "
        "table the caller produces (a sites TSV, a haplotype table), then this dataset is "
        "caller-supplied and must not carry a `sha256` — pinning one switches on a fetch "
        "whose result the loader cannot read."
    )


@pytest.mark.parametrize(
    "name",
    ["dbsnp", "gnomad", "1000g", "hgdp", "encode"],
)
def test_a_caller_supplied_dataset_stays_unpinned(name: str) -> None:
    """The five whose `filename` is a derived table must not become fetchable.

    Named individually rather than derived, because the point is to make pinning one a
    deliberate act with a failing test to read. Each of these needs a conversion the
    caller performs — `DbSnpDB.from_tsv` wants `rsid chrom pos ref alt` where NCBI
    publishes a VCF — so a `sha256` here is not a stronger guarantee but a broken fetch.

    If a converter ever ships, the honest change is to pin the *converted* artifact and
    name it in `filename`, not to pin upstream's.
    """
    descriptor = DEFAULT_REGISTRY.get(name)
    assert descriptor.sha256 is None, (
        f"{name} now pins a sha256, which makes it fetchable. Check that the fetch "
        "produces something its loader can read: upstream publishes a different form "
        "from the derived table `filename` names. See "
        "tests/data/test_a_fetchable_dataset_fetches_what_its_loader_reads.py."
    )
    assert descriptor.filename != (descriptor.source_url or "").rsplit("/", 1)[-1], (
        f"{name}'s filename now matches its upstream basename, so it may no longer be "
        "a derived artifact — re-derive whether it belongs in this list"
    )


def test_the_two_fetchable_datasets_are_the_ones_expected() -> None:
    """Fetchability is a behavioural claim, so changing the set is a deliberate edit.

    A dataset becoming fetchable means the tool will download and hash-verify it on
    request. That is a good thing when the artifact is loadable and a trap when it is
    not, and the difference is invisible from the diff that adds a `sha256`.
    """
    fetchable = {d.name for d in _DESCRIPTORS if _is_fetchable(d)}
    assert fetchable == {"clinvar", "gencode"}, sorted(fetchable)
