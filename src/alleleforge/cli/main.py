"""The ``aforge`` command-line interface (Phase 12).

A thin, reproducible, config-driven shell over the library — **no business logic
lives here**. Every command resolves its inputs, calls the same library
functions the Python API exposes, and can emit machine-readable JSON. Runs are
reproducible from the echoed config plus the global seed, and a provenance
sidecar is written next to any file output.

Subcommands:

* ``resolve`` — normalize any input form and show the variant + consequence.
* ``design`` — variant to a ranked, multi-chemistry menu (the headline command).
* ``offtarget`` — standalone population/haplotype-aware off-target for a spacer.
* ``data`` — inspect the dataset registry (versions, licenses, provenance).
* ``bench`` — run CRISPR-Bench tasks (wired in Phase 14).

Exit codes are meaningful and distinct: ``0`` success, ``2`` usage/input error
(Typer default), ``3`` missing data, ``4`` an unavailable model or feature.
"""

from __future__ import annotations

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


def _load_reference(fasta: Path | None) -> Any:
    """Load a :class:`ReferenceGenome` from a FASTA, or exit ``MISSING_DATA``."""
    if fasta is None:
        _echo_err("error: --reference-fasta is required for this command")
        raise typer.Exit(ExitCode.MISSING_DATA)
    if not fasta.is_file():
        _echo_err(f"error: reference FASTA not found: {fasta}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    from alleleforge.genome.reference import ReferenceGenome

    return ReferenceGenome(fasta, build="hg38")


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
    reference = _load_reference(reference_fasta) if reference_fasta is not None else None
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
    except ValueError as exc:
        _echo_err(f"error: --weights must be four numbers: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc
    return RankingWeights(efficiency=eff, cleanliness=clean, safety=safe, simplicity=simple)


def _load_config(path: Path | None) -> dict[str, Any]:
    """Load a run-config TOML, or exit ``MISSING_DATA`` if it is absent."""
    if path is None:
        return {}
    if not path.is_file():
        _echo_err(f"error: config file not found: {path}")
        raise typer.Exit(ExitCode.MISSING_DATA)
    with path.open("rb") as fh:
        return tomllib.load(fh)


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

    reference = _load_reference(reference_fasta)
    settings = Settings(seed=state.seed)
    try:
        resolved = resolve_variant(variant, build=state.reference_build, reference=reference)
        menu = run_design(
            resolved,
            reference=reference,
            intent=edit_intent,
            chemistries=chemistries,
            weights=weights_obj,
            populations=pops,
            run_offtarget=not no_offtarget,
            max_candidates_per_chemistry=max_per_chemistry,
            settings=settings,
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
            sidecar.write_text(menu.provenance.model_dump_json(indent=2))
        typer.echo(f"wrote {out}" + (f" and {sidecar}" if menu.provenance else ""))
    elif fmt in (OutputFormat.json, OutputFormat.tsv):
        typer.echo(rendered.decode())
    else:
        _echo_err(f"error: --format {fmt.value} requires --out")
        raise typer.Exit(ExitCode.USAGE)

    if as_json and out is not None:
        typer.echo(menu.model_dump_json(indent=2))


@app.command()
def offtarget(
    ctx: typer.Context,
    spacer: Annotated[str, typer.Argument(help="The on-target spacer (5'->3').")],
    reference_fasta: Annotated[
        Path | None, typer.Option(help="Reference FASTA (required).")
    ] = None,
    pam: Annotated[str, typer.Option(help="PAM pattern (IUPAC).")] = "NGG",
    mismatches: Annotated[int, typer.Option(help="Max mismatches.")] = 4,
    populations: Annotated[
        str | None, typer.Option(help="Comma-separated ancestry labels to stratify by.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Run population/haplotype-aware off-target search for a spacer."""
    from alleleforge.offtarget.engine import search
    from alleleforge.types.guide import PAM

    reference = _load_reference(reference_fasta)
    pops = [p.strip() for p in populations.split(",")] if populations else None
    try:
        report = search(
            spacer, PAM(pattern=pam), reference=reference, mismatches=mismatches, populations=pops
        )
    except ValueError as exc:
        _echo_err(f"error: {exc}")
        raise typer.Exit(ExitCode.USAGE) from exc

    sites = [
        {
            "locus": str(s.locus),
            "mismatches": s.mismatches,
            "score": round(s.score, 4),
            "method": s.score_method.value,
            "origin": s.origin.value,
            "causal_allele": s.causal_allele,
            "populations": list(s.populations),
        }
        for s in report.sites
    ]
    payload = {
        "spacer": report.spacer,
        "pam": report.pam,
        "n_sites": report.n_sites,
        "worst_score": round(report.worst_score(), 4),
        "ancestry_stratification": {
            a: round(v, 4) for a, v in report.ancestry_stratification().items()
        },
        "sites": sites,
    }
    human_lines = [
        f"spacer {report.spacer} / PAM {report.pam}: {report.n_sites} site(s), "
        f"worst score {report.worst_score():.3f}"
    ]
    for s in sites:
        human_lines.append(
            f"  {s['locus']}  mm={s['mismatches']}  score={s['score']}  "
            f"{s['origin']}{' ' + str(s['causal_allele']) if s['causal_allele'] else ''}"
        )
    _emit(payload, as_json=as_json, human="\n".join(human_lines))


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


@app.command()
def bench() -> None:
    """Run CRISPR-Bench tasks (wired in Phase 14)."""
    _echo_err("CRISPR-Bench is not yet available; it arrives in Phase 14.")
    raise typer.Exit(ExitCode.UNAVAILABLE)


if __name__ == "__main__":  # pragma: no cover
    app()
