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

import hashlib
import json
import tomllib
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from alleleforge._version import __version__
from alleleforge.config import DEFAULT_REFERENCE, DEFAULT_SEED


class ExitCode(IntEnum):
    """Distinct process exit codes (``2`` is Typer's own usage-error code)."""

    OK = 0
    USAGE = 2
    MISSING_DATA = 3
    UNAVAILABLE = 4


@dataclass
class GlobalState:
    """Global options shared by every command, set in the root callback."""

    seed: int = DEFAULT_SEED
    reference_build: str = DEFAULT_REFERENCE
    cache_dir: Path | None = None
    verbose: bool = False


app = typer.Typer(
    name="aforge",
    help="AlleleForge: variant-driven, uncertainty-aware CRISPR edit design.",
    no_args_is_help=True,
    add_completion=False,
)


def _echo_err(message: str) -> None:
    """Write a message to stderr."""
    typer.echo(message, err=True)


def _version_callback(value: bool) -> None:
    """Print the version and exit (eager ``--version``)."""
    if value:
        typer.echo(__version__)
        raise typer.Exit(ExitCode.OK)


@app.callback()
def main(
    ctx: typer.Context,
    seed: Annotated[int, typer.Option(help="Global random seed (recorded in provenance).")] = (
        DEFAULT_SEED
    ),
    reference: Annotated[
        str, typer.Option(help="Reference build identifier (e.g. hg38, T2T-CHM13v2, mm39).")
    ] = DEFAULT_REFERENCE,
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
        seed=seed, reference_build=reference, cache_dir=cache_dir, verbose=verbose
    )


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

    return ReferenceGenome(fasta, build=build)


def _emit(payload: dict[str, Any], *, as_json: bool, human: str) -> None:
    """Print JSON or a human string depending on ``as_json``."""
    typer.echo(json.dumps(payload, indent=2, default=str) if as_json else human)


@app.command()
def resolve(
    ctx: typer.Context,
    variant: Annotated[str, typer.Argument(help="ClinVar / rsID / HGVS / VCF / coords input.")],
    reference_fasta: Annotated[
        Path | None, typer.Option(help="Reference FASTA for left-alignment + ref validation.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Normalize any input form to a canonical variant (debugging aid)."""
    from alleleforge.variant.resolver import resolve as resolve_variant

    state: GlobalState = ctx.obj
    reference = (
        _load_reference(reference_fasta, state.reference_build)
        if reference_fasta is not None
        else None
    )
    try:
        resolved = resolve_variant(variant, build=state.reference_build, reference=reference)
    except ValueError as exc:
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc
    v = resolved.variant
    payload = {
        "variant": str(v),
        "variant_class": v.variant_class.value,
        "build": v.build,
        "source": resolved.source,
        "working_interval": str(resolved.working_interval),
        "reference_recommendation": (
            resolved.reference_recommendation.recommended_build
            if resolved.reference_recommendation is not None
            else None
        ),
    }
    human = (
        f"{v}  [{v.variant_class.value}, build {v.build}, from {resolved.source}]\n"
        f"working interval: {resolved.working_interval}"
    )
    _emit(payload, as_json=as_json, human=human)


def _parse_weights(spec: str | None) -> Any:
    """Parse a ``eff,clean,safe,simple`` weights string into RankingWeights."""
    from alleleforge.design.ranking import DEFAULT_WEIGHTS, RankingWeights

    if spec is None:
        return DEFAULT_WEIGHTS
    parts = spec.split(",")
    if len(parts) != 4:
        _echo_err("error: --weights expects 'efficiency,cleanliness,safety,simplicity'")
        raise typer.Exit(ExitCode.USAGE)
    try:
        eff, clean, safe, simple = (float(p) for p in parts)
        # RankingWeights rejects non-finite / negative / all-zero weights; surface
        # those as a clean usage error rather than an uncaught traceback.
        return RankingWeights(efficiency=eff, cleanliness=clean, safety=safe, simplicity=simple)
    except ValueError as exc:
        _echo_err(f"error: --weights must be four non-negative numbers: {exc}")
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
        "cell_context",
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


class OutputFormat(StrEnum):
    """Design output formats."""

    json = "json"
    tsv = "tsv"
    html = "html"
    pdf = "pdf"


@app.command()
def design(
    ctx: typer.Context,
    variant: Annotated[str, typer.Argument(help="ClinVar / rsID / HGVS / VCF / coords input.")],
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
    weights: Annotated[
        str | None, typer.Option(help="Ranking weights 'eff,clean,safe,simple'.")
    ] = None,
    max_per_chemistry: Annotated[
        int | None, typer.Option(help="Cap candidates kept per chemistry.")
    ] = None,
    no_offtarget: Annotated[
        bool, typer.Option("--no-offtarget", help="Skip the off-target search.")
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
    trained_base_outcome: Annotated[
        bool,
        typer.Option(
            "--trained-base-outcome",
            help="Use the real trained BE-DICT model for the base-edit window "
            "outcome (opt-in; needs a BE-DICT checkout via $ALLELEFORGE_BEDICT_REPO). "
            "Default is the weight-free baseline.",
        ),
    ] = False,
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
        bool, typer.Option("--json", help="Also print the ranked menu as JSON to stdout.")
    ] = False,
) -> None:
    """Design a ranked, multi-chemistry editing menu for a variant."""
    from alleleforge.config import Settings
    from alleleforge.design.designer import design as run_design
    from alleleforge.report.builder import build_report
    from alleleforge.report.export import report_to_json, report_to_tsv
    from alleleforge.report.html import render_html
    from alleleforge.report.pdf import render_pdf
    from alleleforge.types.edit import Chemistry, EditIntent
    from alleleforge.variant.resolver import resolve as resolve_variant

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
    cell_context = cfg.get("cell_context")
    trained_efficiency = trained_efficiency or bool(cfg.get("trained_efficiency", False))
    trained_outcome = trained_outcome or bool(cfg.get("trained_outcome", False))
    trained_base_outcome = trained_base_outcome or bool(cfg.get("trained_base_outcome", False))
    run_offtarget = _resolve_run_offtarget(no_offtarget, cfg)

    try:
        edit_intent = EditIntent(intent_str)
    except ValueError as exc:
        _echo_err(f"error: unknown intent {intent_str!r}")
        raise typer.Exit(ExitCode.USAGE) from exc
    chemistries = None
    if chem_list:
        try:
            chemistries = [Chemistry(c) for c in chem_list]
        except ValueError as exc:
            _echo_err(f"error: unknown chemistry: {exc}")
            raise typer.Exit(ExitCode.USAGE) from exc
    pops = [p.strip() for p in pops_str.split(",")] if pops_str else None

    reference = _load_reference(reference_fasta, state.reference_build)
    # Honor the user's config file (its Settings keys) with the CLI --seed as
    # an override, so a config.toml maf_threshold/interval_level/cache_dir is
    # applied instead of being silently ignored.
    settings = Settings.load(config_file=config, seed=state.seed)
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
    try:
        resolved = resolve_variant(variant, build=state.reference_build, reference=reference)
        menu = run_design(
            resolved,
            reference=reference,
            intent=edit_intent,
            chemistries=chemistries,
            weights=weights_obj,
            populations=pops,
            run_offtarget=run_offtarget,
            max_candidates_per_chemistry=max_per_chemistry,
            cell_context=cell_context,
            settings=settings,
            cas9_efficiency_scorer=cas9_scorer,
            cas9_outcome_predictor=cas9_outcome,
            base_outcome_predictor=base_outcome,
        )
    except ValueError as exc:
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc

    report = build_report(menu, variant=str(resolved.variant), intent=edit_intent.value)
    if state.verbose:
        _echo_err(
            f"{len(menu.candidates)} candidate(s); best: "
            f"{menu.best.chemistry.value if menu.best else 'none'}"
        )

    if fmt is OutputFormat.json:
        rendered: bytes = report_to_json(report).encode()
    elif fmt is OutputFormat.tsv:
        rendered = report_to_tsv(report).encode()
    elif fmt is OutputFormat.html:
        rendered = render_html(report).encode()
    else:
        rendered = render_pdf(report)

    if out is not None:
        out.write_bytes(rendered)
        sidecar = out.with_suffix(out.suffix + ".provenance.json")
        if menu.provenance is not None:
            sidecar.write_text(menu.provenance.model_dump_json(indent=2), encoding="utf-8")
        typer.echo(f"wrote {out}" + (f" and {sidecar}" if menu.provenance else ""))
    elif fmt in (OutputFormat.json, OutputFormat.tsv):
        typer.echo(rendered.decode())
    else:
        _echo_err(f"error: --format {fmt.value} requires --out")
        raise typer.Exit(ExitCode.USAGE)

    if as_json and out is not None:
        typer.echo(menu.model_dump_json(indent=2))


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


def _batch_rows(report: Any) -> list[dict[str, Any]]:
    """Flatten a ``CohortRunReport`` into per-item summary rows."""
    rows: list[dict[str, Any]] = []
    for it in report.items:
        summary = it.summary or {}
        rows.append(
            {
                "item_id": it.item_id,
                "status": it.status,
                "best_chemistry": summary.get("best_chemistry"),
                "best_efficiency": summary.get("best_efficiency"),
                "best_bystander_burden": summary.get("best_bystander_burden"),
                "worst_offtarget": summary.get("worst_offtarget"),
                "best_specificity": summary.get("best_specificity"),
                "n_candidates": summary.get("n_candidates"),
                "error": it.error,
            }
        )
    return rows


def _batch_tsv(rows: list[dict[str, Any]]) -> str:
    """Render the per-item summary rows as TSV (one row per cohort item)."""
    cols = [
        "item_id",
        "status",
        "best_chemistry",
        "best_efficiency",
        "best_bystander_burden",
        "worst_offtarget",
        "best_specificity",
        "n_candidates",
        "error",
    ]

    def _cell(value: Any) -> str:
        # Neutralize the delimiters so a tab/newline in a field (item_id is a raw
        # input line; error is an exception message) cannot misalign the TSV.
        if value is None:
            return ""
        return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")

    lines = ["\t".join(cols)]
    for r in rows:
        lines.append("\t".join(_cell(r[c]) for c in cols))
    return "\n".join(lines) + "\n"


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
    output_dir: Annotated[
        Path | None, typer.Option(help="Write each item's full menu JSON to <dir>/<item>.json.")
    ] = None,
    max_workers: Annotated[
        int, typer.Option(help="Thread pool size (a fresh reference is opened per worker).")
    ] = 1,
    summary_tsv: Annotated[
        Path | None, typer.Option(help="Write a per-item TSV summary here.")
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
    from alleleforge.config import Settings
    from alleleforge.design.cohort import design_many
    from alleleforge.types.edit import EditIntent

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
    run_offtarget = _resolve_run_offtarget(no_offtarget, cfg)

    try:
        edit_intent = EditIntent(intent_str)
    except ValueError as exc:
        _echo_err(f"error: unknown intent {intent_str!r}")
        raise typer.Exit(ExitCode.USAGE) from exc
    if not inputs.is_file():
        _echo_err(f"error: input file not found: {inputs}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    pops = [p.strip() for p in pops_str.split(",")] if pops_str else None

    reference = _load_reference(reference_fasta, state.reference_build)
    assert reference_fasta is not None  # _load_reference exits otherwise
    # Honor the user's config file (its Settings keys) with the CLI --seed as
    # an override, so a config.toml maf_threshold/interval_level/cache_dir is
    # applied instead of being silently ignored.
    settings = Settings.load(config_file=config, seed=state.seed)

    if _is_vcf_path(inputs):
        from alleleforge.variant import iter_vcf

        variants: Any = iter_vcf(inputs)
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
        report = design_many(
            variants,
            intent=edit_intent,
            manifest_path=manifest,
            resume=not no_resume,
            output_dir=output_dir,
            max_workers=max_workers,
            item_id=_batch_item_id,
            build=state.reference_build,
            weights=weights_obj,
            populations=pops,
            run_offtarget=run_offtarget,
            max_candidates_per_chemistry=max_per_chemistry,
            settings=settings,
            **ref_kwargs,
        )
    except RuntimeError as exc:  # e.g. a VCF input but cyvcf2 is not installed
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.UNAVAILABLE) from exc

    rows = _batch_rows(report)
    if summary_tsv is not None:
        summary_tsv.write_text(_batch_tsv(rows), encoding="utf-8")
    if state.verbose:
        _echo_err(f"designed {report.succeeded}/{report.total} (skipped {report.skipped})")

    if as_json:
        payload = {
            "provenance": report.provenance,
            "total": report.total,
            "succeeded": report.succeeded,
            "failed": report.failed,
            "skipped": report.skipped,
            "items": rows,
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        return

    header = (
        f"cohort: {report.total} item(s) — {report.succeeded} ok, "
        f"{report.failed} failed, {report.skipped} skipped (resume)"
    )
    lines = [header]
    for r in rows:
        if r["status"] == "ok":
            eff = r["best_efficiency"]
            eff_str = f"{eff:.2f}" if isinstance(eff, (int, float)) else "-"
            lines.append(
                f"  {r['item_id']}  ok  best={r['best_chemistry'] or '-'}  "
                f"eff={eff_str}  n={r['n_candidates'] or 0}"
            )
        else:
            lines.append(f"  {r['item_id']}  error  {r['error']}")
    typer.echo("\n".join(lines))
    if summary_tsv is not None:
        typer.echo(f"wrote {summary_tsv}")


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
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Run population/haplotype-aware off-target search for a spacer."""
    from alleleforge.offtarget.engine import search
    from alleleforge.types.guide import PAM

    state: GlobalState = ctx.obj
    reference = _load_reference(reference_fasta, state.reference_build)
    pops = [p.strip() for p in populations.split(",")] if populations else None
    try:
        report = search(
            spacer,
            PAM(pattern=pam),
            reference=reference,
            mismatches=mismatches,
            dna_bulges=dna_bulges,
            rna_bulges=rna_bulges,
            cfd_threshold=cfd_threshold,
            mit_threshold=mit_threshold,
            maf=maf,
            populations=pops,
        )
    except ValueError as exc:
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc

    sites = [
        {
            "locus": str(s.locus),
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
        "worst_score": round(report.worst_score(), 4),
        "specificity": round(report.specificity_score(), 4),
        "ancestry_stratification": {
            a: round(v, 4) for a, v in report.ancestry_stratification().items()
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
    human_lines = [
        f"spacer {report.spacer} / PAM {report.pam}: {report.n_sites} site(s), "
        f"worst score {report.worst_score():.3f}, "
        f"specificity {report.specificity_score():.3f}{scorer_note}"
    ]
    for s in sites:
        mit = f"  mit={s['mit_score']}" if s["mit_score"] is not None else ""
        human_lines.append(
            f"  {s['locus']}  mm={s['mismatches']}  score={s['score']}{mit}  "
            f"{s['origin']}{' ' + str(s['causal_allele']) if s['causal_allele'] else ''}"
        )
    _emit(payload, as_json=as_json, human="\n".join(human_lines))


@app.command()
def verify(
    result: Annotated[
        Path, typer.Argument(help="A result JSON (ranked menu) with a provenance block.")
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
    """
    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.types.candidate import RankedMenu
    from alleleforge.types.prediction import trusted_deserialization_context

    if not result.is_file():
        _echo_err(f"error: result file not found: {result}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    try:
        # This is AlleleForge's own prior `af design` output, so re-read it through
        # the trusted context: a calibrated efficiency/bystander prediction keeps its
        # `calibrated=True` instead of being silently coerced to False on load.
        menu = RankedMenu.model_validate_json(
            result.read_text(), context=trusted_deserialization_context()
        )
    except ValueError as exc:
        _echo_err(f"error: not a valid result JSON: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc

    prov = menu.provenance
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

    checks: list[dict[str, str]] = []
    if cache_dir is not None:
        for ck in prov.models:
            if ck.sha256 is None:
                checks.append({"artifact": f"{ck.name}.{ck.version}", "status": "unpinned"})
                continue
            path = cache_dir / f"{ck.name}.{ck.version}.ckpt"
            if not path.is_file():
                checks.append({"artifact": f"{ck.name}.{ck.version}", "status": "not-cached"})
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual == ck.sha256:
                checks.append({"artifact": f"{ck.name}.{ck.version}", "status": "ok"})
            else:
                checks.append({"artifact": f"{ck.name}.{ck.version}", "status": "MISMATCH"})
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
                checks.append({"artifact": label, "status": "unpinned"})
                continue
            if ds.name not in DEFAULT_REGISTRY:
                # No known cache layout to locate the bytes; report rather than pass.
                checks.append({"artifact": label, "status": "unknown"})
                continue
            ds_path = DEFAULT_REGISTRY.cache_path(ds.name, cache_dir=cache_dir)
            if not ds_path.is_file():
                checks.append({"artifact": label, "status": "not-cached"})
                continue
            ds_actual = hashlib.sha256(ds_path.read_bytes()).hexdigest()
            if ds_actual == ds.sha256:
                checks.append({"artifact": label, "status": "ok"})
            else:
                checks.append({"artifact": label, "status": "MISMATCH"})
                problems.append(
                    f"dataset {label} hash mismatch: "
                    f"expected {ds.sha256[:12]}…, got {ds_actual[:12]}…"
                )

    payload: dict[str, Any] = {
        "seed": prov.seed,
        "alleleforge_version": prov.alleleforge_version,
        "n_models": len(prov.models),
        "n_datasets": len(prov.datasets),
        "checkpoint_checks": checks,
        "problems": problems,
        "verified": not problems,
    }
    human = [
        f"provenance: aforge {prov.alleleforge_version}, seed {prov.seed}, "
        f"{len(prov.models)} model(s), {len(prov.datasets)} dataset(s)"
    ]
    human += [f"  checkpoint {c['artifact']}: {c['status']}" for c in checks]
    if problems:
        human.append("PROBLEMS:")
        human += [f"  - {p}" for p in problems]
    else:
        human.append("verified: provenance is complete and consistent")
    _emit(payload, as_json=as_json, human="\n".join(human))
    if problems:
        raise typer.Exit(ExitCode.UNAVAILABLE)


data_app = typer.Typer(name="data", help="Inspect the dataset registry.", no_args_is_help=True)
app.add_typer(data_app)


@data_app.command("list")
def data_list(
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """List every registered dataset with its version and license."""
    from alleleforge.data.registry import DEFAULT_REGISTRY

    rows = [
        {
            "name": name,
            "version": d.version,
            "license": d.license,
            "redistributable": d.redistributable,
        }
        for name in DEFAULT_REGISTRY.names
        for d in (DEFAULT_REGISTRY.get(name),)
    ]
    human = "\n".join(
        f"{r['name']:12s} {r['version'] or '-':14s} {r['license'] or '-':18s} "
        f"{'vendored' if r['redistributable'] else 'fetch-on-consent'}"
        for r in rows
    )
    _emit({"datasets": rows}, as_json=as_json, human=human)


@data_app.command("show")
def data_show(
    name: Annotated[str, typer.Argument(help="Dataset name (see `aforge data list`).")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Show one dataset's full provenance descriptor."""
    from alleleforge.data.registry import DEFAULT_REGISTRY

    if name not in DEFAULT_REGISTRY:
        _echo_err(f"error: unknown dataset {name!r}; known: {DEFAULT_REGISTRY.names}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    d = DEFAULT_REGISTRY.get(name)
    payload = d.model_dump()
    human = "\n".join(f"{k}: {v}" for k, v in payload.items())
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
    from alleleforge.benchmark.tasks import TASKS

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
    from alleleforge.benchmark.baseline import build_baseline
    from alleleforge.benchmark.runner import run_benchmark
    from alleleforge.benchmark.splits import SplitIntegrityError, load_split
    from alleleforge.benchmark.tasks import get_task

    state: GlobalState = ctx.obj
    try:
        task_obj = get_task(task)
    except KeyError as exc:
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc
    try:
        split, dataset = load_split(task, version=split_version)
    except FileNotFoundError as exc:
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc
    except SplitIntegrityError as exc:
        _echo_err(f"error: split integrity check failed: {exc}")
        raise typer.Exit(ExitCode.MISSING_DATA) from exc

    baseline = build_baseline(task_obj, split, dataset)
    result = run_benchmark(baseline, task_obj, split=split, dataset=dataset, seed=state.seed)

    if out is not None:
        out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        typer.echo(f"wrote {out}")
    if as_json:
        typer.echo(result.model_dump_json(indent=2))
    elif out is None:
        # ECE is undefined (None) for a degenerate fold with no scorable
        # predictions; show "n/a" (as the leaderboard does) rather than crashing on
        # None.__format__.
        ece = result.metrics["ece"]
        ece_str = "n/a" if ece is None else f"{ece:.4f}"
        typer.echo(
            f"{result.task} @ {result.split_version}: {result.primary_metric}="
            f"{result.primary_value:.4f}, ece={ece_str} "
            f"(n={result.n_test}, model={result.model.name})"
        )


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

    from alleleforge.benchmark.leaderboard import Leaderboard, Submission, SubmissionError
    from alleleforge.benchmark.runner import BenchmarkResult

    by_model: dict[str, list[BenchmarkResult]] = {}
    for path in results:
        if not path.is_file():
            _echo_err(f"error: result file not found: {path}")
            raise typer.Exit(ExitCode.MISSING_DATA)
        try:
            result = BenchmarkResult.model_validate_json(path.read_text())
        except ValueError as exc:
            _echo_err(f"error: {path} is not a valid result JSON: {exc}")
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
        _echo_err(f"error: inadmissible submission: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc

    rendered = board.render_html() if fmt is LeaderboardFormat.html else board.render_markdown()
    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        typer.echo(f"wrote {out}")
    else:
        typer.echo(rendered)


if __name__ == "__main__":  # pragma: no cover
    app()
