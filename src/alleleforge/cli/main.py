"""The ``aforge`` command-line interface (Phase 12).

A thin, reproducible, config-driven shell over the library — **no business logic
lives here**. Every command resolves its inputs, calls the same library
functions the Python API exposes, and can emit machine-readable JSON. Runs are
reproducible from the echoed config plus the global seed, and a provenance
sidecar is written next to any file output.

Subcommands:

* ``resolve`` — normalize any input form and show the variant + consequence.
* ``design`` — variant to a ranked, multi-chemistry menu (the headline command).
* ``batch`` — design a whole cohort from a VCF or variant list (streaming, resumable).
* ``offtarget`` — standalone population/haplotype-aware off-target for a spacer.
* ``data`` — inspect the dataset registry (versions, licenses, provenance).
* ``bench`` — list/run CRISPR-Bench tasks and render the leaderboard (Phase 14).

Exit codes are meaningful and distinct: ``0`` success, ``2`` usage/input error
(Typer default), ``3`` missing data, ``4`` an unavailable model or feature.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Annotated, Any, NoReturn, TypeVar

import typer

from alleleforge._version import __version__
from alleleforge.cache_sweep import FAILURES
from alleleforge.config import DEFAULT_REFERENCE, DEFAULT_SEED
from alleleforge.data.gnomad import GnomadDB
from alleleforge.data.haplotypes import Haplotype

# The cohort summary lives in the library: it is a product a Python caller and the
# web API must be able to produce, not shell plumbing. Aliased to the names the
# command bodies already use.
from alleleforge.design.cohort_summary import cohort_reference_shape_suffix as _shape_suffix
from alleleforge.design.cohort_summary import cohort_rows as _batch_rows
from alleleforge.design.cohort_summary import cohort_to_parquet as _batch_parquet
from alleleforge.design.cohort_summary import cohort_to_tsv as _batch_tsv
from alleleforge.design.designer import DEFECT_NOTE
from alleleforge.errors import MissingDependencyError, reason
from alleleforge.types.provenance import DatasetVersion
from alleleforge.types.sequence import GenomicInterval
from alleleforge.types.variant import Variant


class ExitCode(IntEnum):
    """Distinct process exit codes (``2`` is Typer's own usage-error code)."""

    OK = 0
    USAGE = 2
    MISSING_DATA = 3
    UNAVAILABLE = 4


@dataclass
class GlobalState:
    """Global options shared by every command, set in the root callback."""

    #: ``None`` when `--seed` was not given. The documented precedence is
    #: defaults < config file < environment < explicit overrides, and a flag's *default*
    #: is not an explicit override: passing `DEFAULT_SEED` here unconditionally outranked
    #: `ALLELEFORGE_SEED`, so the documented variable changed nothing on any CLI run
    #: while the library honoured it. `seed_or_default` is for the callers that need a
    #: number regardless.
    seed: int | None = None
    #: ``None`` when `--reference` was not given, for the reason `seed` above is: a
    #: flag's default is not an explicit override, and passing one unconditionally hid
    #: `ALLELEFORGE_REFERENCE` from every CLI run. Read it through `reference_build`,
    #: which resolves environment and config before falling back to the default.
    _reference_build: str | None = None
    cache_dir: Path | None = None
    verbose: bool = False

    @property
    def seed_or_default(self) -> int:
        """Return the seed a caller that cannot consult `Settings` should use."""
        return DEFAULT_SEED if self.seed is None else self.seed

    @property
    def reference_build(self) -> str:
        """Return the build label: the flag, else the environment/config, else the default.

        Resolved here rather than in the callback so `--help` and a command that never
        looks at a genome pay nothing, and so a malformed setting is reported by the
        command that needed it rather than by every invocation.
        """
        if self._reference_build is not None:
            return self._reference_build
        from alleleforge.config import get_settings

        # Through the same boundary `_load_settings` uses: a malformed setting is the
        # caller's environment, and reaching the terminal as a traceback here would undo
        # the fix one function down purely because this call site is different.
        try:
            return str(get_settings().reference)
        except ValueError as exc:
            _echo_err(f"error: {reason(exc)}")
            raise typer.Exit(ExitCode.USAGE) from None


app = typer.Typer(
    name="aforge",
    help="AlleleForge: variant-driven, uncertainty-aware CRISPR edit design.",
    no_args_is_help=True,
    add_completion=False,
)


def _echo_err(message: str) -> None:
    """Write a message to stderr."""
    typer.echo(message, err=True)


#: Which optional extra installs each third-party module a command may need. The CLI's
#: heavy imports are deferred into the command bodies, but the modules they pull in
#: import their dependencies at module level — so a missing optional package surfaces
#: as a raw ImportError traceback from inside the import, not from the guarded call.
_EXTRA_FOR_MODULE: dict[str, str] = {
    "pyfaidx": "genome",
    "pyliftover": "genome",
    "cyvcf2": "genome",
    "pysam": "genome",
    "mappy": "genome",
    "polars": "core",
    "pyarrow": "core",
    "numpy": "core",
    "hgvs": "variant",
    "torch": "ml",
    "transformers": "ml",
    "lightgbm": "cas9-rs3",
    "sglearn": "cas9-rs3",
    "fastapi": "web",
    "uvicorn": "web",
    # The command is *written* in typer, so an import failure here never reaches
    # `_missing_dependency` — it happens before this module loads. The entry point is
    # `alleleforge.cli:main`, which answers for it; this row is what keeps the two
    # namings of the extra from drifting apart.
    "typer": "cli",
}


def _carries_a_prediction(artifact: Any) -> bool:
    """Return whether ``artifact`` holds at least one candidate prediction.

    A prediction implies a scorer ran, which implies provenance should name a model.
    Duck-typed across the two shapes `verify` accepts: a `DesignReport`'s candidates
    expose `efficiency` directly, a `RankedMenu`'s expose it under `prediction`.
    """
    for candidate in getattr(artifact, "candidates", ()):
        for owner in (candidate, getattr(candidate, "prediction", None)):
            if owner is not None and getattr(owner, "efficiency", None) is not None:
                return True
    return False


def _chemistries_with_no_named_model(artifact: Any, models: Any) -> list[str]:
    """Return the chemistries on ``artifact``'s menu that ``models`` names nothing for.

    :func:`_carries_a_prediction` only catches an *emptied* list. But a checkpoint is
    tagged with the chemistry it scored and every candidate states its own, so the
    finer question is answerable: deleting the two prime cards from a prime-only menu
    and leaving an unrelated base-editor one behind used to pass as "complete and
    consistent", with a populated-looking block that named nothing for a single number
    in the file.

    Grouped by :func:`~alleleforge.design.designer.model_chemistry_group`, read off the
    producer rather than restated here — the base vertical stamps one card, tagged
    ``base_abe``, that covers CBE candidates too.
    """
    from alleleforge.design.designer import model_chemistry_group
    from alleleforge.types.edit import Chemistry

    named = {ck.chemistry for ck in models}
    missing: set[str] = set()
    for candidate in getattr(artifact, "candidates", ()):
        chemistry = getattr(candidate, "chemistry", None)
        if chemistry is None:
            continue
        chemistry = Chemistry(chemistry)
        if not model_chemistry_group(chemistry) & named:
            missing.add(chemistry.value)
    return sorted(missing)


def _registered_matrices_the_result_names(artifact: Any) -> set[str]:
    """Return the *registered* scoring matrices ``artifact``'s candidates were scored by.

    The mirror of :func:`_carries_a_prediction` for datasets. `design()` records a
    scoring matrix in provenance under one explicit rule — "only matrices the registry
    knows are recorded", because the length-relative approximation is code with no bytes
    to pin — and every candidate names the matrix its off-target table was actually
    scored by. So the result carries the evidence for the rule, and `verify` can check it
    instead of taking `datasets` on trust.

    Duck-typed across the two shapes `verify` accepts, exactly as the model check is: a
    `DesignReport`'s candidates carry the reconciled label on `offtarget_matrix`, a
    `RankedMenu`'s carry the report itself and reconcile on demand. A mixed table's label
    joins both identities with ``" + "``, so split before matching.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY

    names: set[str] = set()
    for candidate in getattr(artifact, "candidates", ()):
        label = getattr(candidate, "offtarget_matrix", None)
        if label is None:
            report = getattr(candidate, "offtarget", None)
            label = report.effective_matrix() if report is not None else None
        if label is None:
            continue
        names.update(part.strip() for part in label.split(" + "))
    return {name for name in names if name in DEFAULT_REGISTRY}


#: Every "wrote <path>" confirmation goes to **stderr**, not stdout. It is a status
#: message about a side effect, and stdout is a data stream: `aforge design --out x.json
#: --json > menu.json` used to interleave the line with the ranked-menu JSON and produce
#: a file no parser accepts. The test that covered that path documented the defect
#: instead of failing on it — it dropped the first line before parsing. Same reason
#: every diagnostic here already uses `_echo_err`.


def _missing_dependency(exc: ImportError) -> NoReturn:
    """Turn an optional-dependency ImportError into an actionable message.

    `pip install "alleleforge[cli]"` is a documented install, and every design command
    needs the genome stack on top of it — so the first command a new user runs used to
    end in a `ModuleNotFoundError: No module named 'pyfaidx'` traceback. The library
    already answers this well wherever it checks explicitly ("install the 'genome'
    extra"); this gives the same answer for the imports that fail before any check runs.
    """
    module = (exc.name or "").split(".")[0]
    extra = _EXTRA_FOR_MODULE.get(module)
    fix = (
        f"pip install 'alleleforge[{extra}]'"
        if extra
        else f"pip install {module}"
        if module
        else "install the missing dependency"
    )
    _echo_err(
        f"error: this command needs the optional dependency {module or '?'}, which is "
        f"not installed: {fix}"
    )
    raise typer.Exit(ExitCode.UNAVAILABLE)


def _version_callback(value: bool) -> None:
    """Print the version and exit (eager ``--version``)."""
    if value:
        typer.echo(__version__)
        raise typer.Exit(ExitCode.OK)


@app.callback()
def main(
    ctx: typer.Context,
    seed: Annotated[
        int | None,
        typer.Option(
            help=(
                "Global random seed (recorded in provenance). Overrides "
                f"ALLELEFORGE_SEED and the config file; default {DEFAULT_SEED}."
            )
        ),
    ] = None,
    reference: Annotated[
        str | None,
        typer.Option(
            help=(
                "Reference build identifier (e.g. hg38, T2T-CHM13v2, mm39). Overrides "
                f"ALLELEFORGE_REFERENCE and the config file; default {DEFAULT_REFERENCE}."
            )
        ),
    ] = None,
    cache_dir: Annotated[
        Path | None, typer.Option(help="Override the XDG cache directory.")
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output.")] = False,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Configure global state shared by every subcommand."""
    ctx.obj = GlobalState(
        seed=seed, _reference_build=reference, cache_dir=cache_dir, verbose=verbose
    )
    # Honor --cache-dir at the process boundary: the cache root is consumed via the
    # get_settings() singleton by the dataset registry, model loader, FM-index,
    # reference index, and gnomAD fetch — none of which read the CLI's local Settings.
    # Exporting the ALLELEFORGE_CACHE_DIR env var the whole settings stack already
    # resolves (env > file > default) redirects every consumer at once, so the flag
    # stops being silently ignored. Safe because the singleton loads lazily, after this.
    if cache_dir is not None:
        os.environ["ALLELEFORGE_CACHE_DIR"] = str(cache_dir)


def _load_settings(config: Path | None, seed: int | None) -> Any:
    """Build settings, reporting a bad value as a usage error rather than a traceback.

    A malformed `ALLELEFORGE_*` variable or config key reached the terminal as a raw
    pydantic `ValidationError` and exit 1 — the code this CLI reserves for a defect in
    itself. It is the caller's environment, and the message now names the variable they
    set rather than the model field it maps to.
    """
    # Imported here rather than at module scope: this CLI defers its heavy imports so
    # `--help` stays fast, and `alleleforge.config` pulls in pydantic-settings.
    from alleleforge.config import Settings

    # Omitted, not passed as `None`: an override is "the caller said so", and
    # `Settings.load(seed=None)` would both fail validation and — if it did not —
    # outrank the environment with a non-answer. This is the whole reason
    # `ALLELEFORGE_SEED` did nothing on the command line.
    overrides = {} if seed is None else {"seed": seed}
    try:
        return Settings.load(config_file=config, **overrides)
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc


def _load_reference(fasta: Path | None, build: str = DEFAULT_REFERENCE) -> Any:
    """Load a :class:`ReferenceGenome` from a FASTA, or exit ``MISSING_DATA``.

    ``build`` labels the reference with the user's declared build (``--reference``)
    rather than a hard-coded ``hg38``, so coordinates and provenance reflect the
    genome the caller actually supplied.
    """
    if fasta is None:
        _echo_err("error: --reference-fasta is required for this command")
        raise typer.Exit(ExitCode.MISSING_DATA)
    if not fasta.is_file():
        _echo_err(f"error: reference FASTA not found: {fasta}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    from alleleforge.genome.reference import ReferenceGenome

    try:
        # Index eagerly so a malformed FASTA fails here, with a message, rather than as
        # a traceback from whichever fetch happened to run first. An empty file, a
        # truncated download and a FASTA that is really a VCF all land here.
        #
        # A *header-only* FASTA indexes fine — it has a contig with no bases — so no
        # check here can catch it. That case is reported where it matters, by the
        # search's searchable-bases accounting: a scan over no sequence says so instead
        # of returning a spotless report.
        reference = ReferenceGenome(fasta, build=build)
    except Exception as exc:  # noqa: BLE001 - pyfaidx raises its own indexing errors
        # One handler on purpose. A narrower `(OSError, ValueError, KeyError)` clause in
        # front of this changed nothing observable — the indexer's own exception type is
        # not in that set, and everything else it raises lands here anyway. Two clauses
        # differing only in the verb is a branch no test can distinguish.
        _echo_err(f"error: cannot read reference FASTA {fasta}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc
    return reference


def _emit(payload: dict[str, Any], *, as_json: bool, human: str) -> None:
    """Print JSON or a human string depending on ``as_json``."""
    typer.echo(json.dumps(payload, indent=2, default=str) if as_json else human)


@app.command()
def resolve(
    ctx: typer.Context,
    variant: Annotated[
        str,
        typer.Argument(
            help="Variant to design for. Coordinates (chrom:pos:ref>alt, 1-based as in a VCF) "
            "and a VCF record work everywhere. A ClinVar accession (VCV…) needs "
            "--clinvar and a dbSNP rsID (rs…) needs --dbsnp, each naming a release you "
            "supply — neither is ever downloaded. A coding/protein HGVS string (c./p.) "
            "needs a projector from the `hgvs` library, which this surface has no way to "
            "supply; genomic g. works without one."
        ),
    ],
    reference_fasta: Annotated[
        Path | None, typer.Option(help="Reference FASTA for left-alignment + ref validation.")
    ] = None,
    clinvar: Annotated[
        Path | None,
        typer.Option("--clinvar", help="ClinVar VCF release to look a `VCV…` accession up in."),
    ] = None,
    dbsnp: Annotated[
        Path | None,
        typer.Option("--dbsnp", help="dbSNP `rsid chrom pos ref alt` TSV to look an `rs…` up in."),
    ] = None,
    vep: Annotated[bool, typer.Option("--vep", help=_VEP_HELP)] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Normalize any input form to a canonical variant (debugging aid)."""
    from alleleforge.design.designer import _reference_snapshot
    from alleleforge.report.builder import (
        COORDINATE_NOTE,
        COORDINATE_SYSTEM,
        VARIANT_POSITION_NOTE,
    )
    from alleleforge.variant.resolver import resolve as resolve_variant

    state: GlobalState = ctx.obj
    reference = (
        _load_reference(reference_fasta, state.reference_build)
        if reference_fasta is not None
        else None
    )
    try:
        resolved = resolve_variant(
            variant,
            build=state.reference_build,
            reference=reference,
            effect=_effect_predictor(vep),
            clinvar=_load_clinvar(clinvar),
            dbsnp=_load_dbsnp(dbsnp),
        )
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc
    v = resolved.variant
    # `variant_class` is computed from the allele *lengths*, so a one-base ref and a
    # one-base alt is an `snv` whether or not they differ. A variant whose alleles are
    # equal changes nothing, and the design path already refuses to build a reagent
    # for one — this command, whose whole job is to say what an input means, said
    # `snv` and nothing else. Reported rather than refused: a reference call is a
    # legitimate VCF row and `aforge batch` reads VCFs.
    changes = v.ref != v.alt
    payload = {
        "variant": str(v),
        "variant_class": v.variant_class.value,
        "changes_the_sequence": changes,
        "build": v.build,
        "source": resolved.source,
        # Naming the source form ("clinvar") does not say *which release* answered.
        # Two dbSNP builds can put one rsID at two loci, so the descriptor of the
        # file that produced this variant is what tells the two runs apart — the
        # same pin the reference already gets below.
        "resolved_from": [d.model_dump(mode="json") for d in resolved.sources],
        # What the database asserts, on the command whose entire job is saying what an
        # input means. An accession is chosen for its classification, not its
        # coordinates — that is why the resolver carries the assertion at all — and this
        # payload reported `source: clinvar` and dropped the whole difference between
        # `VCV000012345` and the coordinates it stands for. `None` here means no
        # database asserted anything, which for a coordinate input is simply the truth.
        "clinical_significance": (
            resolved.clinical_assertion.significance.value
            if resolved.clinical_assertion is not None
            else None
        ),
        # The class alone is not the claim: "Pathogenic, no assertion criteria provided"
        # and "Pathogenic, reviewed by expert panel" are the same class and very
        # different evidence. The model carries both for that reason; so does this.
        "clinical_review_status": (
            resolved.clinical_assertion.review_status
            if resolved.clinical_assertion is not None
            else None
        ),
        "working_interval": str(resolved.working_interval),
        # Every locus on this payload — the working interval, and the position inside
        # `variant` — is 0-based half-open, and a genome browser reads the same digits as
        # 1-based inclusive. The report, the cohort TSV and the off-target surfaces all
        # say so; `resolve`, whose entire job is telling a caller what their input means,
        # printed loci and stated no convention.
        "coordinate_system": COORDINATE_SYSTEM,
        # Whether this normalization was checked against a genome. Without a reference,
        # `resolve` skips left-alignment *and* REF-allele validation, so
        # `chr2:1006:T>A` where the genome has a G comes back as a clean, normalized
        # SNV and exits 0 — while the same input with `--reference-fasta` is refused
        # by name ("asserted ref 'T' but reference has 'G' (wrong build?)"). The two
        # payloads were byte-identical: an unchecked variant and a verified one were
        # indistinguishable in the artifact.
        "reference_checked": reference is not None,
        # Stated the same way as `reference_checked`, and for the same reason: a null
        # `consequence` without this flag means nobody asked, not that VEP looked and
        # found the variant unremarkable.
        "consequence_checked": vep,
        "consequence": resolved.effect.consequence.value if resolved.effect else None,
        "impact": resolved.effect.impact.name if resolved.effect else None,
        "gene": resolved.effect.gene if resolved.effect else None,
        "reference": _reference_snapshot(reference) if reference is not None else None,
        "reference_recommendation": (
            resolved.reference_recommendation.recommended_build
            if resolved.reference_recommendation is not None
            else None
        ),
        # The build name alone is an answer with no question attached. `reason` names
        # the regions that triggered it — the segdup, the centromere — which is what
        # tells a reader that alignment here is ambiguous, and so that an off-target
        # search at this locus under-reports.
        "reference_recommendation_reason": (
            resolved.reference_recommendation.reason
            if resolved.reference_recommendation is not None
            else None
        ),
    }
    note = (
        ""
        if changes
        else "\nNOTE: this does not change the sequence — the reference and alternate "
        "alleles are identical, so there is no edit to design"
    )
    recommendation = (
        f"\nNOTE: {resolved.reference_recommendation.reason}; a read cannot be placed "
        "uniquely here, so an off-target search at this locus under-reports"
        if resolved.reference_recommendation is not None
        else ""
    )
    checked = (
        f"\nreference build {v.build}{_shape_suffix(_reference_snapshot(reference))}"
        " — the REF allele was verified against it and the variant left-aligned"
        if reference is not None
        else "\nNOTE: no reference supplied, so the REF allele was NOT checked against a"
        " genome and the variant was NOT left-aligned; pass --reference-fasta to verify it"
    )
    # `COORDINATE_NOTE` is about loci, and the variant on the line above is the one
    # printed locus that does not round-trip: it is read 1-based and printed 0-based.
    # This command exists to hand a caller a normalized variant, so it is the surface
    # most likely to have its output pasted straight back in — and the only one that
    # said nothing. The refusal names the trap and both renders carry this sentence;
    # the debugging aid did not.
    human = (
        f"{v}  [{v.variant_class.value}, build {v.build}, from {resolved.source}]\n"
        f"{VARIANT_POSITION_NOTE}\n"
        f"working interval: {resolved.working_interval}\n"
        f"{COORDINATE_NOTE}{checked}{note}{recommendation}"
    )
    _emit(payload, as_json=as_json, human=human)


def _parse_populations(spec: Any) -> list[str] | None:
    """Parse ancestry labels from the CLI's comma string or a config TOML's array.

    The flag takes ``afr,eur``; a TOML file naturally writes ``["afr", "eur"]``, and
    `populations` is a whitelisted config key, so the array form arrived unwarned and
    was handed to `str.split`.

    Args:
        spec: A comma-separated string, a sequence of labels, or ``None``.

    Returns:
        The labels, or ``None`` when nothing was requested.
    """
    if spec is None:
        return None
    if isinstance(spec, str):
        parts = spec.split(",")
    elif isinstance(spec, Sequence):
        parts = [str(item) for item in spec]
    else:
        _echo_err(
            "error: populations must be a comma-separated string or an array, "
            f"not {type(spec).__name__}"
        )
        raise typer.Exit(ExitCode.USAGE)
    labels = [p.strip() for p in parts if p.strip()]
    return labels or None


def _known(values: Iterable[Any]) -> str:
    """Render a closed vocabulary for a refusal message.

    A refusal that names the rejected value and not the accepted ones sends the
    reader to `--help` for something the refusing code already has in a local
    variable. Three of this CLI's five closed-set refusals did list them; these are
    the other two.
    """
    return ", ".join(sorted(str(getattr(v, "value", v)) for v in values))


def _parse_weights(spec: Any) -> Any:
    """Parse a weights specification from the CLI or a run-config TOML.

    Three spellings mean the same thing, because a config file is TOML and should
    be writable as TOML: the CLI's ``"eff,clean,safe,simple"`` string, a
    four-element array in that same order, and a table keyed by the axis names.
    The table is the shape a result's own ``provenance.config_snapshot`` records,
    so a user reconstructing a run from its provenance writes that one.

    Args:
        spec: A string, a sequence of four numbers, a mapping keyed by axis name,
            or ``None`` for the defaults.

    Returns:
        The parsed :class:`RankingWeights`.
    """
    # The axes come from the ranker rather than a copy here: a shell that spells the
    # objective list itself cannot reach a new objective the ranker gains, and would
    # refuse the very table naming it.
    from alleleforge.design.ranking import DEFAULT_WEIGHTS, OBJECTIVES, RankingWeights

    if spec is None:
        return DEFAULT_WEIGHTS
    expected = f"'{','.join(OBJECTIVES)}', a {len(OBJECTIVES)}-element array, or a table"
    if isinstance(spec, str):
        values: Any = spec.split(",")
    elif isinstance(spec, Mapping):
        unknown = sorted(set(spec) - set(OBJECTIVES))
        missing = sorted(set(OBJECTIVES) - set(spec))
        if unknown or missing:
            _echo_err(
                f"error: weights table must name exactly {list(OBJECTIVES)}"
                + (f"; unexpected {unknown}" if unknown else "")
                + (f"; missing {missing}" if missing else "")
            )
            raise typer.Exit(ExitCode.USAGE)
        values = [spec[axis] for axis in OBJECTIVES]
    elif isinstance(spec, Sequence):
        values = list(spec)
    else:
        _echo_err(f"error: weights must be {expected}, not {type(spec).__name__}")
        raise typer.Exit(ExitCode.USAGE)
    if len(values) != len(OBJECTIVES):
        _echo_err(f"error: weights expects {expected}")
        raise typer.Exit(ExitCode.USAGE)
    try:
        # RankingWeights rejects non-finite / negative / all-zero weights; surface
        # those as a clean usage error rather than an uncaught traceback.
        return RankingWeights(
            **{axis: float(v) for axis, v in zip(OBJECTIVES, values, strict=True)}
        )
    except (TypeError, ValueError) as exc:
        _echo_err(f"error: weights must be {len(OBJECTIVES)} non-negative numbers: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc


#: Run-parameter keys a config file may carry (the rest must be `Settings` fields).
#: These mirror the design/batch command knobs; a config key outside this set and
#: the `Settings` fields is almost certainly a typo and is warned about.
_RUN_PARAM_KEYS = frozenset(
    {
        "intent",
        "chemistry",
        "populations",
        "weights",
        "max_per_chemistry",
        "no_offtarget",
        "run_offtarget",
        "trained_efficiency",
        "trained_outcome",
        "trained_base_outcome",
        "trained_prime",
        "cell_context",
        "vector_scheme",
    }
)


def _resolve_run_offtarget(no_offtarget: bool, cfg: dict[str, Any]) -> bool:
    """Return whether to run the off-target search, honoring the config file.

    A CLI ``--no-offtarget`` always skips. Otherwise the config may skip via either
    spelling — ``no_offtarget = true`` or ``run_offtarget = false`` — so a
    whitelisted config key is honored rather than silently ignored.
    """
    skip = no_offtarget or bool(cfg.get("no_offtarget", False))
    if "run_offtarget" in cfg:
        skip = skip or not bool(cfg["run_offtarget"])
    return not skip


def _load_config(path: Path | None) -> dict[str, Any]:
    """Load a run-config TOML (warning on unknown keys), or exit if it is absent."""
    if path is None:
        return {}
    if not path.is_file():
        _echo_err(f"error: config file not found: {path}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    with path.open("rb") as fh:
        cfg: dict[str, Any] = tomllib.load(fh)
    from alleleforge.config import Settings

    known = set(Settings.model_fields) | _RUN_PARAM_KEYS
    for key in cfg:
        if key not in known:
            _echo_err(
                f"warning: unknown config key {key!r} (ignored); "
                f"known keys: {', '.join(sorted(known))}"
            )
    return cfg


def _write_provenance_sidecar(out: Path, menu: Any) -> Path | None:
    """Write the ``.provenance.json`` sidecar beside ``out``, or return ``None``.

    Every written artifact gets one, so the sidecar cannot depend on which format was
    asked for — which is what happened when a new format took its own write path.
    """
    if menu.provenance is None:
        return None
    sidecar = out.with_suffix(out.suffix + ".provenance.json")
    sidecar.write_text(menu.provenance.model_dump_json(indent=2), encoding="utf-8")
    return sidecar


class OutputFormat(StrEnum):
    """Design output formats."""

    json = "json"
    tsv = "tsv"
    html = "html"
    pdf = "pdf"
    parquet = "parquet"
    #: The ranked menu itself, not the report built from it. The report truncates
    #: each candidate's outcome spectrum and points the reader at the menu for the
    #: rest; this is that document, as a file you can name rather than a stream you
    #: have to redirect.
    menu = "menu"


#: Shared by every command that can reuse a reference scan, so the two flags read the
#: same everywhere they appear.
_CACHE_HELP = (
    "Reuse an identical reference scan from a previous run, and record this one for "
    "the next. The engine consults the store only when the result is a pure function "
    "of the reference — the default scorer and no --gnomad/--haplotypes/--patient-vcf "
    "— so an augmented scan is always computed fresh. Cached reports are checksummed "
    "and re-checked on read, which costs microseconds against a scan of milliseconds "
    "and upwards; the store never evicts, and `aforge cache verify` says what it holds."
)
_GENOME_INDEX_HELP = (
    "Anchor PAMs through a persistent, memory-mapped FM-index of the reference "
    "instead of rebuilding one in memory. Identical hits (pinned by a parity test); "
    "the first run pays to build it and every later run memory-maps it."
)


def _reuse(reference: Any, *, cache: bool, index: bool) -> tuple[Any | None, Any | None]:
    """Build the off-target cache and genome index a run asked to reuse.

    Both are opt-in: a run that did not ask must neither read a store nor write one.
    """
    store = None
    if cache:
        from alleleforge.offtarget.cache import OffTargetCache

        store = OffTargetCache()
    built = None
    if index:
        from alleleforge.genome.index import GenomeIndex

        built = GenomeIndex.build_genome(reference)
    return store, built


#: Help text shared by every command's `--vep`, so the disclosure is worded once.
_VEP_HELP = (
    "Annotate the variant's predicted molecular consequence with the Ensembl VEP REST "
    "API. Opt-in because of what travels outbound: this sends the chromosome, "
    "position and both alleles to a third-party public server, and that variant may "
    "have come from a patient VCF. Without it the consequence is simply not measured."
)


def _effect_predictor(vep: bool) -> Any | None:
    """Return a VEP effect predictor when ``--vep`` was given, else ``None``.

    The flag *is* the consent: `_VEP_HELP` tells the user, at the prompt, that the
    variant leaves the machine, which is the disclosure the predictor's own consent
    gate exists to obtain.
    """
    if not vep:
        return None
    from alleleforge.variant.effect import VepRestPredictor

    return VepRestPredictor(consent=True)


def _load_encode_tracks(path: Path | None, track: str | None) -> tuple[Any | None, str | None]:
    """Load the accessibility tracks, requiring the pair to be given together.

    The adjustment needs both a source and a track name; supplying one alone is a
    mistake that would otherwise be silently ignored, leaving the efficiency
    unadjusted while the user believes it is chromatin-aware.

    A name the file does not contain is the same mistake one step further in. It
    raised ``KeyError`` inside the chemistry, which caught it as a decline reason,
    so a typo produced an **empty menu and exit 0** with the cause buried in a
    rationale paragraph. The name is checked here, where it was supplied, and the
    refusal lists what the file does contain.

    The loaded tracks are pinned by content hash like every other user-supplied
    source, because the accessibility signal moves the efficiency number and a
    provenance block naming only the track *name* cannot tell two of them apart.
    """
    if path is None and track is None:
        return None, None
    if path is None or track is None:
        _echo_err("error: --encode-tracks and --chromatin-track must be given together")
        raise typer.Exit(ExitCode.USAGE)
    from alleleforge.data.annotations import EncodeTracks

    try:
        tracks = EncodeTracks.from_bedgraph(path)
        available = tracks.tracks
        if not available:
            _echo_err(
                f"error: --encode-tracks {path} defines no tracks. Expected "
                "tab-separated 'track chrom start end value' rows; lines beginning "
                "'track', 'browser' or '#' are skipped as UCSC directives."
            )
            raise typer.Exit(ExitCode.USAGE)
        if track not in available:
            _echo_err(
                f"error: --chromatin-track {track!r} is not in {path}; "
                f"it has: {', '.join(available)}"
            )
            raise typer.Exit(ExitCode.USAGE)
        return _attach_source(tracks, path, "encode-tracks"), track
    except (OSError, ValueError) as exc:
        _echo_err(f"error: could not read --encode-tracks {path}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc


def _validate_regions(regions: list[GenomicInterval] | None, reference: Any) -> None:
    """Fail loudly on a region the reference cannot serve, before any work begins.

    The rule itself lives in the engine (`_reject_unknown_contigs`), where every caller
    passes — this is the CLI's early exit, so a bad `--region` costs a usage error
    rather than a loaded reference and a started scan, and it reports the offending
    contig with the CLI's exit code rather than as a traceback.

    Deliberately a thin call rather than a second copy of the check: two
    implementations of "is this contig known" would drift, and the engine's is the one
    the library and the web API depend on.
    """
    from alleleforge.offtarget.engine import _reject_unknown_contigs

    if not regions:
        return
    try:
        _reject_unknown_contigs(regions, reference)
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc


def _load_regions(regions: list[str] | None, bed: Path | None) -> list[GenomicInterval] | None:
    """Merge ``--region`` loci and a ``--regions-bed`` file into one restriction list.

    The parsing is the library's: a locus string and a BED row are two spellings of the
    same restriction and must be accepted or refused identically. They were not — the
    inline BED reader built intervals directly and so took an empty one that
    ``--region`` rejects by name.
    """
    from alleleforge.genome.bed import merge_region_arguments

    try:
        return merge_region_arguments(regions, bed)
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc
    except OSError as exc:
        _echo_err(f"error: could not read --regions-bed {bed}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc


def _load_haplotypes(path: Path | None) -> Iterable[Haplotype]:
    """Load a phased-haplotype panel, or return empty when none was given.

    Returns the *panel*, not a tuple of its haplotypes: the panel carries the
    provenance descriptor, and flattening it here would strip the record of which
    data made the run haplotype-aware. A panel is re-iterable, which is what
    ``design`` needs of it.
    """
    if path is None:
        return ()
    from alleleforge.data.haplotypes import HaplotypePanel

    try:
        return _attach_source(
            HaplotypePanel.from_tsv(path, source=str(path)), path, "haplotype-panel"
        )
    except KeyError as exc:
        # A wrong-schema TSV raises KeyError from the column lookup, which used to
        # surface as a bare traceback. Name the missing column and the expected header:
        # a hand-built or differently-exported panel is the ordinary cause.
        _echo_err(
            f"error: --haplotypes {path} is missing the column {exc.args[0]!r}. "
            "Expected a tab-separated header of: "
            "hap_id  chrom  start  end  population  frequency  variants"
        )
        raise typer.Exit(ExitCode.USAGE) from exc
    except (OSError, ValueError) as exc:
        _echo_err(f"error: could not read --haplotypes {path}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc


def _load_patient_variants(path: Path | None, reference: Any) -> list[Variant] | None:
    """Load personal variants from a VCF or a one-variant-per-line list.

    Each is resolved against the reference, so a patient allele asserting a
    reference base the genome does not have fails here rather than silently
    personalizing the scan with a wrong-build variant.
    """
    if path is None:
        return None
    from alleleforge.variant.resolver import resolve as resolve_one

    try:
        if path.name.endswith((".vcf", ".vcf.gz", ".bcf")):
            from alleleforge.variant import iter_vcf

            records: list[Any] = list(iter_vcf(path))
        else:
            records = _read_variant_list(path)
        variants = _PatientVariants(
            resolve_one(rec, reference=reference).variant for rec in records
        )
        # Deliberately *not* a content hash. Recording that the scan was
        # personalized, and over how many variants, is what a reader needs to
        # interpret a `patient`-origin site; fingerprinting the file itself would
        # put an identifier for a person's genotypes into a report meant to be
        # shared.
        variants.dataset_version = DatasetVersion(
            name="patient-variants",
            version=f"n={len(variants)}",
            # Caller-supplied all the same, and the most caller-supplied source there
            # is: the flag exists for a file that is nobody else's. Leaving it false
            # made the one row that can *never* be re-checked from anywhere read like a
            # registry dataset, which is the confusion the flag was added to end. It
            # carries no hash, so it says "these bytes were yours" and nothing more —
            # exactly the statement the privacy decision above permits.
            caller_supplied=True,
        )
        return variants
    except MissingDependencyError as exc:
        # A missing optional dependency (cyvcf2, for a real VCF path) already carries
        # an actionable message; it just arrived as a traceback. UNAVAILABLE, not
        # MISSING_DATA: the file is fine, the feature is not installed. Named rather
        # than `RuntimeError`: catching the base class reported a genuine defect in the
        # reader as an installation problem, telling the user to install something that
        # was already installed.
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.UNAVAILABLE) from exc
    except (OSError, ValueError, KeyError) as exc:
        _echo_err(f"error: could not read --patient-vcf {path}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc


class _PatientVariants(list[Variant]):
    """A patient's variants, able to carry a provenance descriptor.

    A bare ``list`` cannot hold the attribute ``_collect_datasets`` looks for, and
    a run personalized with someone's genotypes should say so in its provenance.
    """

    dataset_version: DatasetVersion


def _describe_source(path: Path, name: str) -> DatasetVersion:
    """Return a provenance descriptor pinning ``path`` by its content hash.

    A file a user supplies has no upstream version string, so the honest pin is
    what it *contained* on this run: two runs agree iff the bytes did. Without
    this a population- or haplotype-aware result records neither which data made
    it so nor whether any was supplied at all — and the whole point of the
    provenance block is that a result can be re-derived from it.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return DatasetVersion(
        name=name,
        version=f"sha256:{digest[:12]}",
        sha256=digest,
        # Marked, because the pin means something different for a reader: nothing in a
        # cache or a bundle holds these bytes, so `verify` cannot re-hash them and must
        # not report them as an artifact the reader could go and fetch.
        caller_supplied=True,
    )


_T = TypeVar("_T")


def _attach_source(obj: _T, path: Path, name: str) -> _T:
    """Tag a loaded source with its provenance descriptor, if it accepts one."""
    with contextlib.suppress(AttributeError, ValueError):
        obj.dataset_version = _describe_source(path, name)  # type: ignore[attr-defined]
    return obj


def _warn_if_ancestries_unbacked(
    populations: list[str] | None, gnomad: Path | None, haplotypes: Path | None
) -> None:
    """Warn when ancestry labels are requested with no ancestry-bearing data.

    ``--populations`` names the labels to stratify *by*; it supplies no alleles.
    With neither ``--gnomad`` nor ``--haplotypes``, the scan is reference-only and
    the ancestry breakdown comes back empty — which reads like "no ancestry-specific
    risk found" rather than "nothing was searched". ``--patient-vcf`` does not count:
    a personal genotype personalizes the scan but carries no population frequencies,
    so it cannot fill an ancestry breakdown either.
    """
    if populations and gnomad is None and haplotypes is None:
        _echo_err(
            "warning: --populations was given without --gnomad or --haplotypes, so no "
            "population alleles were searched. The off-target scan is REFERENCE-ONLY "
            "and the ancestry breakdown will be empty — that is 'not measured', not "
            "'clean'."
        )


def _load_gnomad(path: Path | None) -> GnomadDB | None:
    """Load the population allele-frequency sites file, if one was given."""
    if path is None:
        return None
    try:
        return _attach_source(GnomadDB.from_sites_tsv(path), path, "gnomad-sites")
    except (OSError, ValueError) as exc:
        _echo_err(f"error: could not read --gnomad {path}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc


def _load_clinvar(path: Path | None) -> Any:
    """Load the ClinVar release, if one was given.

    `ClinVarDB` implements the resolver's `ClinVarLookup` Protocol and parses a plain
    or gzipped ClinVar VCF in pure Python. It shipped for many releases while every
    shell refused an accession outright, on the stated grounds that the Protocol had
    no implementation — so the project's own flagship example, `aforge design
    VCV000012345`, had never run. The database is file-backed exactly like `--gnomad`:
    nothing fetches it, and the caller supplies the release.
    """
    if path is None:
        return None
    from alleleforge.data.clinvar import ClinVarDB

    try:
        return _attach_source(ClinVarDB.from_vcf(path), path, "clinvar")
    except (OSError, ValueError, KeyError) as exc:
        _echo_err(f"error: could not read --clinvar {path}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc


def _load_dbsnp(path: Path | None) -> Any:
    """Load the dbSNP release, if one was given. See :func:`_load_clinvar`."""
    if path is None:
        return None
    from alleleforge.data.dbsnp import DbSnpDB

    try:
        return _attach_source(DbSnpDB.from_tsv(path), path, "dbsnp")
    except (OSError, ValueError, KeyError) as exc:
        _echo_err(f"error: could not read --dbsnp {path}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc


@app.command()
def design(
    ctx: typer.Context,
    variant: Annotated[
        str,
        typer.Argument(
            help="Variant to design for. Coordinates (chrom:pos:ref>alt, 1-based as in a VCF) "
            "and a VCF record work everywhere. A ClinVar accession (VCV…) needs "
            "--clinvar and a dbSNP rsID (rs…) needs --dbsnp, each naming a release you "
            "supply — neither is ever downloaded. A coding/protein HGVS string (c./p.) "
            "needs a projector from the `hgvs` library, which this surface has no way to "
            "supply; genomic g. works without one."
        ),
    ],
    reference_fasta: Annotated[
        Path | None, typer.Option(help="Reference FASTA (required).")
    ] = None,
    intent: Annotated[
        str | None, typer.Option(help="correct | knock_out | install | revert (default: correct).")
    ] = None,
    chemistry: Annotated[
        list[str] | None,
        typer.Option(help="Restrict to chemistries (repeatable): cas9_nuclease, base_abe, ..."),
    ] = None,
    populations: Annotated[
        str | None, typer.Option(help="Comma-separated ancestry labels to stratify by.")
    ] = None,
    encode_tracks: Annotated[
        Path | None,
        typer.Option(
            "--encode-tracks",
            help=(
                "ENCODE accessibility bedGraph ('track chrom start end value') for the "
                "ePRIDICT-style open-chromatin efficiency adjustment. Needs "
                "--chromatin-track to name which track to read."
            ),
        ),
    ] = None,
    chromatin_track: Annotated[
        str | None,
        typer.Option("--chromatin-track", help="Which track in --encode-tracks to read."),
    ] = None,
    regions: Annotated[
        list[str] | None,
        typer.Option(
            "--region",
            help=(
                "Restrict the off-target search to this locus, 'chrom:start-end' "
                "— 0-based half-open, as in a BED file, NOT the 1-based form a "
                "genome browser shows. The variant inputs are the exception and take "
                "1-based VCF positions, as a VCF record holds them: the variant string "
                "itself, `--gnomad` and `--patient-vcf`. A BED file works too: "
                "--regions-bed. "
                "Whole-genome search over a real reference is slow in pure Python, so "
                "scoping to a gene panel is usually what makes a run practical."
            ),
        ),
    ] = None,
    regions_bed: Annotated[
        Path | None,
        typer.Option("--regions-bed", help="BED file of regions to restrict the search to."),
    ] = None,
    haplotypes: Annotated[
        Path | None,
        typer.Option(
            "--haplotypes",
            help=(
                "Phased common-haplotype panel TSV (plain or .gz), "
                "'#hap_id chrom start end population frequency variants' — enables the "
                "haplotype-aware pass, which catches a site that only exists on a "
                "co-inherited combination of alleles. Its start/end and the pos inside "
                "each `chrom:pos:ref>alt` are 0-based, like --region and unlike "
                "--gnomad."
            ),
        ),
    ] = None,
    patient_vcf: Annotated[
        Path | None,
        typer.Option(
            "--patient-vcf",
            help=(
                "Personal variants (VCF or one-variant-per-line list) to personalize "
                "the off-target scan — a site present in this genome but not the "
                "reference is nominated as `patient` origin."
            ),
        ),
    ] = None,
    clinvar: Annotated[
        Path | None,
        typer.Option(
            "--clinvar",
            help=(
                "ClinVar VCF release (plain or .gz) — what a `VCV…` accession input is "
                "looked up in. Never downloaded: the registry has no pinned checksum "
                "for ClinVar, so you supply the release. The record's clinical "
                "significance is carried into the design, which is what an accession "
                "is chosen for over the plain coordinates."
            ),
        ),
    ] = None,
    dbsnp: Annotated[
        Path | None,
        typer.Option(
            "--dbsnp",
            help=(
                "dbSNP `rsid chrom pos ref alt` TSV (plain or .gz), 1-based pos as in "
                "a VCF — what an `rs…` input is looked up in. Never downloaded; you "
                "supply the file."
            ),
        ),
    ] = None,
    gnomad: Annotated[
        Path | None,
        typer.Option(
            "--gnomad",
            help=(
                "Population allele-frequency sites TSV (plain or .gz), "
                "'#chrom pos ref alt af <pop>...' with 1-based pos as in a VCF — the "
                "input that makes the off-target search population-aware. Without it "
                "the scan is reference-only, which is the known safety gap this tool "
                "exists to close, and --populations has nothing to stratify."
            ),
        ),
    ] = None,
    weights: Annotated[
        str | None, typer.Option(help="Ranking weights 'eff,clean,safe,simple'.")
    ] = None,
    max_per_chemistry: Annotated[
        int | None, typer.Option(help="Cap candidates kept per chemistry.")
    ] = None,
    no_offtarget: Annotated[
        bool, typer.Option("--no-offtarget", help="Skip the off-target search.")
    ] = False,
    allow_ng: Annotated[
        bool,
        typer.Option(
            "--allow-ng",
            help="Fall back to SpCas9-NG (NG PAM) guides when no NGG guide is "
            "actionable. Off by default: an NG guide is a different reagent with "
            "different specificity, so it is offered rather than assumed. "
            "Consumed by SpCas9 nuclease design alone — prime and base editing "
            "take no PAM-flexible fallback, and the rationale says so when one is "
            "enabled and the nuclease vertical did not run.",
        ),
    ] = False,
    allow_spry: Annotated[
        bool,
        typer.Option(
            "--allow-spry",
            help="Fall back to SpRY (NRN/NYN PAM) guides when neither NGG nor NG "
            "yields one. Off by default, for the same reason as --allow-ng.",
        ),
    ] = False,
    trained_efficiency: Annotated[
        bool,
        typer.Option(
            "--trained-efficiency",
            help="Use the real trained Rule Set 3 model for SpCas9 efficiency "
            "(opt-in; needs the cas9-rs3 extra + booster). Default is the "
            "weight-free baseline.",
        ),
    ] = False,
    trained_outcome: Annotated[
        bool,
        typer.Option(
            "--trained-outcome",
            help="Use the real trained Lindel model for the SpCas9 indel spectrum "
            "(opt-in; needs a Lindel checkout via $ALLELEFORGE_LINDEL_REPO). "
            "Default is the weight-free microhomology baseline.",
        ),
    ] = False,
    trained_prime: Annotated[
        bool,
        typer.Option(
            "--trained-prime",
            help="Use the trained DeepPrime model for prime-editing efficiency "
            "instead of the transparent PRIDICT2-style baseline (consent-gated "
            "weight download).",
        ),
    ] = False,
    vep: Annotated[bool, typer.Option("--vep", help=_VEP_HELP)] = False,
    reuse_cache: Annotated[bool, typer.Option("--cache", help=_CACHE_HELP)] = False,
    genome_index: Annotated[bool, typer.Option("--genome-index", help=_GENOME_INDEX_HELP)] = False,
    trained_base_outcome: Annotated[
        bool,
        typer.Option(
            "--trained-base-outcome",
            help="Use the real trained BE-DICT model for the base-edit window "
            "outcome (opt-in; needs a BE-DICT checkout via $ALLELEFORGE_BEDICT_REPO). "
            "Default is the weight-free baseline.",
        ),
    ] = False,
    cell_context: Annotated[
        str | None,
        typer.Option(
            "--cell-context",
            help=(
                "The target cell line or type (e.g. HEK293T, K562, HepG2). Consumed by "
                "prime editing, where a context outside the scorer's training "
                "distribution flags the efficiency prediction out-of-distribution "
                "instead of reporting it as if it were in-domain. SpCas9 nuclease and "
                "base editing do not take it, and the rationale says so when a context "
                "is supplied and they run. Omitted, no OOD claim is made either way."
            ),
        ),
    ] = None,
    vector_scheme: Annotated[
        str | None,
        typer.Option(
            "--vector-scheme",
            help=(
                "The cloning vector the guide oligos are ordered for: "
                "lentiguide-bsmbi (default, BsmBI), px330-bbsi (BbsI), or "
                "pegrna-gg-bsai (BsaI). This picks the enzyme the inserts are "
                "screened against for a cloning-lethal internal Type IIS site, so "
                "naming the wrong vector reports an insert clean that your own "
                "enzyme cuts. A pegRNA candidate keeps the pegRNA acceptor when an "
                "sgRNA-only vector is named — an sgRNA vector cannot receive a 3' "
                "extension — and every candidate's block names the vector it used."
            ),
        ),
    ] = None,
    render_candidates: Annotated[
        int | None,
        typer.Option(
            "--render-candidates",
            help=(
                "How many candidates the html/pdf render draws (default 50; 0 for all). "
                "Every Pareto-front candidate is drawn whatever the cap, and the page "
                "states what it withheld. The json/tsv exports are never capped."
            ),
        ),
    ] = None,
    fmt: Annotated[OutputFormat, typer.Option("--format", help="Output format.")] = (
        OutputFormat.json
    ),
    out: Annotated[
        Path | None, typer.Option(help="Write output here (+ a .provenance.json sidecar).")
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Run-config TOML (CLI flags override).")
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option(
            "--json",
            help=(
                "Print the ranked menu as JSON to stdout — the full outcome spectrum, "
                "which the report truncates. With --out it accompanies the report; "
                "without one it replaces it, since a stream carries one document."
            ),
        ),
    ] = False,
) -> None:
    """Design a ranked, multi-chemistry editing menu for a variant."""
    try:
        from alleleforge.design.designer import design as run_design
        from alleleforge.report.builder import DEFAULT_RENDER_CANDIDATES, build_report
        from alleleforge.report.export import report_to_json, report_to_parquet, report_to_tsv
        from alleleforge.report.html import render_html
        from alleleforge.report.oligos import scheme_by_name
        from alleleforge.report.pdf import render_pdf
        from alleleforge.types.edit import Chemistry, EditIntent
        from alleleforge.variant.resolver import resolve as resolve_variant
    except ImportError as exc:
        _missing_dependency(exc)

    state: GlobalState = ctx.obj
    cfg = _load_config(config)
    intent_str = intent or cfg.get("intent", "correct")
    pops_str = populations if populations is not None else cfg.get("populations")
    chem_list = chemistry if chemistry else cfg.get("chemistry")
    weights_obj = _parse_weights(weights or cfg.get("weights"))
    # Honor the remaining whitelisted run-params from the config file (a CLI flag
    # still wins). Without this a config key that _load_config accepts silently
    # (no typo warning) would do nothing — the "config file is honored" contract.
    max_per_chemistry = (
        max_per_chemistry if max_per_chemistry is not None else cfg.get("max_per_chemistry")
    )
    cell_context = cell_context or cfg.get("cell_context")
    trained_efficiency = trained_efficiency or bool(cfg.get("trained_efficiency", False))
    trained_outcome = trained_outcome or bool(cfg.get("trained_outcome", False))
    trained_base_outcome = trained_base_outcome or bool(cfg.get("trained_base_outcome", False))
    trained_prime = trained_prime or bool(cfg.get("trained_prime", False))
    run_offtarget = _resolve_run_offtarget(no_offtarget, cfg)
    vector_scheme = vector_scheme or cfg.get("vector_scheme")

    # Resolved before the design runs: a typo'd vector name is a usage error, and
    # learning about it after a whole-genome off-target search would be cruel.
    scheme = None
    if vector_scheme:
        try:
            scheme = scheme_by_name(vector_scheme)
        except ValueError as exc:
            _echo_err(f"error: {reason(exc)}")
            raise typer.Exit(ExitCode.USAGE) from exc

    try:
        edit_intent = EditIntent(intent_str)
    except ValueError as exc:
        _echo_err(f"error: unknown intent {intent_str!r}; choose one of: {_known(EditIntent)}")
        raise typer.Exit(ExitCode.USAGE) from exc
    chemistries = None
    if chem_list:
        try:
            chemistries = [Chemistry(c) for c in chem_list]
        except ValueError as exc:
            # Not `{exc}`: pydantic's message is "'PRIME' is not a valid Chemistry",
            # which names the *class*. `Chemistry` is not a word in the vocabulary the
            # caller is being asked to use.
            unknown = sorted(c for c in chem_list if c not in {m.value for m in Chemistry})
            _echo_err(
                f"error: unknown chemistry: {', '.join(repr(c) for c in unknown)}; "
                f"choose one of: {_known(Chemistry)}"
            )
            raise typer.Exit(ExitCode.USAGE) from exc
    pops = _parse_populations(pops_str)
    _warn_if_ancestries_unbacked(pops, gnomad, haplotypes)
    gnomad_db = _load_gnomad(gnomad)
    clinvar_db = _load_clinvar(clinvar)
    dbsnp_db = _load_dbsnp(dbsnp)
    haplotype_panel = _load_haplotypes(haplotypes)
    region_list = _load_regions(regions, regions_bed)
    tracks, track_name = _load_encode_tracks(encode_tracks, chromatin_track)

    reference = _load_reference(reference_fasta, state.reference_build)
    _validate_regions(region_list, reference)
    patient_variants = _load_patient_variants(patient_vcf, reference)
    # Honor the user's config file (its Settings keys) with the CLI --seed as
    # an override, so a config.toml maf_threshold/interval_level/cache_dir is
    # applied instead of being silently ignored.
    settings = _load_settings(config, state.seed)
    cas9_scorer = None
    if trained_efficiency:
        from alleleforge.scoring.cas9_efficiency import TrainedRuleSet3Scorer

        # The user opted in explicitly, so consent for the gated weight download.
        cas9_scorer = TrainedRuleSet3Scorer(consent=True)
    cas9_outcome = None
    if trained_outcome:
        from alleleforge.scoring.cas9_outcome import LindelAdapter

        cas9_outcome = LindelAdapter(consent=True)
    base_outcome = None
    if trained_base_outcome:
        from alleleforge.scoring.base_outcome import BeDictAdapter

        base_outcome = BeDictAdapter(consent=True)
    prime_scorer = None
    if trained_prime:
        from alleleforge.scoring.prime_efficiency import DeepPrimeAdapter

        prime_scorer = DeepPrimeAdapter(consent=True)
    try:
        resolved = resolve_variant(
            variant,
            build=state.reference_build,
            reference=reference,
            effect=_effect_predictor(vep),
            clinvar=clinvar_db,
            dbsnp=dbsnp_db,
        )
        store, index = _reuse(reference, cache=reuse_cache, index=genome_index)
        menu = run_design(
            resolved,
            reference=reference,
            offtarget_cache=store,
            genome_index=index,
            intent=edit_intent,
            chemistries=chemistries,
            weights=weights_obj,
            populations=pops,
            gnomad=gnomad_db,
            haplotypes=haplotype_panel,
            offtarget_regions=region_list,
            encode_tracks=tracks,
            chromatin_track=track_name,
            patient_vcf=patient_variants,
            run_offtarget=run_offtarget,
            max_candidates_per_chemistry=max_per_chemistry,
            cell_context=cell_context,
            settings=settings,
            cas9_efficiency_scorer=cas9_scorer,
            cas9_outcome_predictor=cas9_outcome,
            base_outcome_predictor=base_outcome,
            prime_efficiency_scorer=prime_scorer,
            allow_ng=allow_ng,
            allow_spry=allow_spry,
        )
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc

    report = build_report(
        menu, variant=str(resolved.variant), intent=edit_intent.value, scheme=scheme
    )
    if state.verbose:
        _echo_err(
            f"{len(menu.candidates)} candidate(s); best: "
            f"{menu.best.chemistry.value if menu.best else 'none'}"
        )

    # `--json` prints the ranked menu, which is a *different document* from the report:
    # the report truncates each candidate's outcome to the top alleles and says so, and
    # tells the reader the full spectrum is on the menu, "`aforge design --json` writes
    # it". Without `--out` the report is written to stdout as well, and two documents on
    # one stream is what `test_a_json_stream_carries_only_json` exists to prevent — so
    # the menu used to be dropped, silently, on exactly the command that note sends a
    # reader to. Refusing is the honest form: the flag's help promises the menu, and a
    # promise that cannot be kept here has a remedy the user can take.
    # `--render-candidates 0` means "draw them all"; typer has no natural way to
    # spell `None` on the command line, and 0 candidates is not a render anyone wants.
    cap = DEFAULT_RENDER_CANDIDATES if render_candidates is None else (render_candidates or None)
    # Parquet is written by its own writer rather than rendered to bytes: the notes
    # the TSV carries in `#` comment lines live in Parquet's file-level key/value
    # metadata, which only exists on the file. It therefore requires --out, like the
    # other two formats no terminal can usefully receive.
    if fmt is OutputFormat.parquet:
        if out is None:
            _echo_err("error: --format parquet requires --out")
            raise typer.Exit(ExitCode.USAGE)
        try:
            report_to_parquet(report, out)
        except MissingDependencyError as exc:
            _echo_err(f"error: {reason(exc)}")
            raise typer.Exit(ExitCode.UNAVAILABLE) from exc
        sidecar = _write_provenance_sidecar(out, menu)
        _echo_err(f"wrote {out}" + (f" and {sidecar}" if sidecar else ""))
        if as_json:
            typer.echo(menu.model_dump_json(indent=2))
        return

    if fmt is OutputFormat.menu:
        rendered: bytes = menu.model_dump_json(indent=2).encode()
    elif fmt is OutputFormat.json:
        rendered = report_to_json(report).encode()
    elif fmt is OutputFormat.tsv:
        rendered = report_to_tsv(report).encode()
    elif fmt is OutputFormat.html:
        rendered = render_html(report, max_candidates=cap).encode()
    else:
        rendered = render_pdf(report, max_candidates=cap)

    if out is not None:
        out.write_bytes(rendered)
        sidecar = _write_provenance_sidecar(out, menu)
        _echo_err(f"wrote {out}" + (f" and {sidecar}" if sidecar else ""))
    elif as_json:
        # The caller asked for the ranked menu and gave nowhere to put the report, and a
        # stream cannot carry both (`test_a_json_stream_carries_only_json`). The menu is
        # the document they named; the report on stdout is the default they did not. It
        # used to resolve the other way and *silently*, so `aforge design VARIANT --json`
        # — the exact command every truncated outcome table points a reader at for the
        # withheld alleles — printed the truncation instead of the full spectrum.
        pass
    elif fmt in (OutputFormat.json, OutputFormat.tsv, OutputFormat.menu):
        typer.echo(rendered.decode())
    else:
        _echo_err(f"error: --format {fmt.value} requires --out")
        raise typer.Exit(ExitCode.USAGE)

    if as_json:
        typer.echo(menu.model_dump_json(indent=2))

    # A chemistry's vertical that hits an *unexpected* exception is recorded as a defect
    # note and contributes no candidates, rather than crashing the whole design — that
    # graceful degradation is deliberate, and the rationale says so where a reader looks.
    # Reporting *success* for it is not part of it. `aforge batch` already draws this
    # line ("a script or a CI job driving this had no way to tell without re-parsing the
    # summary"), and `design` did not: a corrupted `--cache` entry, now refused rather
    # than served, took the whole prime vertical out of a menu and exited 0.
    if DEFECT_NOTE in (menu.rationale or ""):
        _echo_err(
            "error: a chemistry failed with an unexpected error and contributed no "
            "candidates; the menu was written and its rationale names the failure"
        )
        raise typer.Exit(ExitCode.UNAVAILABLE)


#: VCF path suffixes routed through the cyvcf2 fast path; anything else is a
#: plain one-variant-per-line list.
_VCF_SUFFIXES = (".vcf", ".vcf.gz", ".vcf.bgz", ".bcf")


def _is_vcf_path(path: Path) -> bool:
    """Return whether ``path`` looks like a VCF (vs a plain variant list)."""
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in _VCF_SUFFIXES)


def _read_variant_list(path: Path) -> list[str]:
    """Read a one-variant-per-line list, skipping blanks and ``#`` comments."""
    out: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _batch_item_id(item: Any) -> str:
    """Stable, filesystem-friendly id for a cohort item (resume + output names)."""
    from alleleforge.variant.resolver import VcfRecord

    if isinstance(item, VcfRecord):
        return f"{item.chrom}:{item.pos}:{item.ref}>{item.alt}"
    return str(item)


@app.command()
def batch(
    ctx: typer.Context,
    inputs: Annotated[
        Path,
        typer.Argument(
            help="A VCF (.vcf/.vcf.gz/.bcf) or a one-variant-per-line list "
            "(ClinVar/rsID/HGVS/coords; '#' comments skipped)."
        ),
    ],
    reference_fasta: Annotated[
        Path | None, typer.Option(help="Reference FASTA (required).")
    ] = None,
    intent: Annotated[
        str | None, typer.Option(help="correct | knock_out | install | revert (default: correct).")
    ] = None,
    populations: Annotated[
        str | None, typer.Option(help="Comma-separated ancestry labels to stratify by.")
    ] = None,
    encode_tracks: Annotated[
        Path | None,
        typer.Option(
            "--encode-tracks",
            help=(
                "ENCODE accessibility bedGraph ('track chrom start end value') for the "
                "ePRIDICT-style open-chromatin efficiency adjustment. Needs "
                "--chromatin-track to name which track to read."
            ),
        ),
    ] = None,
    chromatin_track: Annotated[
        str | None,
        typer.Option("--chromatin-track", help="Which track in --encode-tracks to read."),
    ] = None,
    regions: Annotated[
        list[str] | None,
        typer.Option(
            "--region",
            help=(
                "Restrict the off-target search to this locus, 'chrom:start-end' "
                "— 0-based half-open, as in a BED file, NOT the 1-based form a "
                "genome browser shows. The variant inputs are the exception and take "
                "1-based VCF positions, as a VCF record holds them: the variant string "
                "itself, `--gnomad` and `--patient-vcf`. A BED file works too: "
                "--regions-bed. "
                "Whole-genome search over a real reference is slow in pure Python, so "
                "scoping to a gene panel is usually what makes a run practical."
            ),
        ),
    ] = None,
    regions_bed: Annotated[
        Path | None,
        typer.Option("--regions-bed", help="BED file of regions to restrict the search to."),
    ] = None,
    haplotypes: Annotated[
        Path | None,
        typer.Option(
            "--haplotypes",
            help=(
                "Phased common-haplotype panel TSV (plain or .gz), "
                "'#hap_id chrom start end population frequency variants' — enables the "
                "haplotype-aware pass, which catches a site that only exists on a "
                "co-inherited combination of alleles. Its start/end and the pos inside "
                "each `chrom:pos:ref>alt` are 0-based, like --region and unlike "
                "--gnomad."
            ),
        ),
    ] = None,
    patient_vcf: Annotated[
        Path | None,
        typer.Option(
            "--patient-vcf",
            help=(
                "Personal variants (VCF or one-variant-per-line list) to personalize "
                "the off-target scan — a site present in this genome but not the "
                "reference is nominated as `patient` origin."
            ),
        ),
    ] = None,
    clinvar: Annotated[
        Path | None,
        typer.Option(
            "--clinvar",
            help=(
                "ClinVar VCF release (plain or .gz) — what a `VCV…` accession input is "
                "looked up in. Never downloaded: the registry has no pinned checksum "
                "for ClinVar, so you supply the release. The record's clinical "
                "significance is carried into the design, which is what an accession "
                "is chosen for over the plain coordinates."
            ),
        ),
    ] = None,
    dbsnp: Annotated[
        Path | None,
        typer.Option(
            "--dbsnp",
            help=(
                "dbSNP `rsid chrom pos ref alt` TSV (plain or .gz), 1-based pos as in "
                "a VCF — what an `rs…` input is looked up in. Never downloaded; you "
                "supply the file."
            ),
        ),
    ] = None,
    gnomad: Annotated[
        Path | None,
        typer.Option(
            "--gnomad",
            help=(
                "Population allele-frequency sites TSV (plain or .gz), "
                "'#chrom pos ref alt af <pop>...' with 1-based pos as in a VCF — the "
                "input that makes the off-target search population-aware. Without it "
                "the scan is reference-only, which is the known safety gap this tool "
                "exists to close, and --populations has nothing to stratify."
            ),
        ),
    ] = None,
    weights: Annotated[
        str | None, typer.Option(help="Ranking weights 'eff,clean,safe,simple'.")
    ] = None,
    max_per_chemistry: Annotated[
        int | None, typer.Option(help="Cap candidates kept per chemistry.")
    ] = None,
    no_offtarget: Annotated[
        bool, typer.Option("--no-offtarget", help="Skip the off-target search.")
    ] = False,
    manifest: Annotated[
        Path | None,
        typer.Option(help="JSONL run manifest to append to; enables resume (skip recorded items)."),
    ] = None,
    no_resume: Annotated[
        bool, typer.Option("--no-resume", help="Re-run every item even if the manifest records it.")
    ] = False,
    chemistry: Annotated[
        list[str] | None,
        typer.Option("--chemistry", help="Restrict to these chemistries (repeatable)."),
    ] = None,
    cell_context: Annotated[
        str | None,
        typer.Option("--cell-context", help="Cell type / context label for the design."),
    ] = None,
    allow_ng: Annotated[
        bool,
        typer.Option(
            "--allow-ng",
            help="Fall back to SpCas9-NG (NG PAM) guides when no NGG guide is "
            "actionable. Off by default: an NG guide is a different reagent with "
            "different specificity, so it is offered rather than assumed. "
            "Consumed by SpCas9 nuclease design alone — prime and base editing "
            "take no PAM-flexible fallback, and the rationale says so when one is "
            "enabled and the nuclease vertical did not run.",
        ),
    ] = False,
    allow_spry: Annotated[
        bool,
        typer.Option(
            "--allow-spry",
            help="Fall back to SpRY (NRN/NYN PAM) guides when neither NGG nor NG "
            "yields one. Off by default, for the same reason as --allow-ng.",
        ),
    ] = False,
    trained_efficiency: Annotated[
        bool,
        typer.Option(
            "--trained-efficiency",
            help="Use the real trained Rule Set 3 model for SpCas9 efficiency "
            "(consent-gated weight download).",
        ),
    ] = False,
    trained_outcome: Annotated[
        bool,
        typer.Option(
            "--trained-outcome",
            help="Use the trained Lindel model for SpCas9 repair outcomes "
            "(consent-gated weight download).",
        ),
    ] = False,
    trained_base_outcome: Annotated[
        bool,
        typer.Option(
            "--trained-base-outcome",
            help="Use the trained BE-DICT model for base-editing outcomes "
            "(consent-gated weight download).",
        ),
    ] = False,
    trained_prime: Annotated[
        bool,
        typer.Option(
            "--trained-prime",
            help="Use the trained DeepPrime model for prime-editing efficiency "
            "(consent-gated weight download).",
        ),
    ] = False,
    vep: Annotated[bool, typer.Option("--vep", help=_VEP_HELP)] = False,
    reuse_cache: Annotated[bool, typer.Option("--cache", help=_CACHE_HELP)] = False,
    genome_index: Annotated[bool, typer.Option("--genome-index", help=_GENOME_INDEX_HELP)] = False,
    output_dir: Annotated[
        Path | None, typer.Option(help="Write each item's full menu JSON to <dir>/<item>.json.")
    ] = None,
    max_workers: Annotated[
        int, typer.Option(help="Thread pool size (a fresh reference is opened per worker).")
    ] = 1,
    summary_tsv: Annotated[
        Path | None, typer.Option(help="Write a per-item TSV summary here.")
    ] = None,
    summary_parquet: Annotated[
        Path | None,
        typer.Option(
            help=(
                "Write the same per-item summary here as Parquet — the same columns in "
                "the same order, typed, with the TSV's `#` notes as file-level metadata. "
                "A cohort is the result that goes into a dataframe."
            )
        ),
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Run-config TOML (CLI flags override).")
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit the full run report as JSON to stdout.")
    ] = False,
) -> None:
    """Design a whole cohort from a VCF or variant list (streaming, resumable).

    The cohort multiplier over ``design``: it streams the input lazily (bounded
    memory — each menu is summarized then released), is resumable through a JSONL
    run manifest, and isolates per-item failures (an unresolvable variant is
    recorded, not fatal). A ``.vcf``/``.vcf.gz``/``.bcf`` input takes the cyvcf2
    fast path; anything else is read as a one-variant-per-line list.
    """
    try:
        from alleleforge.design.cohort import RESUME_UNVERIFIED, design_many
    except ImportError as exc:
        _missing_dependency(exc)
    from alleleforge.types.edit import Chemistry, EditIntent

    state: GlobalState = ctx.obj
    cfg = _load_config(config)
    intent_str = intent or cfg.get("intent", "correct")
    pops_str = populations if populations is not None else cfg.get("populations")
    weights_obj = _parse_weights(weights or cfg.get("weights"))
    # Honor the whitelisted run-params this command exposes from the config file
    # (a CLI flag still wins), so an accepted config key is not silently ignored.
    max_per_chemistry = (
        max_per_chemistry if max_per_chemistry is not None else cfg.get("max_per_chemistry")
    )
    # `chemistry`/`cell_context` are whitelisted config keys (no typo warning), so they
    # must actually restrict/route the run — otherwise batch silently ignores them while
    # `design`, the web `/api/batch`, and `design_many` all honor them (a parity gap).
    # A CLI flag wins over the config file, matching every other option here.
    chem_list = chemistry if chemistry else cfg.get("chemistry")
    cell_context = cell_context or cfg.get("cell_context")
    run_offtarget = _resolve_run_offtarget(no_offtarget, cfg)

    try:
        edit_intent = EditIntent(intent_str)
    except ValueError as exc:
        _echo_err(f"error: unknown intent {intent_str!r}; choose one of: {_known(EditIntent)}")
        raise typer.Exit(ExitCode.USAGE) from exc
    chemistries = None
    if chem_list:
        try:
            chemistries = [Chemistry(c) for c in chem_list]
        except ValueError as exc:
            # Not `{exc}`: pydantic's message is "'PRIME' is not a valid Chemistry",
            # which names the *class*. `Chemistry` is not a word in the vocabulary the
            # caller is being asked to use.
            unknown = sorted(c for c in chem_list if c not in {m.value for m in Chemistry})
            _echo_err(
                f"error: unknown chemistry: {', '.join(repr(c) for c in unknown)}; "
                f"choose one of: {_known(Chemistry)}"
            )
            raise typer.Exit(ExitCode.USAGE) from exc
    if not inputs.is_file():
        _echo_err(f"error: input file not found: {inputs}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    pops = _parse_populations(pops_str)
    _warn_if_ancestries_unbacked(pops, gnomad, haplotypes)
    gnomad_db = _load_gnomad(gnomad)
    clinvar_db = _load_clinvar(clinvar)
    dbsnp_db = _load_dbsnp(dbsnp)
    haplotype_panel = _load_haplotypes(haplotypes)
    region_list = _load_regions(regions, regions_bed)
    tracks, track_name = _load_encode_tracks(encode_tracks, chromatin_track)

    reference = _load_reference(reference_fasta, state.reference_build)
    _validate_regions(region_list, reference)
    patient_variants = _load_patient_variants(patient_vcf, reference)
    assert reference_fasta is not None  # _load_reference exits otherwise
    # Honor the user's config file (its Settings keys) with the CLI --seed as
    # an override, so a config.toml maf_threshold/interval_level/cache_dir is
    # applied instead of being silently ignored.
    settings = _load_settings(config, state.seed)

    ingest: Any = None
    if _is_vcf_path(inputs):
        from alleleforge.variant.vcf import VcfIngestCounts, iter_vcf

        # A real VCF routinely carries soft-filtered calls and structural variants, and
        # none of them names a designable substitution. Dropping them is right; doing it
        # without a word means the cohort is quietly smaller than the file and the run
        # still reports success. Filled as the stream is consumed, so it is complete by
        # the time the summary below is printed.
        ingest = VcfIngestCounts()
        variants: Any = iter_vcf(inputs, counts=ingest)
    else:
        variants = _read_variant_list(inputs)

    # A pyfaidx handle is not thread-safe to share, so parallel runs open a fresh
    # reference per worker (the .fai built by _load_reference above is reused).
    ref_kwargs: dict[str, Any] = {"reference": reference}
    if max_workers > 1:
        from alleleforge.genome.reference import ReferenceGenome

        fasta = reference_fasta
        ref_kwargs = {
            "reference_factory": lambda: ReferenceGenome(fasta, build=state.reference_build)
        }

    try:
        # The same consent-gated opt-ins the single-variant command offers. A cohort is
        # where a trained model matters most — it is the run someone leaves going — and
        # the batch path could not select one by any means, config file included.
        cas9_scorer = None
        if trained_efficiency:
            from alleleforge.scoring.cas9_efficiency import TrainedRuleSet3Scorer

            cas9_scorer = TrainedRuleSet3Scorer(consent=True)
        cas9_outcome = None
        if trained_outcome:
            from alleleforge.scoring.cas9_outcome import LindelAdapter

            cas9_outcome = LindelAdapter(consent=True)
        base_outcome = None
        if trained_base_outcome:
            from alleleforge.scoring.base_outcome import BeDictAdapter

            base_outcome = BeDictAdapter(consent=True)
        prime_scorer = None
        if trained_prime:
            from alleleforge.scoring.prime_efficiency import DeepPrimeAdapter

            prime_scorer = DeepPrimeAdapter(consent=True)
        store, index = _reuse(reference, cache=reuse_cache, index=genome_index)
        report = design_many(
            variants,
            offtarget_cache=store,
            genome_index=index,
            intent=edit_intent,
            manifest_path=manifest,
            resume=not no_resume,
            output_dir=output_dir,
            max_workers=max_workers,
            item_id=_batch_item_id,
            build=state.reference_build,
            weights=weights_obj,
            populations=pops,
            gnomad=gnomad_db,
            haplotypes=haplotype_panel,
            offtarget_regions=region_list,
            encode_tracks=tracks,
            chromatin_track=track_name,
            patient_vcf=patient_variants,
            run_offtarget=run_offtarget,
            max_candidates_per_chemistry=max_per_chemistry,
            chemistries=chemistries,
            cell_context=cell_context,
            allow_ng=allow_ng,
            allow_spry=allow_spry,
            cas9_efficiency_scorer=cas9_scorer,
            cas9_outcome_predictor=cas9_outcome,
            base_outcome_predictor=base_outcome,
            prime_efficiency_scorer=prime_scorer,
            effect=_effect_predictor(vep),
            clinvar=clinvar_db,
            dbsnp=dbsnp_db,
            settings=settings,
            **ref_kwargs,
        )
    # Named rather than `RuntimeError`: a defect escaping `design_many` is a bug in the
    # cohort machinery, not a missing package, and must not be reported as one.
    except MissingDependencyError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.UNAVAILABLE) from exc
    # `design_many` refuses a call it cannot honour: a parallel run with no
    # reference factory, and a resume whose manifest was opened under different
    # result-determining inputs. Both are the caller's to fix and both name a remedy;
    # arriving as a traceback made a decision the code had already taken look like a
    # crash.
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc

    rows = _batch_rows(report)
    counts = {
        "total": report.total,
        "succeeded": report.succeeded,
        "failed": report.failed,
        "skipped": report.skipped,
    }
    if summary_tsv is not None:
        summary_tsv.write_text(_batch_tsv(rows, report.provenance, counts=counts), encoding="utf-8")
    if summary_parquet is not None:
        try:
            _batch_parquet(rows, summary_parquet, report.provenance, counts=counts)
        except MissingDependencyError as exc:
            _echo_err(f"error: {reason(exc)}")
            raise typer.Exit(ExitCode.UNAVAILABLE) from exc
    # Not behind --verbose: a skipped item reads as work already done, and this is the
    # run saying it could not confirm what that work was designed under.
    if report.provenance.get(RESUME_UNVERIFIED):
        _echo_err(f"warning: {report.provenance[RESUME_UNVERIFIED]}")
    if state.verbose:
        _echo_err(f"designed {report.succeeded}/{report.total} (skipped {report.skipped})")

    if as_json:
        from alleleforge.report.builder import COORDINATE_NOTE, RESEARCH_USE_DISCLAIMER

        payload = {
            # The cohort summary TSV carries this, the web cohort response carries it,
            # every other JSON this CLI emits carries it — and the cohort JSON, which is
            # the file a lab actually passes around after a run, did not. The exemption
            # recorded for the per-item menu files reasons that "the run that wrote it
            # puts the context in the summary TSV beside it"; a `--json` run writes no
            # TSV, so that justification does not reach this document.
            "disclaimer": RESEARCH_USE_DISCLAIMER,
            "coordinate_note": COORDINATE_NOTE,
            "provenance": report.provenance,
            "total": report.total,
            "succeeded": report.succeeded,
            "failed": report.failed,
            "skipped": report.skipped,
            "ingest": None
            if ingest is None
            else {
                "rows": ingest.rows,
                "records": ingest.records,
                "skipped": ingest.skipped,
            },
            "items": rows,
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        return

    # `total` counts what this run *processed*; a resumed run skips the rest. Stating
    # the requested count first stops "0 item(s)" from being the headline for a resume
    # that had nothing left to do — the two numbers now visibly add up.
    requested = report.total + report.skipped
    header = (
        f"cohort: {requested} requested — {report.total} designed "
        f"({report.succeeded} ok, {report.failed} failed), "
        f"{report.skipped} already done (resume)"
    )
    lines = [header]
    if ingest is not None and ingest.summary():
        lines.append(f"  ingest: {ingest.summary()}")
    for r in rows:
        if r["status"] == "ok":
            eff = r["best_efficiency"]
            low, high = r["best_efficiency_low"], r["best_efficiency_high"]
            if isinstance(eff, (int, float)):
                eff_str = f"{eff:.2f}"
                # The interval is the point of the number. Scanning a cohort is exactly
                # when a bare estimate gets taken at face value, so it never appears bare.
                if isinstance(low, (int, float)) and isinstance(high, (int, float)):
                    eff_str += f" [{low:.2f},{high:.2f}]"
                if r["best_efficiency_in_distribution"] is False:
                    eff_str += " OOD"
            else:
                eff_str = "-"
            flagged = r["best_caveats"]
            caveat_str = f"  !{','.join(flagged)}" if flagged else ""
            # An item that designed nothing is `ok` — nothing errored — and every
            # other column is blank, which reads as a silent shrug in a list of five
            # hundred. Say why, as the single-variant report does.
            no_candidate = r.get("no_candidate_reason")
            why = f"  — {no_candidate}" if not r["n_candidates"] and no_candidate else ""
            lines.append(
                f"  {r['item_id']}  ok  best={r['best_chemistry'] or '-'}  "
                f"eff={eff_str}  n={r['n_candidates'] or 0}{caveat_str}{why}"
            )
        else:
            lines.append(f"  {r['item_id']}  error  {r['error']}")
    typer.echo("\n".join(lines))
    if summary_tsv is not None:
        _echo_err(f"wrote {summary_tsv}")
    if summary_parquet is not None:
        _echo_err(f"wrote {summary_parquet}")
    # Per-item isolation is the feature: every item runs, the manifest is complete, and
    # one bad variant does not abandon the other four hundred. Reporting *success* for
    # a run that failed items is not part of that — a script or a CI job driving this
    # had no way to tell without re-parsing the summary, while `verify`, `bench compare`
    # and `scripts/reproduce.py` all signal failure through the exit code.
    if report.failed:
        _echo_err(
            f"error: {report.failed} of {report.total} item(s) failed; "
            "the run completed and the manifest is intact"
        )
        raise typer.Exit(ExitCode.UNAVAILABLE)


@app.command()
def offtarget(
    ctx: typer.Context,
    spacer: Annotated[str, typer.Argument(help="The on-target spacer (5'->3').")],
    reference_fasta: Annotated[
        Path | None, typer.Option(help="Reference FASTA (required).")
    ] = None,
    pam: Annotated[str, typer.Option(help="PAM pattern (IUPAC).")] = "NGG",
    mismatches: Annotated[int, typer.Option(help="Max mismatches.", min=0)] = 4,
    dna_bulges: Annotated[int, typer.Option(help="Max DNA bulges.", min=0)] = 1,
    rna_bulges: Annotated[int, typer.Option(help="Max RNA bulges.", min=0)] = 1,
    cfd_threshold: Annotated[
        float, typer.Option(help="Report a site at or above this CFD score.", min=0.0, max=1.0)
    ] = 0.20,
    mit_threshold: Annotated[
        float, typer.Option(help="...or at or above this MIT score.", min=0.0, max=1.0)
    ] = 0.10,
    maf: Annotated[
        float,
        typer.Option(
            help="Min population allele frequency to consider carrying.", min=0.0, max=1.0
        ),
    ] = 0.001,
    populations: Annotated[
        str | None, typer.Option(help="Comma-separated ancestry labels to stratify by.")
    ] = None,
    regions: Annotated[
        list[str] | None,
        typer.Option(
            "--region",
            help=(
                "Restrict the off-target search to this locus, 'chrom:start-end' "
                "— 0-based half-open, as in a BED file, NOT the 1-based form a "
                "genome browser shows. The variant inputs are the exception and take "
                "1-based VCF positions, as a VCF record holds them: the variant string "
                "itself, `--gnomad` and `--patient-vcf`. A BED file works too: "
                "--regions-bed. "
                "Whole-genome search over a real reference is slow in pure Python, so "
                "scoping to a gene panel is usually what makes a run practical."
            ),
        ),
    ] = None,
    regions_bed: Annotated[
        Path | None,
        typer.Option("--regions-bed", help="BED file of regions to restrict the search to."),
    ] = None,
    haplotypes: Annotated[
        Path | None,
        typer.Option(
            "--haplotypes",
            help=(
                "Phased common-haplotype panel TSV (plain or .gz), "
                "'#hap_id chrom start end population frequency variants' — enables the "
                "haplotype-aware pass, which catches a site that only exists on a "
                "co-inherited combination of alleles. Its start/end and the pos inside "
                "each `chrom:pos:ref>alt` are 0-based, like --region and unlike "
                "--gnomad."
            ),
        ),
    ] = None,
    patient_vcf: Annotated[
        Path | None,
        typer.Option(
            "--patient-vcf",
            help=(
                "Personal variants (VCF or one-variant-per-line list) to personalize "
                "the off-target scan — a site present in this genome but not the "
                "reference is nominated as `patient` origin."
            ),
        ),
    ] = None,
    gnomad: Annotated[
        Path | None,
        typer.Option(
            "--gnomad",
            help=(
                "Population allele-frequency sites TSV (plain or .gz), "
                "'#chrom pos ref alt af <pop>...' with 1-based pos as in a VCF — the "
                "input that makes the off-target search population-aware. Without it "
                "the scan is reference-only, which is the known safety gap this tool "
                "exists to close, and --populations has nothing to stratify."
            ),
        ),
    ] = None,
    scorer: Annotated[
        str | None,
        typer.Option(
            "--scorer",
            help="Specificity scorer: 'cfd' (default, published Doench 2016 matrix), "
            "'mit' (Hsu 2013 position weights), or 'cfd-cas12a' (the Cas12a analog, "
            "5' seed and TTTV PAM — pair it with --pam TTTV).",
        ),
    ] = None,
    on_target: Annotated[
        str | None,
        typer.Option(
            help=(
                "The spacer's own locus as 'chrom:start-end(strand)', so it is not "
                "counted against itself. Without it the guide's own perfect match is "
                "reported like any other site and the specificity is not comparable to "
                "a design report's."
            )
        ),
    ] = None,
    reuse_cache: Annotated[
        bool,
        typer.Option(
            "--cache",
            help="Reuse an identical reference scan from a previous run, and record "
            "this one for the next. The engine consults the store only when the "
            "result is a pure function of the reference — the default scorer and no "
            "--gnomad/--haplotypes/--patient-vcf — so an augmented scan is always "
            "computed fresh.",
        ),
    ] = False,
    genome_index: Annotated[
        bool,
        typer.Option(
            "--genome-index",
            help="Anchor PAMs through a persistent, memory-mapped FM-index of the "
            "reference instead of rebuilding one in memory. Identical hits (pinned by "
            "a parity test); the first run pays to build it and every later run "
            "memory-maps it. Worth it for a whole genome, not for a small contig.",
        ),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Run population/haplotype-aware off-target search for a spacer."""
    try:
        from alleleforge.offtarget.cache import OffTargetCache
        from alleleforge.offtarget.engine import search
    except ImportError as exc:
        _missing_dependency(exc)
    from alleleforge.types.guide import PAM

    state: GlobalState = ctx.obj
    reference = _load_reference(reference_fasta, state.reference_build)
    pops = _parse_populations(populations)
    _warn_if_ancestries_unbacked(pops, gnomad, haplotypes)
    gnomad_db = _load_gnomad(gnomad)
    haplotype_panel = _load_haplotypes(haplotypes)
    region_list = _load_regions(regions, regions_bed)
    _validate_regions(region_list, reference)
    patient_variants = _load_patient_variants(patient_vcf, reference)
    try:
        locus = GenomicInterval.parse(on_target) if on_target else None
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc
    scorer_impl = None
    if scorer is not None:
        from alleleforge.offtarget.scoring import scorer_for

        try:
            scorer_impl = scorer_for(scorer)
        except ValueError as exc:
            _echo_err(f"error: {reason(exc)}")
            raise typer.Exit(ExitCode.USAGE) from exc
    index = None
    if genome_index:
        from alleleforge.genome.index import GenomeIndex

        index = GenomeIndex.build_genome(reference)
    try:
        report = search(
            spacer,
            PAM(pattern=pam),
            reference=reference,
            scorer=scorer_impl,
            cache=OffTargetCache() if reuse_cache else None,
            genome_index=index,
            on_target=locus,
            mismatches=mismatches,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
            cfd_threshold=cfd_threshold,
            mit_threshold=mit_threshold,
            maf=maf,
            populations=pops,
            gnomad=gnomad_db,
            haplotypes=haplotype_panel,
            regions=region_list,
            patient_vcf=patient_variants,
        )
    except ValueError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc

    from alleleforge.design.designer import _reference_snapshot
    from alleleforge.report.builder import (
        COORDINATE_NOTE,
        COORDINATE_SYSTEM,
        RESEARCH_USE_OFFTARGET,
    )

    sites = [
        {
            "locus": str(s.locus),
            "pam": s.pam_sequence,
            "mismatches": s.mismatches,
            "dna_bulges": s.dna_bulges,
            "rna_bulges": s.rna_bulges,
            "score": round(s.score, 4),
            "method": s.score_method.value,
            "score_matrix": s.score_matrix,
            "mit_score": None if s.mit_score is None else round(s.mit_score, 4),
            "origin": s.origin.value,
            "causal_allele": s.causal_allele,
            "populations": list(s.populations),
            "frequency": None if s.frequency is None else round(s.frequency, 6),
            "ancestries": {a: round(v, 6) for a, v in s.ancestries.items()},
        }
        for s in report.sites
    ]
    payload = {
        "spacer": report.spacer,
        "pam": report.pam,
        "scorer": report.scorer,
        "score_matrix": report.score_matrix,
        "effective_matrix": report.effective_matrix(),
        "n_sites": report.n_sites,
        "search": {
            "mismatch_threshold": report.mismatch_threshold,
            "dna_bulge_budget": report.dna_bulge_budget,
            "rna_bulge_budget": report.rna_bulge_budget,
            "cfd_threshold": report.cfd_threshold,
            "mit_threshold": report.mit_threshold,
            # The extent, for the consumer that cannot read the human line. Every
            # number below is conditional on it -- a panel scan and a genome-wide scan
            # report different specificities -- and `searched_bases: 0` is the one
            # value that makes "0 sites, specificity 1.000" mean nothing at all.
            "searched_bases": report.searched_bases,
            "resolved_bases": report.resolved_bases,
            "maf_threshold": report.maf_threshold,
            # ...and the sentence those numbers support, which this surface alone was
            # withholding. The human line says "NO SEQUENCE WAS SEARCHED — this is not a
            # clean result, it is an empty one"; the design report's JSON carries the
            # same sentence in `offtarget_search`, and so does the web response in
            # `search_description`. Here a consumer got the inputs to that inference and
            # not the inference, on the surface most likely to be scripted against.
            "description": report.search_description(),
            # The structured facts behind that sentence. `search_description()` folds
            # several of them into prose, which a human can read and a pipeline cannot
            # branch on — and this payload is the surface most likely to be scripted
            # against. The HTTP response has carried all of them all along, so a script
            # written against the API could filter on an unbacked ancestry and the same
            # script written against the CLI could not.
            "scanned_pam": report.scanned_pam,
            "sources_considered": dict(report.sources_considered),
            # The ancestries a caller asked to stratify by that no loaded source can
            # speak for. An empty ancestry breakdown reads as "no ancestry-specific risk
            # found"; this is what distinguishes that from "nothing was measured".
            "unbacked_populations": list(report.unbacked_populations),
            "available_populations": list(report.available_populations),
            "ambiguous_spacer_positions": list(report.ambiguous_spacer_positions),
            # What was found and not reported. Without these, "0 sites" from a scan with
            # a long sub-threshold tail is indistinguishable from a genuinely clean one.
            "subthreshold_placements": report.subthreshold_placements,
            "subthreshold_score_sum": round(report.subthreshold_score_sum, 4),
            "on_target_excluded_placements": report.on_target_excluded_placements,
        },
        # The document-level context. Every number above is conditional on which
        # genome was searched, and `reference_build` alone is a label the caller
        # chose: two FASTAs both called hg38 give different specificities. The
        # `locus` strings below are 0-based half-open, which a genome browser reads
        # as 1-based inclusive.
        "reference_build": state.reference_build,
        "reference": _reference_snapshot(reference),
        "coordinate_system": COORDINATE_SYSTEM,
        # This command nominates off-target sites and ranks no candidates, so it carries
        # the off-target wording rather than the menu's.
        "disclaimer": RESEARCH_USE_OFFTARGET,
        "on_target_excluded": locus is not None,
        "worst_score": round(report.worst_score(), 4),
        "specificity": round(report.specificity_score(), 4),
        # Present only for a population-aware search: with reference sites alone the
        # burden is the unweighted score sum. When it is present it is the one number
        # here that tells a rare-variant off-target from a universal one.
        "expected_burden": (
            round(report.expected_burden(), 4) if report.is_frequency_weighted() else None
        ),
        "ancestry_stratification": {
            a: round(v, 4) for a, v in report.ancestry_stratification().items()
        },
        "ancestry_expected_burden": {
            a: round(v, 6) for a, v in report.ancestry_expected_burden().items()
        },
        "sites": sites,
    }
    # The nominal matrix records how the scorer was configured; the effective matrix is
    # what the reported sites were actually scored by (a published matrix falls back to the
    # approximation per off-register hit). Show the effective one when it differs so the
    # human line never claims published CFD for an all-approximation table.
    effective = report.effective_matrix()
    if not report.scorer:
        scorer_note = ""
    elif effective is not None and effective != report.score_matrix:
        scorer_note = (
            f" [scorer {report.scorer}, matrix {report.score_matrix}, effective {effective}]"
        )
    else:
        scorer_note = f" [scorer {report.scorer}, matrix {report.score_matrix}]"
    # Without a locus the guide's own perfect match is reported like any other site,
    # which pegs the worst score at 1.0 and caps specificity at 0.5 for even a
    # spotless guide. That is the honest result of the question actually asked — the
    # tool was not told which perfect match is the intended one — but the number is
    # then not the same quantity a design report prints, so say which one this is.
    on_target_note = (
        "" if locus is not None else "  [on-target locus NOT excluded; pass --on-target]"
    )
    burden_note = (
        f", expected burden {report.expected_burden():.3f} (frequency-weighted)"
        if report.is_frequency_weighted()
        else ""
    )
    human_lines = [
        f"spacer {report.spacer} / PAM {report.pam}: {report.n_sites} site(s), "
        f"worst score {report.worst_score():.3f}, "
        f"specificity {report.specificity_score():.3f}{burden_note}{scorer_note}"
        f"{on_target_note}",
        # Every number on the line above is conditional on the budgets and cut-offs,
        # so print them under it rather than leaving "3 site(s)" to be read as absolute.
        f"  search: {report.search_description()}",
        # ...and on the genome, which the build label alone does not identify. Once,
        # under the search line, rather than repeated on every site row.
        f"  reference build {state.reference_build}"
        f"{_shape_suffix(_reference_snapshot(reference))}; {COORDINATE_NOTE}",
    ]
    # The HTML and PDF renders have shown the per-ancestry worst case since it existed;
    # the CLI put it in the JSON only. Same fact, every surface.
    strata = report.ancestry_stratification()
    if strata:
        worst_by = ", ".join(
            f"{a} {v:.3f}" for a, v in sorted(strata.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        human_lines.append(f"  worst off-target score by ancestry: {worst_by}")
        # ...and how often a genome from that population actually carries it. A score
        # does not depend on ancestry, so the line above reads the same for every
        # stratum on exactly the finding this engine exists to reproduce. Printed
        # together because either one alone is half the answer.
        burden = report.ancestry_expected_burden()
        weighted = ", ".join(
            f"{a} {v:.4f}" for a, v in sorted(burden.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        human_lines.append(f"  expected burden by ancestry (frequency-weighted): {weighted}")
    # A published matrix falls back to the length-relative approximation per hit, so one
    # report can mix two scales. `effective_matrix()` says both were used — it cannot say
    # *which row is which*, and the rows are printed in score order, so a reader compares
    # a published 0.50 against an approximated 0.60 with nothing to distinguish them. The
    # JSON has carried `score_matrix` per site all along; the human form had not. Only
    # when the report is actually mixed: on a homogeneous table the header line already
    # names the one matrix, and repeating it on every row is noise.
    matrices = {s.score_matrix for s in report.sites if s.score_matrix is not None}
    mixed_matrices = len(matrices) > 1
    for site, s in zip(report.sites, sites, strict=True):
        mit = f"  mit={s['mit_score']}" if s["mit_score"] is not None else ""
        # The PAM belongs on the row: an NGG and a low-stringency NAG site carry very
        # different real risk, and two overlapping rows are only distinguishable — one
        # locus reached from two adjacent PAMs, not one locus printed twice — by it.
        pam = f"  pam={s['pam']}" if s["pam"] else ""
        # A population site's *frequency* is what makes it actionable or not: the same
        # `score=1.0` is a hit in one genome in ten or one in a thousand, and the two
        # are different decisions. The JSON carried the frequency and the per-ancestry
        # breakdown from the start; the human line named the causal allele and stopped,
        # so the CLI user of the population-aware feature had to re-run with `--json`
        # to learn whether the site mattered.
        carried = ""
        if site.frequency is not None:
            breakdown = ", ".join(f"{a} {v:.3g}" for a, v in sorted(site.ancestries.items()))
            carried = f"  carried at {site.frequency:.3g}" + (
                f" ({breakdown})" if breakdown else ""
            )
        # `mm=0` is the most reassuring thing a row can say, and a bulged alignment says
        # it: three of the five rows in a real bulged scan read `mm=0` while being 21-nt
        # or 19-nt alignments through a gap. Only the interval width gave it away, and no
        # reader computes that. Shown when non-zero, so an ungapped table stays clean —
        # and it is also what explains the neighbouring `matrix=` fallback, since the
        # published matrix is defined only for a 20-nt ungapped alignment.
        bulges = "".join(
            f"  {label}={count}"
            for label, count in (("dna", site.dna_bulges), ("rna", site.rna_bulges))
            if count
        )
        matrix = f"  matrix={site.score_matrix}" if mixed_matrices and site.score_matrix else ""
        human_lines.append(
            f"  {s['locus']}{pam}  mm={s['mismatches']}{bulges}  "
            f"score={s['score']}{mit}{matrix}  "
            f"{s['origin']}{' ' + str(s['causal_allele']) if s['causal_allele'] else ''}"
            f"{carried}"
        )
    _emit(payload, as_json=as_json, human="\n".join(human_lines))
    # A search that examined nothing exits non-zero, after saying so. The human line
    # already reads "NO SEQUENCE WAS SEARCHED -- this is not a clean result, it is an
    # empty one", and the exit code said 0, so a pipeline branching on `$?` saw a
    # spotless guide: 0 sites, worst score 0.000, specificity 1.000. `aforge batch`
    # already draws this distinction -- a run with failed items *completes* without
    # having *succeeded* -- and a truncated reference or a scope that resolves to
    # nothing is missing data, which is what that code is for.
    if report.searched_bases == 0:
        raise typer.Exit(ExitCode.MISSING_DATA)


def _check(kind: str, artifact: str, status: str, origin: str = "") -> dict[str, str]:
    """One artifact-integrity row: what it is, which one, what was found, and from where.

    Every row used to print the word "checkpoint", datasets included — while the line
    above them counted models and datasets separately, leaving a reader to work out
    which of the rows were which. A model and a dataset fail for different reasons and
    have different remedies.

    ``origin`` is its own key rather than a suffix on ``status`` because ``status`` is a
    *machine value*: three places compare it to ``"ok"`` — the re-hashed count, the
    "nothing was established" note, and the list of what went unchecked — and it is
    published in ``--json``. Writing ``"ok (bundled)"`` into it made the note say nothing
    had been re-hashed on the line directly under a row saying it had. A word that is
    read by code is not a place to put a word for a reader.
    """
    return {"kind": kind, "artifact": artifact, "status": status, "origin": origin}


@app.command()
def verify(
    result: Annotated[
        Path,
        typer.Argument(
            help=(
                "A result JSON (ranked menu) with a provenance block, or the bare "
                "'.provenance.json' sidecar `design --out` writes beside it."
            )
        ),
    ],
    cache_dir: Annotated[
        Path | None,
        typer.Option(help="Artifact cache dir; re-hash pinned checkpoints and datasets here."),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Verify a result's provenance is complete and its pinned artifacts are intact.

    Turns provenance from a record into a checkable contract: it confirms the block
    names every model and dataset the result used and carries a seed, version, and
    config snapshot; with ``--cache-dir`` it re-hashes each pinned model checkpoint
    *and pinned dataset* found there against the hash recorded in provenance. Exits
    non-zero on incomplete provenance or an artifact hash mismatch.

    "Names every model and dataset the result used" is checked *against the result*,
    not taken on trust: a menu must name a model for each chemistry it ranks, and a
    scoring matrix a candidate says it was scored by must appear in ``datasets``. Both were
    once verifiable from the provenance block alone, which meant deleting a row passed
    — and deleting the matrix row also emptied ``--cache-dir``'s work, since that row
    is the artifact it re-hashes.

    Takes either shape `design` produces: the full result JSON, or the bare
    `<out>.provenance.json` sidecar written beside it. For `design --format` tsv, html
    and pdf the sidecar is the only machine-readable provenance a run leaves behind, so
    refusing it would put this contract out of reach of three of the four formats.
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.report.builder import DesignReport
    from alleleforge.types.candidate import RankedMenu
    from alleleforge.types.prediction import trusted_deserialization_context
    from alleleforge.types.provenance import Provenance

    if not result.is_file():
        _echo_err(f"error: result file not found: {result}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    text = result.read_text()
    # This is AlleleForge's own prior `aforge design` output, so re-read it through
    # the trusted context: a calibrated efficiency/bystander prediction keeps its
    # `calibrated=True` instead of being silently coerced to False on load.
    context = trusted_deserialization_context()
    # The three shapes this tool writes, most common first: `design --format json`
    # emits a `DesignReport`, a cohort's per-item file is a `RankedMenu`, and the
    # sidecar is a bare `Provenance`.
    #
    # `DesignReport` was previously absent from this list and a report still verified,
    # because the two candidate models overlapped enough for pydantic to coerce one
    # into the other — so `verify` was reading a different object than the file
    # described and only ever touching `.provenance`, where the difference did not
    # show. Adding a field to `DesignCandidate` ended the coincidence; naming all
    # three shapes ends the reliance on it.
    prov: Provenance | None = None
    artifact: DesignReport | RankedMenu | None = None
    errors: list[str] = []
    for model in (DesignReport, RankedMenu):
        try:
            artifact = model.model_validate_json(text, context=context)
        except ValueError as exc:
            errors.append(f"{model.__name__}: {reason(exc)}")
        else:
            prov = artifact.provenance
            break
    else:
        try:
            prov = Provenance.model_validate_json(text, context=context)
        except ValueError as exc:
            # The likeliest way to arrive here is the most natural one: `design
            # --format html` prints "wrote report.html and report.html.provenance.json",
            # and the user hands `verify` the artifact rather than the sidecar. This
            # function's own docstring already knows that for tsv/html/pdf the sidecar
            # is the only machine-readable provenance a run leaves — the refusal did
            # not, and answered with three stacked pydantic validation errors,
            # `errors.pydantic.dev` links included.
            sidecar = result.with_name(f"{result.name}.provenance.json")
            if sidecar.is_file():
                _echo_err(
                    f"error: {result.name} carries no machine-readable provenance — for "
                    "tsv, html and pdf output the provenance is written to a sidecar. "
                    f"Verify that instead:\n  aforge verify {sidecar}"
                )
                raise typer.Exit(ExitCode.USAGE) from exc
            _echo_err(
                "error: not a design report, a ranked menu, or a provenance sidecar. "
                + " / ".join(errors)
            )
            raise typer.Exit(ExitCode.USAGE) from exc
    if prov is None:
        _echo_err("error: result carries no provenance block; it is not verifiable")
        raise typer.Exit(ExitCode.UNAVAILABLE)

    problems: list[str] = []
    if not prov.alleleforge_version:
        problems.append("provenance is missing alleleforge_version")
    if not prov.config_snapshot:
        problems.append("provenance is missing config_snapshot")
    for ck in prov.models:
        if not ck.name or not ck.version:
            problems.append(f"a model checkpoint is missing name/version: {ck.name!r}")
    for ds in prov.datasets:
        if not ds.name or not ds.version:
            problems.append(f"a dataset is missing name/version: {ds.name!r}")
    # Completeness has to be checked *against the artifact* when there is one. Every
    # field above is verifiable from the provenance block alone, so a record whose
    # `models` list had simply been emptied passed as "complete and consistent" — with
    # a report full of efficiency predictions sitting in the same file. Provenance is
    # meant to name what produced the numbers; a number with nothing named against it
    # is exactly the state this command exists to refuse. The bare sidecar carries no
    # such evidence and is unaffected.
    if artifact is not None and not prov.models and _carries_a_prediction(artifact):
        problems.append(
            "provenance names no model, but the result carries model-derived "
            "predictions — nothing here says what produced them"
        )
    elif artifact is not None:
        # And the same question one level finer, since an emptied list is not the only
        # way to lose the models that matter: a block naming a model for some *other*
        # chemistry looks populated and says nothing about the candidates on the menu.
        for chemistry in _chemistries_with_no_named_model(artifact, prov.models):
            problems.append(
                f"the result ranks {chemistry} candidates, but provenance names no "
                f"{chemistry} model — nothing here says what scored them"
            )

    # The same cross-check for the dataset half of the same sentence. The models check
    # above only catches an *emptied* list; a scoring matrix can be checked by name,
    # because every candidate says which one scored its off-target table. Dropping the
    # `doench-2016-cfd` row — one edit, in the same obvious place — used to verify clean
    # *and* silently defeat `--cache-dir`, since the matrix is the one artifact that
    # actually gets re-hashed: no row, nothing to re-hash, "verified".
    if artifact is not None:
        recorded = {ds.name for ds in prov.datasets}
        for matrix in sorted(_registered_matrices_the_result_names(artifact) - recorded):
            problems.append(
                f"the result was scored by the dataset {matrix!r}, which provenance "
                "does not name — so its bytes cannot be re-hashed"
            )

    checks: list[dict[str, str]] = []
    if cache_dir is not None:
        for ck in prov.models:
            if ck.sha256 is None:
                checks.append(_check("model", f"{ck.name}.{ck.version}", "unpinned"))
                continue
            path = cache_dir / f"{ck.name}.{ck.version}.ckpt"
            if not path.is_file():
                checks.append(_check("model", f"{ck.name}.{ck.version}", "not-cached"))
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual == ck.sha256:
                checks.append(_check("model", f"{ck.name}.{ck.version}", "ok"))
            else:
                checks.append(_check("model", f"{ck.name}.{ck.version}", "MISMATCH"))
                problems.append(
                    f"checkpoint {ck.name}.{ck.version} hash mismatch: "
                    f"expected {ck.sha256[:12]}…, got {actual[:12]}…"
                )
        # A pinned dataset (e.g. the vendored Doench-2016 CFD matrix) is a
        # result-determining artifact too: the spec's tamper contract covers a
        # "checkpoint *or dataset*" whose bytes no longer match its pinned hash, so
        # re-hash datasets symmetrically rather than trusting them on name alone.
        for ds in prov.datasets:
            label = f"{ds.name}.{ds.version}"
            if ds.sha256 is None:
                checks.append(_check("dataset", label, "unpinned"))
                continue
            if ds.caller_supplied:
                # The bytes are on the caller's disk — a file they named with
                # `--gnomad`/`--clinvar`/`--haplotypes`. No cache and no bundle holds
                # them, so looking there and reporting `not-cached` offered a remedy
                # ("fetch it") that is false for this row: nothing is fetchable. The
                # check the reader *can* run is against their own copy.
                checks.append(_check("dataset", label, "caller-supplied"))
                continue
            if ds.name not in DEFAULT_REGISTRY:
                # No known cache layout to locate the bytes; report rather than pass.
                checks.append(_check("dataset", label, "unknown"))
                continue
            # A bundled dataset ships inside the installed package and is never in the
            # cache, so looking there reported "not-cached" for the one dataset whose
            # bytes are always available to hash — and it is the vendored CFD matrix,
            # which produces every specificity number on the result being verified.
            descriptor = DEFAULT_REGISTRY.get(ds.name)
            ds_path = descriptor.bundled_file() or DEFAULT_REGISTRY.cache_path(
                ds.name, cache_dir=cache_dir
            )
            if not ds_path.is_file():
                checks.append(_check("dataset", label, "not-cached"))
                continue
            ds_actual = hashlib.sha256(ds_path.read_bytes()).hexdigest()
            if ds_actual == ds.sha256:
                # Say *which* artifact matched. A bundled dataset's pin is the hash of
                # the file that ships, which need not be the artifact at `source_url` —
                # for the CFD matrix it is a conversion of it — so a bare `ok` beside a
                # URL invites a reader to check the wrong bytes and read tampering.
                checks.append(
                    _check("dataset", label, "ok", origin="bundled" if ds.bundled else "")
                )
            else:
                checks.append(_check("dataset", label, "MISMATCH"))
                problems.append(
                    f"dataset {label} hash mismatch: "
                    f"expected {ds.sha256[:12]}…, got {ds_actual[:12]}…"
                )

    # Two different claims, and only one of them was ever made. Completeness is checked
    # always; re-hashing the pinned artifacts happens only with --cache-dir. Reporting
    # "verified" for a run that hashed nothing is the same failure this project names
    # everywhere else — "not measured" printed as "clean" — and it is worst here,
    # because checking is the entire purpose of the command.
    n_ok = sum(1 for c in checks if c["status"] == "ok")
    payload: dict[str, Any] = {
        "seed": prov.seed,
        "alleleforge_version": prov.alleleforge_version,
        "n_models": len(prov.models),
        "n_datasets": len(prov.datasets),
        "checkpoint_checks": checks,
        "artifacts_rehashed": n_ok,
        "artifacts_checkable": len(checks),
        "artifact_verification_run": cache_dir is not None,
        "problems": problems,
        "verified": not problems,
    }
    human = [
        f"provenance: aforge {prov.alleleforge_version}, seed {prov.seed}, "
        f"{len(prov.models)} model(s), {len(prov.datasets)} dataset(s)"
    ]
    human += [
        f"  {c['kind']} {c['artifact']}: {c['status']}"
        + (f" ({c['origin']})" if c.get("origin") else "")
        for c in checks
    ]
    if problems:
        human.append("PROBLEMS:")
        human += [f"  - {p}" for p in problems]
    else:
        human.append("verified: provenance is complete and consistent")
    if cache_dir is None:
        human.append(
            "  NOTE: no artifact bytes were re-hashed. This checked that provenance is "
            "complete, not that the pinned checkpoints and datasets are intact — pass "
            "--cache-dir to do that."
        )
    elif n_ok == 0:
        human.append(
            f"  NOTE: --cache-dir was given but nothing was re-hashed ({len(checks)} "
            "artifact(s) unpinned, not cached, or of unknown layout). Nothing about "
            "artifact integrity was established."
        )
    elif n_ok < len(checks):
        # The partial case, which read exactly like the complete one: "verified" with a
        # per-row list a reader has to add up. A run that re-hashed one of four artifacts
        # has established something about one of them, and the other three are unmeasured
        # — the distinction this project draws everywhere else, missing from the command
        # whose entire purpose is drawing it. The zero case was already handled, which is
        # the usual shape: the total absence was foreseen and the partial one was not.
        unchecked = ", ".join(
            f"{c['artifact']} ({c['status']})" for c in checks if c["status"] != "ok"
        )
        human.append(
            f"  NOTE: re-hashed {n_ok} of {len(checks)} artifact(s). Nothing was "
            f"established about the rest: {unchecked}."
        )
        if any(c["status"] == "caller-supplied" for c in checks):
            human.append(
                "  A caller-supplied source cannot be re-hashed from a cache — the "
                "bytes are on your disk. Check it yourself by comparing your file's "
                "SHA-256 (`sha256sum`, or `shasum -a 256` on macOS) with the sha256 "
                "recorded in this provenance."
            )
    _emit(payload, as_json=as_json, human="\n".join(human))
    if problems:
        raise typer.Exit(ExitCode.UNAVAILABLE)


data_app = typer.Typer(name="data", help="Inspect the dataset registry.", no_args_is_help=True)

cache_app = typer.Typer(
    name="cache",
    help="Inspect and check the on-disk stores a run reuses work from.",
    no_args_is_help=True,
)
app.add_typer(cache_app)


#: Statuses `aforge cache verify` treats as a failure. Everything else is either a pass
#: or an explicit "nothing was checked" — which is not the same thing and is counted
#: separately rather than folded into either.
_CACHE_FAILURES = FAILURES


def _si_bytes(count: int) -> str:
    """Render a byte count the way a person reads a disk."""
    size = float(count)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"  # pragma: no cover - the loop returns first


@cache_app.command("verify")
def cache_verify(
    ctx: typer.Context,
    deep: Annotated[
        bool,
        typer.Option(
            "--deep",
            help=(
                "Also reconstruct each cached FM-index from its BWT and compare the "
                "result to the content hash recorded at build time. This is the only "
                "check that catches an index altered in place without changing its "
                "length, and it costs a full pass over the index — minutes on a "
                "whole-genome one. Without it the indexes get their cheap structural "
                "checks only."
            ),
        ),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Check the integrity of the caches this machine would serve results from.

    Four stores under the cache dir hold bytes a run trusts. Two hold **work** it reuses
    instead of recomputing: the cross-run **off-target report** cache (written by `aforge
    offtarget --cache`) and the persistent **FM-index** cache (written by `aforge
    offtarget --genome-index`). Two hold **artifacts** it was given: the **dataset** cache
    and the **checkpoint** cache, each pinned by a checksum recorded in a descriptor or a
    model card, plus the datasets that ship inside the installed package. Each store
    already knows how to detect a corrupted entry — the
    report cache re-checks a checksum sidecar, the index reconstructs its text and
    compares a content hash — but both only did so when a design happened to read that
    entry — a dataset and a checkpoint are re-hashed on every resolve, which is stricter
    still and just as reactive. So a damaged cache announced itself in the middle of the
    run that needed it, and `FMIndex.verify()`, the only check that catches an index
    altered without changing its length, was reachable from Python and from no shell.

    Exits non-zero if any entry fails, naming it. Nothing is repaired or deleted here:
    what to do with a corrupt entry is the operator's call, and both stores are
    content-addressed, so deleting the named directory or file is always safe.
    """
    from alleleforge.cache_sweep import held_bytes, verify_stores
    from alleleforge.config import get_settings

    state: GlobalState = ctx.obj
    cache_root = state.cache_dir if state.cache_dir is not None else get_settings().cache_dir
    # The sweep is the library's; this command renders it and picks an exit code. It was
    # written here first, which left a Python caller — or the web API, or a deployment's
    # own health check — holding a suspect cache directory with no way to ask.
    checks = [
        _check(check.kind, check.artifact, check.status, check.detail)
        for check in verify_stores(cache_root, deep=deep)
    ]

    held = held_bytes(cache_root)
    failed = [c for c in checks if c["status"] in _CACHE_FAILURES]
    unchecked = [c for c in checks if c["status"] in ("unpinned", "not-cached", "unverifiable")]
    examined = [c for c in checks if c not in unchecked]
    width = max((len(c["artifact"]) for c in examined), default=0)
    human = [f"cache dir: {cache_root}"]
    human += [f"  {c['kind']:18s} {c['artifact']:{width}s} {c['status']}" for c in examined]
    if not examined:
        human.append("  nothing to check here — no store holds an entry with a pin.")
    if unchecked:
        # Listed by count, not one line each: two dozen unpinned model cards would bury
        # the rows that carry an answer.
        absent = sum(1 for c in unchecked if c["status"] == "not-cached")
        unverifiable = sum(1 for c in unchecked if c["status"] == "unverifiable")
        human.append(
            f"  NOTE: {len(unchecked)} artifact(s) were not checked — {absent} pinned but "
            f"not on this disk, {len(unchecked) - absent - unverifiable} carrying no pin "
            f"at all, {unverifiable} in a cache namespace that stores no checksum. Almost "
            "none of the registry ships or is downloaded by default; `aforge data list` "
            "says which, and `--json` lists every row."
        )
    if not deep and any(c["kind"] == "fm-index" for c in checks):
        human.append(
            "  NOTE: the FM-indexes got their structural checks only. An index altered "
            "in place without changing its length still reads as intact — pass --deep "
            "to reconstruct and re-hash it."
        )
    for c in failed:
        human.append(f"  {c['artifact']}: {c['origin']}")
    if held:
        listed = ", ".join(f"{store} {_si_bytes(size)}" for store, size in held.items())
        human.append(
            f"  holding {_si_bytes(sum(held.values()))} on disk ({listed}). Nothing "
            "evicts these: every store here is content-addressed, so a changed input is "
            "a new key and the old entry stays. Deleting any of them is safe — the next "
            "run recomputes or re-fetches what it needs."
        )
    _emit(
        {"cache_dir": str(cache_root), "checks": checks, "held_bytes": held},
        as_json=as_json,
        human="\n".join(human),
    )
    if failed:
        raise typer.Exit(ExitCode.UNAVAILABLE)


@app.command()
def lift(
    loci: Annotated[
        list[str],
        typer.Argument(
            help="Loci to lift, 'chrom:start-end' — 0-based half-open, as everywhere else."
        ),
    ],
    chain: Annotated[
        Path, typer.Option("--chain", help="A local UCSC chain file. Never downloaded.")
    ],
    from_build: Annotated[
        str, typer.Option("--from", help="The build the input loci are in, e.g. 'hg19'.")
    ],
    to_build: Annotated[str, typer.Option("--to", help="The build to lift to, e.g. 'hg38'.")],
) -> None:
    """Lift loci to another assembly, so a build mismatch has a remedy in the tool.

    `resolve` refuses a record whose native assembly disagrees with the requested
    build — the right answer, since relabeling a coordinate designs a guide at the
    wrong place in the genome — and tells the caller to lift first. This is that
    operation: run it on the loci, then re-run `resolve` or `design` on the output.

    Prints `input<TAB>output` per locus, in order, in the same locus form `design --region`
    accepts, so the result pipes straight back in. An unmappable locus prints
    `UNMAPPED` rather than being dropped — a shorter list is a smaller search — and
    exits non-zero.
    """
    from alleleforge.genome.coordinates import Liftover

    if not chain.is_file():
        _echo_err(f"error: chain file not found: {chain}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    intervals = [GenomicInterval.parse(text) for text in _parsed_loci(loci)]
    try:
        lo = Liftover.from_chain_file(chain, source_build=from_build, target_build=to_build)
    except ImportError as exc:  # pragma: no cover - depends on the optional extra
        _echo_err(
            f"error: liftover needs pyliftover: pip install 'pyliftover>=0.4' ({reason(exc)})"
        )
        raise typer.Exit(ExitCode.UNAVAILABLE) from exc
    except (OSError, ValueError) as exc:
        _echo_err(f"error: could not read chain file {chain}: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc

    unmapped = 0
    for interval in intervals:
        lifted = lo.lift_interval(interval)
        if lifted is None:
            unmapped += 1
            typer.echo(f"{interval}\tUNMAPPED")
        else:
            typer.echo(f"{interval}\t{lifted}")
    if unmapped:
        _echo_err(
            f"error: {unmapped} of {len(intervals)} loci did not lift from "
            f"{from_build} to {to_build}; they are dropped, not approximated"
        )
        raise typer.Exit(ExitCode.UNAVAILABLE)


def _parsed_loci(loci: list[str]) -> list[str]:
    """Return ``loci``, failing with a usage error on the first unparseable one."""
    for text in loci:
        try:
            GenomicInterval.parse(text)
        except ValueError as exc:
            _echo_err(f"error: {reason(exc)}")
            raise typer.Exit(ExitCode.USAGE) from exc
    return loci


app.add_typer(data_app)


@data_app.command("list")
def data_list(
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """List every registered dataset with its version and license."""
    from alleleforge.data.registry import (
        DEFAULT_REGISTRY,
        dataset_permission,
        dataset_presence,
        dataset_status,
    )

    rows = [
        {
            "name": name,
            "version": d.version,
            "license": d.license,
            **status,
            # The sentence the human table prints, so the two renderings of this row
            # carry the same answer — and so does `GET /api/data`, which grew it first.
            "presence": dataset_presence(status),
        }
        for name in DEFAULT_REGISTRY.names
        for d in (DEFAULT_REGISTRY.get(name),)
        for status in (dataset_status(name, d),)
    ]
    human_rows = []
    for name in DEFAULT_REGISTRY.names:
        d = DEFAULT_REGISTRY.get(name)
        status = dataset_status(name, d)
        human_rows.append(
            f"{name:16s} {d.version or '-':14s} {d.license or '-':18s} "
            f"{dataset_permission(status):16s} {dataset_presence(status)}"
        )
    human = "\n".join(
        [
            *human_rows,
            "",
            "'may redistribute' is a licence permission, not a statement that the data "
            "is present: almost none of it ships. Only a dataset marked bundled or "
            "cached is usable by a run right now, and only a dataset with a pinned "
            "checksum can be fetched at all — the registry refuses to download what it "
            "cannot verify.",
        ]
    )
    _emit({"datasets": rows}, as_json=as_json, human=human)


@data_app.command("show")
def data_show(
    name: Annotated[str, typer.Argument(help="Dataset name (see `aforge data list`).")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Show one dataset's full provenance descriptor."""
    from alleleforge.data.registry import (
        DEFAULT_REGISTRY,
        dataset_permission,
        dataset_presence,
        dataset_reason,
        dataset_status,
    )

    if name not in DEFAULT_REGISTRY:
        _echo_err(f"error: unknown dataset {name!r}; known: {DEFAULT_REGISTRY.names}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    d = DEFAULT_REGISTRY.get(name)
    # The descriptor's own fields say what this dataset *is*; they do not say whether a
    # run can use it, which is the question someone runs `show` on a dataset to answer.
    # `list` grew that answer and `show` did not, so the command for one dataset printed
    # `redistributable: True` and `sha256: None` and left the reader to know that the
    # first is a licence permission and the second means it cannot even be fetched.
    status = dataset_status(name, d)
    payload = {**d.model_dump(), **status, "presence": dataset_presence(status)}
    human = "\n".join(f"{k}: {v}" for k, v in payload.items())
    # One line answering the question, because the fields above answer it only to a
    # reader who already knows that `redistributable` is a permission and that a null
    # `sha256` means the registry will not even fetch it.
    human += (
        f"\n\nusable by a run right now: {'yes' if status['available'] else 'NO'} — "
        f"{dataset_reason(status)}. Licence: {dataset_permission(status)}."
    )
    _emit(payload, as_json=as_json, human=human)


bench_app = typer.Typer(
    name="bench", help="Run CRISPR-Bench tasks (Phase 14).", no_args_is_help=True
)
app.add_typer(bench_app)


@bench_app.command("list")
def bench_list(
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """List the CRISPR-Bench tasks, their datasets, and primary metrics."""
    # The benchmark stack transitively imports the genome layer, so a
    # `pip install 'alleleforge[cli]'` — a documented install, and one a
    # benchmark run needs no reference genome for — failed here with a raw
    # `ModuleNotFoundError` traceback. `design`, `batch` and `offtarget` all
    # route this through `_missing_dependency`; `bench` was the fourth place
    # that needed it and the one that did not have it.
    try:
        from alleleforge.benchmark.tasks import TASKS
    except ImportError as exc:
        _missing_dependency(exc)

    tasks = [TASKS[name] for name in sorted(TASKS)]
    rows: list[dict[str, Any]] = [
        {
            "task": t.name,
            "kind": t.kind.value,
            "chemistry": t.chemistry,
            "dataset": t.dataset,
            "primary_metric": t.primary_metric,
            "metrics": list(t.metrics),
        }
        for t in tasks
    ]
    human = "\n".join(
        f"{t.name:26s} {t.kind.value:14s} {t.dataset:22s} -> {t.primary_metric} "
        f"(+ {', '.join(m for m in t.metrics if m != t.primary_metric)})"
        for t in tasks
    )
    _emit({"tasks": rows}, as_json=as_json, human=human)


@bench_app.command("run")
def bench_run(
    ctx: typer.Context,
    task: Annotated[str, typer.Argument(help="Task name (see `aforge bench list`).")],
    split_version: Annotated[str, typer.Option(help="Frozen split version to score.")] = "v1",
    out: Annotated[Path | None, typer.Option(help="Write the signed result JSON here.")] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full signed result JSON to stdout.")
    ] = False,
) -> None:
    """Score the reference baseline on a task's frozen test split.

    Emits a signed, provenance-stamped result. Real models plug in through the
    Python API (``run_benchmark``) and the leaderboard submission format.
    """
    # The benchmark stack transitively imports the genome layer, so a
    # `pip install 'alleleforge[cli]'` — a documented install, and one a
    # benchmark run needs no reference genome for — failed here with a raw
    # `ModuleNotFoundError` traceback. `design`, `batch` and `offtarget` all
    # route this through `_missing_dependency`; `bench` was the fourth place
    # that needed it and the one that did not have it.
    try:
        from alleleforge.benchmark.baseline import build_baseline
        from alleleforge.benchmark.runner import run_benchmark
        from alleleforge.benchmark.splits import SplitIntegrityError, load_split
        from alleleforge.benchmark.tasks import get_task
    except ImportError as exc:
        _missing_dependency(exc)

    state: GlobalState = ctx.obj
    try:
        task_obj = get_task(task)
    except KeyError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc
    try:
        split, dataset = load_split(task, version=split_version)
    except FileNotFoundError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc
    except SplitIntegrityError as exc:
        _echo_err(f"error: split integrity check failed: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc

    baseline = build_baseline(task_obj, split, dataset)
    result = run_benchmark(
        baseline, task_obj, split=split, dataset=dataset, seed=state.seed_or_default
    )

    if out is not None:
        out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        _echo_err(f"wrote {out}")
    # The bundled fixtures are synthetic stand-ins and had always said so in a field
    # nothing read, so a Spearman over ten synthetic rows printed in exactly the shape
    # of one over GUIDE-seq. Saying so beside the number fixed that for the reader who
    # runs the command bare — and left it broken for the two who keep the number.
    # `--out` printed "wrote <path>" and nothing else; `--json` printed the body, whose
    # `dataset_is_synthetic` field is the same field nothing reads. Those are the users
    # who save, share and publish it. The caveat goes to stderr, where this CLI puts
    # every message about a side effect, so it reaches all three without putting a
    # sentence in a pipeline's data stream.
    if result.dataset_is_synthetic:
        _echo_err(
            f"NOTE: dataset {result.dataset!r} is the bundled SYNTHETIC stand-in "
            "shipped so the harness runs in CI. This number measures the contract, "
            "not the model — it is not a benchmark result."
        )
    # A ranking metric can be undefined — a correlation over constant predictions, an
    # AUROC over a single-class fold — and this is the only surface that can say why
    # while the person who ran it is still looking. It reaches `--out` and `--json`
    # callers too, for the same reason the synthetic caveat above does: those are the
    # users who save and publish the number that is not there.
    if result.primary_value is None:
        _echo_err(
            f"NOTE: {result.primary_metric} is UNDEFINED for this run, not zero — "
            f"{result.primary_undefined_reason}. The result is recorded and will not "
            "be ranked."
        )
    if as_json:
        typer.echo(result.model_dump_json(indent=2))
    elif out is None:
        # ECE is undefined (None) for a degenerate fold with no scorable
        # predictions; show "n/a" (as the leaderboard does) rather than crashing on
        # None.__format__.
        ece = result.metrics["ece"]
        ece_str = "n/a" if ece is None else f"{ece:.4f}"
        primary = "undefined" if result.primary_value is None else f"{result.primary_value:.4f}"
        typer.echo(
            f"{result.task} @ {result.split_version}: {result.primary_metric}="
            f"{primary}, ece={ece_str} "
            f"(n={result.n_test}, model={result.model.name})"
        )


@bench_app.command("gap")
def bench_gap(
    task: Annotated[str, typer.Argument(help="Task name (see `aforge bench list`).")],
    split_version: Annotated[str, typer.Option(help="Frozen split version to score.")] = "v1",
    in_context_fold: Annotated[
        str, typer.Option(help="The fold from a context the model saw (train/val/test).")
    ] = "val",
    held_out_fold: Annotated[
        str, typer.Option(help="The fold from the held-out context (train/val/test).")
    ] = "test",
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Measure how much worse the baseline scores a cell type it did not see.

    A single test-split number says how well a model does on the contexts the
    benchmark happens to hold out; it does not say whether the model transfers.
    This scores an in-context fold and a held-out one and reports the drop between
    them, oriented so a positive gap always means worse generalization, whichever
    direction the task's primary metric ranks in.
    """
    try:
        from alleleforge.benchmark.baseline import build_baseline
        from alleleforge.benchmark.runner import generalization_gap
        from alleleforge.benchmark.splits import SplitIntegrityError, load_split
        from alleleforge.benchmark.tasks import get_task
    except ImportError as exc:
        _missing_dependency(exc)

    try:
        task_obj = get_task(task)
    except KeyError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc
    try:
        split, dataset = load_split(task, version=split_version)
    except FileNotFoundError as exc:
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc
    except SplitIntegrityError as exc:
        _echo_err(f"error: split integrity check failed: {reason(exc)}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc

    baseline = build_baseline(task_obj, split, dataset)
    try:
        gap = generalization_gap(
            baseline,
            task_obj,
            split=split,
            dataset=dataset,
            in_context_fold=in_context_fold,
            held_out_fold=held_out_fold,
        )
    except ValueError as exc:
        # An unknown fold name, or a fold too degenerate for the primary metric to
        # be defined on. Both are the caller's input, not a crash.
        _echo_err(f"error: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc

    # Same caveat, same stream, same reason as `bench run`: the bundled fixtures are
    # synthetic, and a gap over ten synthetic rows prints in the shape of one over
    # real data. `dataset_is_synthetic` lives on the result model, which this
    # operation does not build, so it is read off the dataset directly.
    if dataset.synthetic:
        _echo_err(
            f"NOTE: dataset {dataset.name!r} is the bundled SYNTHETIC stand-in "
            "shipped so the harness runs in CI. This gap measures the contract, "
            "not the model — it is not a generalization result."
        )
    if as_json:
        typer.echo(gap.model_dump_json(indent=2))
    else:
        direction = "higher is better" if gap.higher_is_better else "lower is better"
        typer.echo(
            f"{gap.task} @ {split_version}: {gap.primary_metric} "
            f"({direction}) {gap.in_context_fold}={gap.in_context:.4f} "
            f"{gap.held_out_fold}={gap.held_out:.4f} -> gap={gap.gap:+.4f} "
            "(positive = worse on the held-out context)"
        )


@bench_app.command("compare")
def bench_compare(
    left: Annotated[Path, typer.Argument(help="A benchmark result JSON.")],
    right: Annotated[Path, typer.Argument(help="Another benchmark result JSON.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Check whether two benchmark results are the *same scientific result*.

    This is the operation the reproducibility digest exists for. It covers
    the scientific body only — task, split identity, dataset, metrics, model — so two
    runs on different platforms, releases or wall clocks agree iff the science agrees.

    Each result's stored digest is also re-derived from its own body first: a digest
    nobody recomputes is a claim nobody checks.
    """
    # The benchmark stack transitively imports the genome layer, so a
    # `pip install 'alleleforge[cli]'` — a documented install, and one a
    # benchmark run needs no reference genome for — failed here with a raw
    # `ModuleNotFoundError` traceback. `design`, `batch` and `offtarget` all
    # route this through `_missing_dependency`; `bench` was the fourth place
    # that needed it and the one that did not have it.
    try:
        from alleleforge.benchmark.runner import BenchmarkResult
    except ImportError as exc:
        _missing_dependency(exc)

    results: list[BenchmarkResult] = []
    for path in (left, right):
        try:
            results.append(BenchmarkResult.model_validate_json(path.read_text()))
        except FileNotFoundError:
            _echo_err(f"error: result file not found: {path}")
            raise typer.Exit(ExitCode.MISSING_DATA) from None
        except ValueError as exc:
            _echo_err(f"error: {path} is not a valid benchmark result: {reason(exc)}")
            raise typer.Exit(ExitCode.USAGE) from exc

    a, b = results
    problems: list[str] = []
    for path, result in zip((left, right), results, strict=True):
        if not result.verify_signature():
            problems.append(f"{path}: signature does not match its contents")
        if not result.verify_reproducibility_digest():
            problems.append(f"{path}: reproducibility digest does not match its scientific body")

    agree = a.agrees_with(b)
    differences: list[str] = []
    if not agree:
        left_body, right_body = a.scientific_body(), b.scientific_body()
        differences = [
            f"{key}: {left_body[key]!r} != {right_body[key]!r}"
            for key in sorted(left_body)
            if left_body[key] != right_body[key]
        ]
    # `run` says a number came from a synthetic stand-in; `compare` never read the flag,
    # so two stand-in results were pronounced "the same scientific result" — the strongest
    # sentence this tool says, and the one a reader is most likely to keep as evidence of
    # reproducibility. Whether they agree is unaffected; what they agree *about* is not a
    # benchmark result, and only this command knew both sides.
    synthetic = sorted(
        {result.dataset for result in (a, b) if getattr(result, "dataset_is_synthetic", False)}
    )
    payload = {
        "agree": agree and not problems,
        "left_digest": a.reproducibility_digest,
        "right_digest": b.reproducibility_digest,
        "differences": differences,
        "problems": problems,
        "synthetic_datasets": synthetic,
    }
    human = [
        f"{left.name}: {a.task} @ {a.split_version}  digest {a.reproducibility_digest[:12]}…",
        f"{right.name}: {b.task} @ {b.split_version}  digest {b.reproducibility_digest[:12]}…",
    ]
    if problems:
        human.append("PROBLEMS:")
        human += [f"  - {p}" for p in problems]
    elif agree:
        human.append("agree: the same scientific result (timestamps and versions aside)")
    else:
        human.append("DIFFER: these are not the same scientific result")
        human += [f"  - {d}" for d in differences]
    if synthetic:
        # On stderr, as in `bench run`: it reaches the reader who redirected stdout or
        # asked for JSON, without putting a sentence in the data stream.
        _echo_err(
            f"NOTE: {', '.join(repr(name) for name in synthetic)} "
            f"{'is a' if len(synthetic) == 1 else 'are'} bundled SYNTHETIC stand-in"
            f"{'' if len(synthetic) == 1 else 's'} shipped so the harness runs in CI. "
            "Agreement here says the pipeline is reproducible; it is not agreement about "
            "a benchmark result."
        )
    _emit(payload, as_json=as_json, human="\n".join(human))
    if problems or not agree:
        raise typer.Exit(ExitCode.UNAVAILABLE)


class LeaderboardFormat(StrEnum):
    """Renderings the leaderboard command can produce."""

    markdown = "markdown"
    html = "html"


@bench_app.command("leaderboard")
def bench_leaderboard(
    results: Annotated[
        list[Path],
        typer.Argument(help="Signed result JSON files (e.g. from `aforge bench run --out`)."),
    ],
    submitter: Annotated[
        str, typer.Option(help="Submitter name recorded for the local results.")
    ] = "local",
    fmt: Annotated[
        LeaderboardFormat, typer.Option("--format", help="Output format.")
    ] = LeaderboardFormat.markdown,
    out: Annotated[Path | None, typer.Option(help="Write the rendered board here.")] = None,
) -> None:
    """Aggregate signed result JSONs into the model-card-gated leaderboard.

    Results are grouped by model into card-gated submissions; every result must
    verify its own signature and carry a complete model card (name, license,
    citation), so the board cannot show a number that was edited after signing.
    """
    from datetime import UTC, datetime

    # The benchmark stack transitively imports the genome layer, so a
    # `pip install 'alleleforge[cli]'` — a documented install, and one a
    # benchmark run needs no reference genome for — failed here with a raw
    # `ModuleNotFoundError` traceback. `design`, `batch` and `offtarget` all
    # route this through `_missing_dependency`; `bench` was the fourth place
    # that needed it and the one that did not have it.
    try:
        from alleleforge.benchmark.leaderboard import Leaderboard, Submission, SubmissionError
        from alleleforge.benchmark.runner import BenchmarkResult
    except ImportError as exc:
        _missing_dependency(exc)

    by_model: dict[str, list[BenchmarkResult]] = {}
    for path in results:
        if not path.is_file():
            _echo_err(f"error: result file not found: {path}")
            raise typer.Exit(ExitCode.MISSING_DATA)
        try:
            result = BenchmarkResult.model_validate_json(path.read_text())
        except ValueError as exc:
            _echo_err(f"error: {path} is not a valid result JSON: {reason(exc)}")
            raise typer.Exit(ExitCode.USAGE) from exc
        by_model.setdefault(result.model.name, []).append(result)

    board = Leaderboard()
    now = datetime.now(UTC)
    try:
        for model_results in by_model.values():
            board.add(
                Submission(
                    submitter=submitter,
                    model=model_results[0].model,
                    results=tuple(model_results),
                    submitted_at=now,
                )
            )
    except SubmissionError as exc:
        _echo_err(f"error: inadmissible submission: {reason(exc)}")
        raise typer.Exit(ExitCode.USAGE) from exc

    rendered = board.render_html() if fmt is LeaderboardFormat.html else board.render_markdown()
    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        _echo_err(f"wrote {out}")
    else:
        typer.echo(rendered)


if __name__ == "__main__":  # pragma: no cover
    app()
