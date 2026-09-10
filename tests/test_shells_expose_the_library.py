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

import ast
import inspect
import re
from collections.abc import Callable
from pathlib import Path

from alleleforge.design.designer import design
from alleleforge.web.api.models import DesignRequest

_ROOT = Path(__file__).resolve().parents[1]

#: Parameters of `design()` that a shell legitimately does not expose, with the reason.
_NOT_IN_CLI: dict[str, str] = {
    "inp": "the positional variant argument",
    "timestamp": "test-only hook for a reproducible provenance stamp",
    "prime_outcome_predictor": "no trained prime-outcome model is registered to select",
}

_NOT_IN_WEB: dict[str, str] = {
    "inp": "the request's `variant` field",
    "reference": "the server's own reference genome, configured at startup",
    "settings": "server-side; a client does not choose the server's configuration",
    "timestamp": "test-only hook for a reproducible provenance stamp",
    # File-backed, exactly like `gnomad` below — the CLI supplies them with
    # `--clinvar`/`--dbsnp`, and over HTTP a client-supplied server path would be a
    # file-read primitive. The refusal says so and names the coordinate form.
    "clinvar": "file-backed lookup; a client-supplied path on a server reads server files",
    "dbsnp": "file-backed lookup; see `clinvar`",
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
    # A scorer *object* is not expressible in JSON — but the capability behind it is,
    # and saying only the first half is how these four stayed unreachable while
    # `aforge design --trained-efficiency` reached them with a boolean. The request
    # asks for the trained adapter by name; the operator gates the download.
    "cas9_efficiency_scorer": "a Python object; the trained adapter it selects is asked "
    "for by the request field `trained_efficiency`, gated by ALLELEFORGE_TRAINED_MODELS",
    "cas9_outcome_predictor": "a Python object; asked for by `trained_outcome`",
    "base_outcome_predictor": "a Python object; asked for by `trained_base_outcome`",
    "prime_efficiency_scorer": "a Python object; asked for by `trained_prime`",
    "prime_outcome_predictor": "a Python object, and nothing trained ships to select, "
    "so unlike its four siblings there is no capability behind it to expose",
    # Reuse is the operator's call, not the client's: the store and the index live
    # on the server's disk, and a client asking for either would be spending the
    # operator's resources on its own request.
    "offtarget_cache": "server-side resource: the operator enables reuse with "
    "ALLELEFORGE_OFFTARGET_CACHE or create_app(offtarget_cache=...), because the store "
    "is on the server's disk and a request asking for it spends the operator's",
    "genome_index": "server-side resource; ALLELEFORGE_GENOME_INDEX, see `offtarget_cache`",
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


def _bound_arguments(callee: str, target: Callable[..., object]) -> set[str]:
    """Return the parameters of ``target`` the CLI's call to ``callee`` supplies.

    Bound the way Python binds them, from the AST, so a **positional** argument counts.
    The regex form this replaced matched `name=` only, which is why `search(spacer,
    PAM(...), ...)` looked as though the CLI never supplied a spacer or a PAM — and both
    then sat in an allowance list with a reason written to explain the phantom gap.

    That is the third time in this project a false positive in a reachability check meant
    the *rule* was stated wrong rather than needing an exception.
    """
    source = (_ROOT / "src" / "alleleforge" / "cli" / "main.py").read_text()
    names = [n for n, _ in inspect.signature(target).parameters.items()]
    supplied: set[str] = set()
    found = False
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        # Only an unqualified call. `re.search(pattern, text)` is also a call named
        # "search", and binding *its* positional arguments onto this signature would
        # silently mark parameters as supplied that nothing supplies.
        if not isinstance(node.func, ast.Name) or node.func.id != callee:
            continue
        found = True
        supplied |= {names[i] for i in range(len(node.args)) if i < len(names)}
        supplied |= {kw.arg for kw in node.keywords if kw.arg is not None}
    assert found, f"no call to {callee}() found in the CLI — this check would be vacuous"
    return supplied


def _cli_forwards() -> set[str]:
    """Return the `design()` inputs the CLI supplies, at either of the two call sites.

    Two, not one. Several of `design()`'s inputs are read only during resolution, and
    the CLI resolves the variant itself before handing `design()` the result — so
    `resolve_variant(..., effect=...)` is exactly as much "the user reached it from the
    command line" as passing it to `design()` would be.

    Counting only the `design()` call made this file disagree with
    `test_the_readiness_assessment_states_the_real_reachability`, which counts both: one
    said `effect` was unreachable and the other said it was, on the day `--vep` shipped.
    Two answers to one question is how a reader gets the wrong one.
    """
    source = (_ROOT / "src" / "alleleforge" / "cli" / "main.py").read_text()
    supplied: set[str] = set()
    for pattern in (
        r"menu = run_design\(\n(?:.*\n)*?\s{8}\)",
        r"resolved = resolve_variant\(\n(?:.*\n)*?\s{8}\)",
    ):
        call = re.search(pattern, source)
        assert call, f"could not find {pattern!r} in the CLI — this check would be vacuous"
        supplied |= set(re.findall(r"^\s+(\w+)=", call.group(0), re.M))
    return supplied


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


def _cited(reason: str) -> set[str]:
    """Return the identifiers a reason names in backticks."""
    return {tok for tok in re.findall(r"`([a-z][a-z0-9_]{2,})`", reason)}


def test_an_allowance_reason_names_things_that_exist() -> None:
    """A reason is a claim, and a claim in a comment is the kind that goes stale.

    Every entry here excuses a gap by naming what covers it instead — "asked for by the
    request field `trained_efficiency`", "exposed under `max_per_chemistry`". Those names
    were checked by nobody, and `build` sat here reading "the request's `build` field"
    while `DesignRequest` had no such field and the API resolved every request against a
    hardcoded assembly. The exclusion was the whole defect and the list looked maintained.

    So: every identifier an allowance cites must resolve to a request field, a `design()`
    parameter, a `create_app()` argument, or another allowance in the same dict.
    """
    import inspect as _inspect

    from alleleforge.web.api.app import create_app

    known = (
        set(DesignRequest.model_fields)
        | _design_parameters()
        | set(_inspect.signature(create_app).parameters)
    )
    unknown = {
        f"{dict_name}[{param!r}]": sorted(_cited(reason) - known - set(allowances))
        for dict_name, allowances in (("_NOT_IN_CLI", _NOT_IN_CLI), ("_NOT_IN_WEB", _NOT_IN_WEB))
        for param, reason in allowances.items()
        if _cited(reason) - known - set(allowances)
    }
    assert not unknown, (
        f"these allowance reasons name something that does not exist: {unknown}. Either "
        "the name is wrong or the thing it points a reader to is gone — and in both "
        "cases the gap is no longer excused."
    )
    # A floor: a regex that matches nothing would pass every assertion above.
    assert _cited(_NOT_IN_WEB["max_candidates_per_chemistry"]) == {"max_per_chemistry"}


def test_an_allowance_reason_names_a_variable_the_server_reads() -> None:
    """The other half of a reason: the environment variable it points an operator at."""
    source = (_ROOT / "src" / "alleleforge" / "web" / "api" / "app.py").read_text()
    cited = {
        var
        for reason in _NOT_IN_WEB.values()
        for var in re.findall(r"\bALLELEFORGE_[A-Z_]+\b", reason)
    }
    assert cited, "no environment variable cited — this check would be vacuous"
    unread = sorted(var for var in cited if f'os.environ.get("{var}"' not in source)
    assert not unread, f"an allowance tells an operator to set {unread}, and the app never reads it"


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


def test_the_search_and_report_allowances_do_not_outlive_their_gaps() -> None:
    """The same rule, on the two entry points that only had the weaker version.

    The strong form ("excused *and* offered" is a false record) was written for
    `design()` and never mirrored, and by the time it was, three entries had gone
    stale in the direction that matters. `_SEARCH_NOT_IN_WEB["scorer"]` read "not yet
    exposed; the CLI's `--scorer` has no web counterpart" while `OffTargetRequest`
    had the field, and `_SEARCH_NOT_IN_CLI` told a reader the CLI "has no session to
    hold" a cross-run cache two rounds after `aforge offtarget --cache` shipped.

    A weaker sibling check makes this worse rather than neutral: the list *is*
    checked, so it reads as maintained, and set subtraction can never see an entry
    that is both excused and offered because such an entry changes no result.
    """
    from alleleforge.report.builder import build_report
    from alleleforge.web.api.models import OffTargetRequest

    offered = {
        "_SEARCH_NOT_IN_CLI": set(_SEARCH_NOT_IN_CLI) & _cli_search_forwards(),
        "_SEARCH_NOT_IN_WEB": set(_SEARCH_NOT_IN_WEB) & set(OffTargetRequest.model_fields),
        "_REPORT_NOT_IN_CLI": set(_REPORT_NOT_IN_CLI) & _cli_report_forwards(),
        # `scheme` is spelled `vector_scheme` on the request; the alias is the
        # positive test's, and reusing it keeps one answer to "does the web offer it".
        "_REPORT_NOT_IN_WEB": {
            name
            for name in _REPORT_NOT_IN_WEB
            if {"scheme": "vector_scheme"}.get(name, name) in set(DesignRequest.model_fields)
        },
    }
    stale = {name: sorted(hits) for name, hits in offered.items() if hits}
    assert not stale, (
        f"these allowances excuse something the shell already offers: {stale}. Drop the "
        "entry — a reason recorded beside a capability that exists sends a reader away "
        "from it."
    )
    # A floor, since every assertion above is trivially satisfied by empty sets.
    assert build_report is not None
    assert len(_SEARCH_NOT_IN_WEB) > 3, _SEARCH_NOT_IN_WEB


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
    "use_fm_index": "an override for a heuristic that auto-engages past 1 Mb; the "
    "default is the documented behaviour",
}

_SEARCH_NOT_IN_WEB: dict[str, str] = {
    "reference": "the server's own reference genome, configured at startup",
    "regions": "the request's `offtarget_regions` field",
    "gnomad": "file-backed input; a client-supplied path on a server reads server files",
    "haplotypes": "file-backed input; see `gnomad`",
    "patient_vcf": "file-backed input; see `gnomad`",
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
    from alleleforge.offtarget.engine import search

    return _bound_arguments("search", search)


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
    "title": "cosmetic; the default names the tool, and no one has asked to retitle it",
    "top_alleles": "not yet exposed; --render-candidates caps rows, not alleles per row",
    "with_oligos": "always on; a report that withholds the reagents helps no one",
}

_REPORT_NOT_IN_WEB: dict[str, str] = {
    "menu": "built by the server from the design it just ran; not a request field",
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
    from alleleforge.report.builder import build_report

    return _bound_arguments("build_report", build_report)


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


def test_the_readme_states_the_number_of_exceptions_this_file_records() -> None:
    """The README makes an absolute claim; this is what keeps it from becoming false.

    "Every `design()` capability is reachable from the CLI" is true only because none of
    the parameters below is a capability the command line cannot reach — one adapter
    needing an undeclared library, an injection point with nothing trained to select,
    the positional argument and a test hook. That is an argument about four specific
    entries, so the README states the count and points here, and a fifth entry makes
    the sentence a promise nobody checked.

    Two entries left this list when `--clinvar` and `--dbsnp` were added: the excuse
    had said the lookups were "Protocols with no shipped implementation", and
    `ClinVarDB`/`DbSnpDB` had shipped all along.
    """
    words = {
        1: "One",
        2: "Two",
        3: "Three",
        4: "Four",
        5: "Five",
        6: "Six",
        7: "Seven",
        8: "Eight",
    }
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    stated = f"{words[len(_NOT_IN_CLI)]} of its parameters are not passed by any command"
    assert stated in readme, (
        f"the README should say {stated!r}; this file records {len(_NOT_IN_CLI)} "
        f"exceptions ({sorted(_NOT_IN_CLI)}) and the README's absolute claim depends on "
        "each of them not being a capability"
    )
    assert "tests/test_shells_expose_the_library.py" in readme, (
        "the README should name the file that holds the list and its reasons"
    )


def test_the_cli_allowances_are_exactly_the_unsupplied_parameters() -> None:
    """No slack in either direction: every excuse real, every gap excused."""
    unsupplied = _design_parameters() - _cli_forwards()
    assert set(_NOT_IN_CLI) == unsupplied, (
        f"excused but supplied: {sorted(set(_NOT_IN_CLI) - unsupplied)}; "
        f"unsupplied but unexcused: {sorted(unsupplied - set(_NOT_IN_CLI))}"
    )
