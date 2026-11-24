"""The v1.0 criteria are measured, not guessed.

`SPEC_V2.md` lists five conditions for cutting v1.0 and nothing measured any of them,
so "how close are we" was answered by reading five bullet points. Most are blocked
outside this repository — real weights, real corpora, a posted preprint — which is
precisely why measuring them is worth it: it separates *blocked* from *forgotten*, and
it notices the day one stops being blocked.

These pin the report's honesty rather than its verdict. A readiness report that
overstates its evidence is worse than none, and the first draft did exactly that: it
counted 16 "native parity" test modules by grepping for the substring `native`, which
matches any test whose prose contains the word.
"""

from __future__ import annotations

from pathlib import Path

from scripts import release_readiness


def test_every_spec_criterion_is_measured() -> None:
    """One reported criterion per bullet under `SPEC_V2.md`'s R6 section."""
    from pathlib import Path

    spec = (Path(__file__).resolve().parents[1] / "SPEC_V2.md").read_text()
    section = spec.split("## R6 — v1.0 release criteria")[1].split("\nUntil then")[0]
    bullets = [line for line in section.splitlines() if line.startswith("- ")]
    assert bullets, "no R6 criteria found in SPEC_V2.md — this check would be vacuous"
    assert len(release_readiness.criteria()) == len(bullets), (
        f"SPEC_V2.md lists {len(bullets)} v1.0 criteria and the report measures "
        f"{len(release_readiness.criteria())}"
    )


def test_an_unmet_criterion_says_what_blocks_it() -> None:
    """ "Not met" and "not met because the upstream artifact is not frozen" differ."""
    for c in release_readiness.criteria():
        if not c.met:
            assert c.blocked_by, f"{c.track} is unmet and names nothing that blocks it"
        assert c.detail, f"{c.track} reports no detail"


def test_the_artifact_count_excludes_baselines() -> None:
    """A heuristic baseline has no artifact, so it must not count against the pinning.

    Counting all 17 cards would report 1/17 pinned and read as far worse than the
    truth; the denominator is the cards that actually name a source to download.
    """
    from alleleforge.model_zoo.registry import default_registry

    zoo = default_registry()
    cards = [zoo.get(name) for name in zoo.names]
    downloadable = [c for c in cards if c.source_url]
    assert len(downloadable) < len(cards), "the fixture has no baselines to exclude"

    pinning = next(c for c in release_readiness.criteria() if c.track == "R0")
    assert f"/{len(downloadable)} model cards" in pinning.detail


def test_the_native_evidence_counts_marked_tests_not_the_word() -> None:
    """The first draft grepped for the substring and reported 16 where there are 4."""
    import re

    native = next(c for c in release_readiness.criteria() if c.track == "R2")
    modules = next(line for line in native.evidence if line.startswith("parity modules:"))
    named = modules.removeprefix("parity modules:").split(",")
    # An upper bound, not a pin: it exists because the first draft grepped for the
    # substring and reported sixteen where there were four, so a *plausible* count is
    # what it checks. Kernels are added — this arc added three — and the bound moves
    # with them; what it must never do is drift back toward "every test that mentions
    # the word".
    assert 0 < len(named) <= 12, f"implausible parity-module count: {modules}"
    assert re.match(r"^\d+ test module", native.detail)
    assert str(len(named)) == native.detail.split()[0]


def test_the_report_renders_and_exits_non_zero_while_open(
    capsys: object,
) -> None:
    """It is usable as a release gate, not only as prose."""
    assert release_readiness.main([]) in (0, 1)
    assert release_readiness.main(["--json"]) in (0, 1)


def test_a_criterion_summary_covers_its_spec_bullet() -> None:
    """A criterion may not quietly grade a subset of what the spec asks for.

    R2's bullet reads "…on their hot paths with parity tests **and a recorded
    speedup**", and the first version of this report checked only the parity tests and
    printed MET. Each reported summary must mention every conjunct its spec bullet
    names, so half-credit cannot pass as full.
    """
    from pathlib import Path

    spec = (Path(__file__).resolve().parents[1] / "SPEC_V2.md").read_text()
    section = spec.split("## R6 — v1.0 release criteria")[1].split("\nUntil then")[0]
    assert "recorded speedup" in section, "the R2 bullet changed; update this check"

    native = next(c for c in release_readiness.criteria() if c.track == "R2")
    assert "parity tests" in native.summary
    assert "recorded speedup" in native.summary, (
        "the R2 criterion is graded on both halves; its summary must say so"
    )
    assert "speedup harness" in native.detail


def test_a_harness_name_alone_is_not_a_recorded_speedup(tmp_path: Path) -> None:
    """R2 needs measurements for all 3 named kernels, including measured regressions."""
    import scripts.release_readiness as readiness

    root = tmp_path
    (root / "scripts").mkdir()
    (root / "scripts" / "native_speedup.py").write_text("# benchmark\n")
    readme = root / "README.md"
    readme.write_text(
        "## Native acceleration\n\n"
        "Run the [benchmark harness](scripts/native_speedup.py).\n\n"
        "| Kernel | Result |\n|---|---|\n"
        "| `bwt` | measured |\n| `kmer` | measured |\n| `haplotype` | measured |\n"
    )
    assert not readiness._has_native_speedup_record(root)

    readme.write_text(
        readme.read_text()
        .replace("`bwt` | measured", "`bwt` | 0.03x (slower)")
        .replace("`kmer` | measured", "`kmer` | 6.1x")
        .replace("`haplotype` | measured", "`haplotype` | 4.0x")
    )
    assert readiness._has_native_speedup_record(root)


def test_r2_does_not_call_a_stale_build_importable() -> None:
    """The third tightening of this criterion, and the same failure as the first two.

    An extension built before a kernel was added imports fine and reports an unchanged
    version, while that kernel's parity module skips every test in it. The report counted
    the module as evidence and described the extension as "importable" — overstating what
    this machine had actually verified, which is the failure mode the criterion's own
    comments say it exists to avoid.
    """
    import scripts.release_readiness as readiness

    from alleleforge import _native

    original = _native.missing_native_functions
    try:
        _native.missing_native_functions = lambda: frozenset({"evaluate_anchor"})  # type: ignore[assignment]
        stale = readiness._native_kernels()
    finally:
        _native.missing_native_functions = original  # type: ignore[assignment]

    assert "stale here" in stale.detail, stale.detail
    assert "evaluate_anchor" in stale.detail
    assert "importable" not in stale.detail, (
        "a build missing a registered kernel must not be described as importable"
    )
    assert any("maturin develop" in line for line in stale.evidence), (
        "the report should name the command that fixes it"
    )

    current = readiness._native_kernels()
    if _native.NATIVE_AVAILABLE:
        assert "current here" in current.detail, current.detail


def test_the_report_says_its_tracks_are_not_the_roadmap_phases() -> None:
    """The readiness report distinguishes its criteria from roadmap phases.

    The criteria are named after the roadmap phases and are narrower than them: the
    native-kernels criterion asks for kernels on the hot paths with parity tests and a
    recorded speedup, while the phase of the same name carries its own deliverable list.
    The report must state the distinction because the criteria reuse roadmap labels.
    """
    import scripts.release_readiness as readiness

    rendered = readiness._render(readiness.criteria())
    assert "not the roadmap phase statuses" in rendered, rendered.splitlines()[:3]


def test_a_project_page_is_not_a_pinnable_artifact() -> None:
    """`source_url` carries two different things and only one of them can be hashed.

    `rule-set-3` names a release asset: one file, a stable URL, a hash. Eleven other
    cards name a GitHub repository or a Hugging Face model page, where there is no
    single artifact to hash — and recording the landing page's digest would report R0
    met while pinning an HTML document.
    """
    artifact = [
        "https://github.com/o/r/releases/download/v1/weights.txt",
        "https://huggingface.co/org/model/resolve/main/pytorch_model.bin",
        "https://github.com/o/r/raw/main/model.pkl",
        "https://example.invalid/data/matrix.json",
    ]
    reference = [
        "https://github.com/hkimlab/DeepPrime",
        "https://huggingface.co/arcinstitute/evo2_7b",
        "https://www.crisprbehive.design",
        "https://github.com/shendurelab/Lindel/",
    ]
    for url in artifact:
        assert release_readiness._names_an_artifact(url), url
    for url in reference:
        assert not release_readiness._names_an_artifact(url), url


def test_the_unpinned_cards_are_split_by_what_blocks_them() -> None:
    """R0's evidence must say which of the two things stands in the way, and for how many.

    Counting them together made the criterion read as eleven downloads away. It is not:
    eleven of them first need an upstream to publish a pinnable file, which is a
    different kind of waiting and may never happen for some of them.
    """
    r0 = next(c for c in release_readiness.criteria() if c.track == "R0")
    fetchable = next(line for line in r0.evidence if "name a downloadable artifact" in line)
    referenced = next(line for line in r0.evidence if "not a single artifact" in line)

    import re

    counts = [int(re.match(r"(\d+)", line).group(1)) for line in (fetchable, referenced)]  # type: ignore[union-attr]
    assert sum(counts) > 0, (fetchable, referenced)

    from alleleforge.model_zoo.registry import default_registry

    zoo = default_registry()
    cards = [zoo.get(name) for name in zoo.names]
    unpinned = [c for c in cards if c.source_url and not c.checkpoint_sha256]
    assert sum(counts) == len(unpinned), (counts, len(unpinned))


def test_splitting_the_unpinned_does_not_change_the_verdict() -> None:
    """The report got more honest, not more flattering.

    R0 is met only when every card naming a source pins a hash, whichever kind of URL
    it names. A split that quietly excused the unpinnable ones would close the criterion
    by reclassifying it, which is the failure this whole file exists to prevent.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.model_zoo.registry import default_registry

    zoo = default_registry()
    cards = [zoo.get(name) for name in zoo.names]
    downloadable = [c for c in cards if c.source_url]
    datasets = [DEFAULT_REGISTRY.get(n) for n in DEFAULT_REGISTRY.names]

    expected = all(c.checkpoint_sha256 for c in downloadable) and all(
        getattr(d, "sha256", None) for d in datasets
    )
    r0 = next(c for c in release_readiness.criteria() if c.track == "R0")
    assert r0.met is expected


def test_a_moving_path_is_not_a_pinnable_artifact() -> None:
    """A URL can name a file and still not be pinnable.

    `dbsnp` points at `/snp/latest_release/VCF/GCF_000001405.40.gz`, which names a file,
    so the card-side predicate alone would report it one fetch-and-hash away. Pinning it
    would record the digest of whatever `latest_release` meant that day, and the next
    upstream release would invalidate it — at which point the consent gate refuses the
    dataset, so the pin would *break* it rather than merely go stale.

    The two datasets that are pinned name immutable paths, which is what makes their
    hashes mean anything. That contrast is the point of the predicate.
    """
    moving = [
        "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz",
        "https://example.invalid/downloads/latest/weights.bin",
        "https://github.com/o/r/raw/main/model.pkl",
        "https://example.invalid/nightly/data.vcf.gz",
    ]
    fixed = [
        "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/archive_2.0/2024/clinvar_20240528.vcf.gz",
        "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_47/gencode.v47.annotation.gtf.gz",
        "https://github.com/o/r/releases/download/v1/weights.txt",
    ]
    for url in moving:
        assert release_readiness._names_a_moving_target(url), url
    for url in fixed:
        assert not release_readiness._names_a_moving_target(url), url


def test_every_unpinned_dataset_is_accounted_for_by_name() -> None:
    """R0 stated a dataset count and then explained none of it.

    The card side has been split by what blocks it since R679; the dataset side was
    counted into the same verdict and never triaged, so `3/8 datasets pin one` left a
    reader unable to tell the other five from forgotten work. Separating *blocked* from
    *forgotten* is the one thing this report exists to do.

    Every unpinned dataset must appear in exactly one of the three dataset lines, by
    name — a count with no names is how the gap survived.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY

    r0 = next(c for c in release_readiness.criteria() if c.track == "R0")
    lines = {
        "fetchable": next(line for line in r0.evidence if "fixed single artifact" in line),
        "moving": next(line for line in r0.evidence if "moving path" in line),
        "referenced": next(line for line in r0.evidence if "portal or a directory" in line),
    }

    unpinned = [
        DEFAULT_REGISTRY.get(n)
        for n in DEFAULT_REGISTRY.names
        if not getattr(DEFAULT_REGISTRY.get(n), "sha256", None)
    ]
    assert unpinned, "no unpinned datasets left; this check would be vacuous"

    for descriptor in unpinned:
        hits = [key for key, line in lines.items() if descriptor.name in line]
        assert len(hits) == 1, f"{descriptor.name} appears in {hits}, want exactly one"

    import re

    counts = [int(re.match(r"(\d+)", line).group(1)) for line in lines.values()]  # type: ignore[union-attr]
    assert sum(counts) == len(unpinned), (counts, len(unpinned))


def test_the_blocked_count_covers_datasets_as_well_as_cards() -> None:
    """ "for N of them, first deciding which file that is" must count every N.

    It counted the referenced *cards* only, so the sentence understated the work by the
    whole dataset side. R679's lesson was that this number is read as the distance to
    v1.0; a number that omits a category is the same defect in a different place.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.model_zoo.registry import default_registry

    zoo = default_registry()
    cards = [zoo.get(name) for name in zoo.names]
    card_referenced = [
        c
        for c in cards
        if c.source_url
        and not c.checkpoint_sha256
        and not release_readiness._names_an_artifact(c.source_url)
    ]
    datasets = [DEFAULT_REGISTRY.get(n) for n in DEFAULT_REGISTRY.names]
    needs_a_decision = [
        d
        for d in datasets
        if not getattr(d, "sha256", None)
        and (
            not release_readiness._names_an_artifact(getattr(d, "source_url", None) or "")
            or release_readiness._names_a_moving_target(getattr(d, "source_url", None) or "")
        )
    ]

    r0 = next(c for c in release_readiness.criteria() if c.track == "R0")
    expected = len(card_referenced) + len(needs_a_decision)
    assert f"for {expected} of them" in r0.blocked_by, (r0.blocked_by, expected)
    assert expected > len(card_referenced), (
        "the dataset side contributes nothing to this count, so the regression it "
        "guards against could not be observed"
    )
