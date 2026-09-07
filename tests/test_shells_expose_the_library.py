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
    "effect": "asked for by the request field `annotate_consequence` and built "
    "server-side; the predictor itself is an operator-configured object",
    # The deliberate web exclusion: a client-supplied filesystem path on a server is a
    # file-read primitive. These stay library/CLI-only by design.
    "gnomad": "file-backed input; a client-supplied path on a server reads server files",
    "haplotypes": "file-backed input; see `gnomad`",
    "patient_vcf": "file-backed input; see `gnomad`",
    "encode_tracks": "file-backed input; see `gnomad`",
    "max_candidates_per_chemistry": "exposed under the request field `max_per_chemistry`",
    "cas9_efficiency_scorer": "a Python object, not expressible in JSON",
    "cas9_outcome_predictor": "a Python object, not expressible in JSON",
    "base_outcome_predictor": "a Python object, not expressible in JSON",
    "prime_efficiency_scorer": "a Python object, not expressible in JSON",
    "prime_outcome_predictor": "a Python object, not expressible in JSON",
    # Reuse is the operator's call, not the client's: the store and the index live
    # on the server's disk, and a client asking for either would be spending the
    # operator's resources on its own request.
    "offtarget_cache": "server-side resource; an operator enables reuse, not a request",
    "genome_index": "server-side resource; see `offtarget_cache`",
}


def _design_parameters() -> set[str]:
    params = {
        name
        for name, param in inspect.signature(design).parameters.items()
        if param.kind is not param.VAR_KEYWORD
    }
    # Every check here asks "does a shell expose all of these", which an empty set
    # satisfies trivially. The floor makes an introspection failure loud instead.
    assert len(params) > 15, f"design() introspection returned {params}"
    return params


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


def test_an_allowance_does_not_outlive_the_gap_it_excuses() -> None:
    """The stronger form: an excuse for something the shell now offers is a false record.

    Set subtraction hides this — an entry that is both exposed and excused changes no
    result — so `chromatin_track` sat here reading "the web API does not accept" it for
    every round after the web API started accepting it. This list is read by people
    deciding what is missing, and a wrong entry sends them away from a capability that
    exists.
    """
    exposed = sorted(set(_NOT_IN_WEB) & set(DesignRequest.model_fields))
    assert not exposed, (
        f"DesignRequest exposes {exposed}, and _NOT_IN_WEB still records a reason it "
        "cannot. Drop the entry."
    )
    forwarded = sorted(set(_NOT_IN_CLI) & _cli_forwards())
    assert not forwarded, (
        f"the CLI forwards {forwarded}, and _NOT_IN_CLI still records a reason it does "
        "not. Drop the entry."
    )


#: Options that belong to `aforge design` alone, with the reason. `batch` shapes its
#: output through `--output-dir`, `--manifest` and `--summary-tsv` instead, so the
#: single-result rendering options have no meaning there.
_DESIGN_ONLY_OPTIONS: dict[str, str] = {
    "--format": "batch writes a directory of results, not one rendered document",
    "--out": "batch uses --output-dir and --manifest",
    "--render-candidates": "caps a single rendered report; batch renders none",
    "--vector-scheme": "picks the enzyme the *report's* oligo screen uses; batch writes "
    "raw ranked menus and builds no oligos at all, so there is nothing to screen",
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


#: Parameters of `search()` a shell legitimately does not expose, with the reason.
#: The off-target engine is the project's differentiator and had no parity check at
#: all — only `design()` did — which is how three R4-era capabilities and a whole
#: nuclease's scorer came to be library-only.
_SEARCH_NOT_IN_CLI: dict[str, str] = {
    "spacer": "the positional argument",
    "pam": "the `--pam` option, passed positionally as a PAM object",
    "reference": "built by the CLI from --reference-fasta",
    "cache": "a cross-run cache object; the CLI has no session to hold one",
    "genome_index": "a prebuilt whole-genome FM-index object; needs a path option to "
    "select and is not yet exposed (R4 scale path, library-only)",
    "use_fm_index": "an override for a heuristic that auto-engages past 1 Mb; the "
    "default is the documented behaviour",
}

_SEARCH_NOT_IN_WEB: dict[str, str] = {
    "spacer": "the request's `spacer` field",
    "pam": "the request's `pam` field",
    "reference": "the server's own reference genome, configured at startup",
    "regions": "the request's `offtarget_regions` field",
    "gnomad": "file-backed input; a client-supplied path on a server reads server files",
    "haplotypes": "file-backed input; see `gnomad`",
    "patient_vcf": "file-backed input; see `gnomad`",
    "scorer": "not yet exposed; the CLI's `--scorer` has no web counterpart",
    "cache": "server-side concern, not a client's to choose",
    "genome_index": "server-side concern; see `cache`",
    "use_fm_index": "server-side performance heuristic, not a client's to choose",
}


def _search_parameters() -> set[str]:
    import inspect

    from alleleforge.offtarget.engine import search

    params = {
        name
        for name, param in inspect.signature(search).parameters.items()
        if param.kind is not param.VAR_KEYWORD
    }
    assert len(params) > 10, f"search() introspection returned {params}"
    return params


def _cli_search_forwards() -> set[str]:
    source = (_ROOT / "src" / "alleleforge" / "cli" / "main.py").read_text()
    call = re.search(r"report = search\(\n(?:.*\n)*?\s{8}\)", source)
    assert call, "could not find the CLI's search() call — this check would be vacuous"
    return set(re.findall(r"^\s+(\w+)=", call.group(0), re.M))


def test_the_cli_forwards_every_search_parameter_or_says_why() -> None:
    missing = sorted(_search_parameters() - _cli_search_forwards() - set(_SEARCH_NOT_IN_CLI))
    assert not missing, (
        f"search() accepts these and `aforge offtarget` never forwards them: {missing}. "
        "Add the option, or record it in _SEARCH_NOT_IN_CLI with the reason."
    )


def test_the_web_api_exposes_every_search_parameter_or_says_why() -> None:
    from alleleforge.web.api.models import OffTargetRequest

    missing = sorted(
        _search_parameters() - set(OffTargetRequest.model_fields) - set(_SEARCH_NOT_IN_WEB)
    )
    assert not missing, (
        f"search() accepts these and OffTargetRequest cannot request them: {missing}. "
        "Add the field, or record it in _SEARCH_NOT_IN_WEB with the reason."
    )


def test_the_search_allowances_are_real_parameters() -> None:
    known = _search_parameters()
    stale = sorted((set(_SEARCH_NOT_IN_CLI) | set(_SEARCH_NOT_IN_WEB)) - known)
    assert not stale, f"allowances recorded for parameters search() no longer takes: {stale}"


#: Parameters of `build_report()` a shell legitimately does not expose, with the
#: reason. The third entry point behind all three audiences, and the last one with no
#: parity check: `design()` decides what the candidates are, `build_report()` decides
#: what the document says about them. That is where `scheme` — which picks the Type IIS
#: enzyme every insert is screened against, and so decides whether a pX330 user is told
#: their insert is cloning-lethal — sat reachable from Python alone.
_REPORT_NOT_IN_CLI: dict[str, str] = {
    "menu": "the ranked menu the CLI just designed",
    "variant": "the variant the CLI was invoked on",
    "intent": "supplied by --intent",
    "title": "cosmetic; the default names the tool, and no one has asked to retitle it",
    "top_alleles": "not yet exposed; --render-candidates caps rows, not alleles per row",
    "with_oligos": "always on; a report that withholds the reagents helps no one",
}

_REPORT_NOT_IN_WEB: dict[str, str] = {
    "menu": "the ranked menu the server just designed",
    "variant": "the request's `variant` field",
    "intent": "the request's `intent` field",
    "title": "cosmetic; see the CLI note",
    "top_alleles": "not yet exposed; see the CLI note",
    "with_oligos": "always on; see the CLI note",
}


def _report_parameters() -> set[str]:
    from alleleforge.report.builder import build_report

    params = {
        name
        for name, param in inspect.signature(build_report).parameters.items()
        if param.kind is not param.VAR_KEYWORD
    }
    assert len(params) > 5, f"build_report() introspection returned {params}"
    return params


def _cli_report_forwards() -> set[str]:
    source = (_ROOT / "src" / "alleleforge" / "cli" / "main.py").read_text()
    call = re.search(r"report = build_report\(\n(?:.*\n)*?\s{4}\)", source)
    assert call, "could not find the CLI's build_report() call — this check would be vacuous"
    return set(re.findall(r"(\w+)=", call.group(0)))


def test_the_cli_forwards_every_report_parameter_or_says_why() -> None:
    missing = sorted(_report_parameters() - _cli_report_forwards() - set(_REPORT_NOT_IN_CLI))
    assert not missing, (
        f"build_report() accepts these and the CLI never forwards them: {missing}. Add "
        "the option, or record it in _REPORT_NOT_IN_CLI with the reason."
    )


def test_the_web_api_exposes_every_report_parameter_or_says_why() -> None:
    #: `scheme` is a named lookup over the scheme registry, so the request field is
    #: spelled `vector_scheme` — the vector is what the user knows they have.
    aliases = {"scheme": "vector_scheme"}
    fields = set(DesignRequest.model_fields)
    missing = sorted(
        name
        for name in _report_parameters() - set(_REPORT_NOT_IN_WEB)
        if aliases.get(name, name) not in fields
    )
    assert not missing, (
        f"build_report() accepts these and DesignRequest cannot request them: {missing}. "
        "Add the field, or record it in _REPORT_NOT_IN_WEB with the reason."
    )


def test_the_report_allowances_are_real_parameters() -> None:
    known = _report_parameters()
    stale = sorted((set(_REPORT_NOT_IN_CLI) | set(_REPORT_NOT_IN_WEB)) - known)
    assert not stale, f"allowances recorded for parameters build_report() no longer takes: {stale}"


def test_the_two_shells_offer_the_same_output_formats() -> None:
    """A format one shell can produce and the other cannot is a shell-only capability.

    `--format` offered `tsv` and the web `?format=` did not, so the audience that
    cannot open an HTML page — a pipeline — had nothing to read over HTTP; and
    `parquet` existed in neither, having been reachable from Python alone while the
    CLI reference documented it.
    """
    from alleleforge.cli.main import OutputFormat
    from alleleforge.web.api.app import DesignFormat

    cli = {member.value for member in OutputFormat}
    web = {member.value for member in DesignFormat}
    assert len(cli) > 3, cli
    assert cli == web, (
        f"only the CLI can produce {sorted(cli - web)} and only the web API "
        f"{sorted(web - cli)}; the same design should be obtainable in the same "
        "formats from either shell."
    )
