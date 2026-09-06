"""The CLI and the web API must not quietly withhold what `design()` offers.

`design()` is the one entry point behind all three audiences ("library is truth; CLI
and web are thin shells"). A parameter it accepts and a shell does not forward is a
capability that exists and cannot be reached, and this has now happened three times:
the SpCas9-NG and SpRY fallbacks reachable only from `design_cas9`, the trained
prime-efficiency model reachable only from Python while its Cas9 and base-editor
siblings had CLI flags, and — in the very round that fixed the first — the new flags
added to the CLI and not to the web API.

Some parameters genuinely belong to one shell only, and each is recorded with the
reason. That is the point: the gap has to be a decision, not an oversight.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from alleleforge.design.designer import design
from alleleforge.web.api.models import DesignRequest

_ROOT = Path(__file__).resolve().parents[1]

#: Parameters of `design()` that a shell legitimately does not expose, with the reason.
_NOT_IN_CLI: dict[str, str] = {
    "inp": "the positional variant argument",
    "settings": "assembled by the CLI from --config, the env, and --seed",
    "timestamp": "test-only hook for a reproducible provenance stamp",
    "build": "supplied by the global --reference-build option",
    "clinvar": "the CLI resolves the variant itself before calling design()",
    "dbsnp": "the CLI resolves the variant itself before calling design()",
    "hgvs": "the CLI resolves the variant itself before calling design()",
    "effect": "the CLI resolves the variant itself before calling design()",
    "prime_outcome_predictor": "no trained prime-outcome model is registered to select",
}

_NOT_IN_WEB: dict[str, str] = {
    "inp": "the request's `variant` field",
    "reference": "the server's own reference genome, configured at startup",
    "settings": "server-side; a client does not choose the server's configuration",
    "timestamp": "test-only hook for a reproducible provenance stamp",
    "build": "the request's `build` field",
    "clinvar": "resolved server-side from the request's variant string",
    "dbsnp": "resolved server-side from the request's variant string",
    "hgvs": "resolved server-side from the request's variant string",
    "effect": "resolved server-side from the request's variant string",
    # The deliberate web exclusion: a client-supplied filesystem path on a server is a
    # file-read primitive. These stay library/CLI-only by design.
    "gnomad": "file-backed input; a client-supplied path on a server reads server files",
    "haplotypes": "file-backed input; see `gnomad`",
    "patient_vcf": "file-backed input; see `gnomad`",
    "encode_tracks": "file-backed input; see `gnomad`",
    "chromatin_track": "names a track inside a file-backed input the web API does not accept",
    "max_candidates_per_chemistry": "exposed under the request field `max_per_chemistry`",
    "cas9_efficiency_scorer": "a Python object, not expressible in JSON",
    "cas9_outcome_predictor": "a Python object, not expressible in JSON",
    "base_outcome_predictor": "a Python object, not expressible in JSON",
    "prime_efficiency_scorer": "a Python object, not expressible in JSON",
    "prime_outcome_predictor": "a Python object, not expressible in JSON",
}


def _design_parameters() -> set[str]:
    return {
        name
        for name, param in inspect.signature(design).parameters.items()
        if param.kind is not param.VAR_KEYWORD
    }


def _cli_forwards() -> set[str]:
    """Return the keyword arguments the CLI's `design` command passes to `design()`."""
    source = (_ROOT / "src" / "alleleforge" / "cli" / "main.py").read_text()
    call = re.search(r"menu = run_design\(\n(?:.*\n)*?\s{8}\)", source)
    assert call, "could not find the CLI's design() call — this check would be vacuous"
    return set(re.findall(r"^\s+(\w+)=", call.group(0), re.M))


def test_the_cli_forwards_every_design_parameter_or_says_why() -> None:
    missing = sorted(_design_parameters() - _cli_forwards() - set(_NOT_IN_CLI))
    assert not missing, (
        f"design() accepts these and the CLI never forwards them: {missing}. Add the "
        "option, or record it in _NOT_IN_CLI with the reason."
    )


def test_the_web_api_exposes_every_design_parameter_or_says_why() -> None:
    missing = sorted(_design_parameters() - set(DesignRequest.model_fields) - set(_NOT_IN_WEB))
    assert not missing, (
        f"design() accepts these and DesignRequest cannot request them: {missing}. Add "
        "the field, or record it in _NOT_IN_WEB with the reason."
    )


def test_the_recorded_exceptions_are_real_parameters() -> None:
    """An allowance must not outlive the parameter it excuses."""
    known = _design_parameters()
    stale = sorted((set(_NOT_IN_CLI) | set(_NOT_IN_WEB)) - known)
    assert not stale, f"exceptions recorded for parameters design() no longer takes: {stale}"


#: Options that belong to `aforge design` alone, with the reason. `batch` shapes its
#: output through `--output-dir`, `--manifest` and `--summary-tsv` instead, so the
#: single-result rendering options have no meaning there.
_DESIGN_ONLY_OPTIONS: dict[str, str] = {
    "--format": "batch writes a directory of results, not one rendered document",
    "--out": "batch uses --output-dir and --manifest",
    "--render-candidates": "caps a single rendered report; batch renders none",
}


def _command_options(command: str) -> set[str]:
    """Return the long options a CLI subcommand accepts, from the live click tree."""
    import typer

    from alleleforge.cli.main import app

    # Duck-typed on `.commands`/`.params`, not `isinstance(…, click.Group)`: a
    # TyperCommand is not an instance of the click classes visible here, which is how
    # an earlier version of this check (R138/R144) reported the whole CLI as five
    # options. I wrote the isinstance assert anyway and it failed immediately.
    root = typer.main.get_command(app)
    sub = root.commands[command]  # type: ignore[attr-defined]
    assert sub.params, f"no options found for {command!r} — this check would be vacuous"
    return {opt for param in sub.params for opt in param.opts if opt.startswith("--")}


def test_the_cohort_command_offers_every_design_option() -> None:
    """A cohort is where a trained model or a PAM fallback matters most.

    `aforge batch` is the scale path — the run someone leaves going over a whole VCF —
    and it could not select a trained model or a PAM-flexible fallback by any means,
    config file included, while `aforge design` could. `--chemistry` and
    `--cell-context` were config-file-only there, which is the same gap in a quieter
    form: honoured if you know to write TOML, invisible from `--help`.
    """
    design_only = _command_options("design") - _command_options("batch")
    unexplained = sorted(design_only - set(_DESIGN_ONLY_OPTIONS) - {"--help"})
    assert not unexplained, (
        f"`aforge design` accepts these and `aforge batch` does not: {unexplained}. Add "
        "them, or record them in _DESIGN_ONLY_OPTIONS with the reason."
    )


def test_the_design_only_allowances_are_real_options() -> None:
    stale = sorted(set(_DESIGN_ONLY_OPTIONS) - _command_options("design"))
    assert not stale, f"allowances recorded for options `design` no longer has: {stale}"
