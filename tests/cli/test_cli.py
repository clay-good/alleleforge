"""End-to-end tests for the ``aforge`` Typer CLI (Phase 12)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge._version import __version__
from alleleforge.cli.main import ExitCode, app
from alleleforge.types.candidate import RankedMenu

DesignCmd = Callable[[Path, str], list[str]]


# --- global options ---------------------------------------------------------


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_help_lists_commands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "design" in result.output and "offtarget" in result.output


def test_no_args_shows_help(runner: CliRunner) -> None:
    # Typer's no_args_is_help prints usage and exits 2 (no command given).
    result = runner.invoke(app, [])
    assert result.exit_code == ExitCode.USAGE
    assert "Usage" in result.output or "design" in result.output


def test_global_cache_dir_is_honored(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `--cache-dir` was parsed but read nowhere, so the cache root the dataset
    # registry / model loader / FM-index / reference index all consume via the
    # get_settings() singleton stayed the XDG default — a user redirecting the cache
    # (CI, sandbox, read-only home) was silently sent elsewhere. It must be honored.
    import alleleforge.config as config

    custom = tmp_path / "cache"
    monkeypatch.setattr(config, "_SETTINGS", None)  # fresh singleton for this run
    monkeypatch.delenv("ALLELEFORGE_CACHE_DIR", raising=False)  # restored at teardown
    result = runner.invoke(app, ["--cache-dir", str(custom), "resolve", "chr2:100:A>G", "--json"])
    assert result.exit_code == 0
    assert str(config.get_settings().cache_dir) == str(custom)


# --- resolve ----------------------------------------------------------------


def test_resolve_coords_human(runner: CliRunner) -> None:
    result = runner.invoke(app, ["resolve", "chr2:100:A>G"])
    assert result.exit_code == 0
    assert "chr2:99:A>G" in result.output  # 1-based input -> 0-based internal
    assert "snv" in result.output


def test_resolve_json(runner: CliRunner) -> None:
    result = runner.invoke(app, ["resolve", "chr2:100:A>G", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["variant"] == "chr2:99:A>G"
    assert data["variant_class"] == "snv"
    assert data["source"] == "coordinates"


def test_resolve_bad_input_is_usage_error(runner: CliRunner) -> None:
    result = runner.invoke(app, ["resolve", "not-a-variant"])
    assert result.exit_code == ExitCode.USAGE


# --- design -----------------------------------------------------------------


def test_design_json_stdout(runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd) -> None:
    result = runner.invoke(app, design_cmd(prime_fasta, "json"))
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["disclaimer"]
    assert data["intent"] == "install"
    assert len(data["candidates"]) == 3
    assert data["candidates"][0]["chemistry"] == "prime"


def test_design_tsv_stdout(runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd) -> None:
    result = runner.invoke(app, design_cmd(prime_fasta, "tsv"))
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert lines[0].startswith("schema_version\trank\tchemistry")
    assert len(lines) == 4  # header + 3 candidates


def test_design_html_requires_out(
    runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd
) -> None:
    result = runner.invoke(app, design_cmd(prime_fasta, "html"))
    assert result.exit_code == ExitCode.USAGE


def test_design_writes_file_and_provenance_sidecar(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path, design_cmd: DesignCmd
) -> None:
    out = tmp_path / "report.html"
    result = runner.invoke(app, [*design_cmd(prime_fasta, "html"), "--out", str(out)])
    assert result.exit_code == 0
    assert out.is_file() and out.read_text().startswith("<!DOCTYPE html>")
    sidecar = out.with_suffix(".html.provenance.json")
    assert sidecar.is_file()
    assert json.loads(sidecar.read_text())["seed"] == 20240501


def test_design_pdf_to_file(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path, design_cmd: DesignCmd
) -> None:
    out = tmp_path / "report.pdf"
    result = runner.invoke(app, [*design_cmd(prime_fasta, "pdf"), "--out", str(out)])
    assert result.exit_code == 0
    assert out.read_bytes().startswith(b"%PDF-1.4")


def test_design_missing_reference_is_missing_data(runner: CliRunner) -> None:
    result = runner.invoke(app, ["design", "chr2:71:A>C", "--intent", "install"])
    assert result.exit_code == ExitCode.MISSING_DATA


def test_design_bad_intent_is_usage_error(runner: CliRunner, prime_fasta: Path) -> None:
    result = runner.invoke(
        app, ["design", "chr2:71:A>C", "--reference-fasta", str(prime_fasta), "--intent", "bogus"]
    )
    assert result.exit_code == ExitCode.USAGE


def test_design_chemistry_filter(runner: CliRunner, prime_fasta: Path) -> None:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--chemistry",
            "prime",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert {c["chemistry"] for c in data["candidates"]} <= {"prime"}


def test_design_weights_flag(runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd) -> None:
    result = runner.invoke(app, [*design_cmd(prime_fasta, "json"), "--weights", "0.5,0.2,0.2,0.1"])
    assert result.exit_code == 0


def test_design_bad_weights_is_usage_error(
    runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd
) -> None:
    result = runner.invoke(app, [*design_cmd(prime_fasta, "json"), "--weights", "0.5,0.2"])
    assert result.exit_code == ExitCode.USAGE


def test_design_config_toml(runner: CliRunner, prime_fasta: Path, tmp_path: Path) -> None:
    cfg = tmp_path / "run.toml"
    cfg.write_text('intent = "install"\nmax_per_chemistry = 2\n')
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--config",
            str(cfg),
            "--json",
        ],
    )
    assert result.exit_code == 0
    menu = json.loads(result.output)
    assert menu["intent"] == "install"
    # max_per_chemistry from the config must actually cap the menu, not be ignored.
    per_chem: dict[str, int] = {}
    for cand in menu["candidates"]:
        per_chem[cand["chemistry"]] = per_chem.get(cand["chemistry"], 0) + 1
    assert all(n <= 2 for n in per_chem.values())


def test_design_config_toml_governs_settings(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    # A config.toml Settings key (maf_threshold) must be honored, not ignored:
    # it flows into the resolved settings recorded in provenance.
    cfg = tmp_path / "run.toml"
    cfg.write_text('intent = "install"\nmaf_threshold = 0.05\n')
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--config",
            str(cfg),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    sidecar = out.with_suffix(".html.provenance.json")
    prov = json.loads(sidecar.read_text())
    assert prov["config_snapshot"]["settings"]["maf_threshold"] == 0.05


def test_design_config_honors_run_params(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    # Whitelisted run-params carried only in the config file must be honored, not
    # silently ignored: run_offtarget=false and cell_context flow into the run
    # (visible in the provenance snapshot). Before the fix both were dropped —
    # run_offtarget stayed True and cell_context stayed null.
    cfg = tmp_path / "run.toml"
    cfg.write_text('intent = "install"\nrun_offtarget = false\ncell_context = "HEK293T"\n')
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--config",
            str(cfg),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    prov = json.loads(out.with_suffix(".html.provenance.json").read_text())
    assert prov["config_snapshot"]["run_offtarget"] is False
    assert prov["config_snapshot"]["cell_context"] == "HEK293T"


def test_reference_build_is_honored(runner: CliRunner, prime_fasta: Path, tmp_path: Path) -> None:
    # The user's --reference build must label the reference (and provenance),
    # not a hard-coded hg38.
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "--reference",
            "mm39",
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    prov = json.loads(out.with_suffix(".html.provenance.json").read_text())
    assert prov["reference_build"] == "mm39"


def test_design_warns_on_unknown_config_key(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    # A typo'd config key is warned about (and ignored), not silently dropped.
    cfg = tmp_path / "run.toml"
    cfg.write_text('intent = "install"\nmaf_treshold = 0.05\n')  # note the typo
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--config",
            str(cfg),
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert "unknown config key" in result.output and "maf_treshold" in result.output


def test_design_reproducible_modulo_timestamp(
    runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd
) -> None:
    a = runner.invoke(app, design_cmd(prime_fasta, "json"))
    b = runner.invoke(app, design_cmd(prime_fasta, "json"))
    assert a.exit_code == b.exit_code == 0

    def _strip(text: str) -> dict[str, object]:
        data = json.loads(text)
        if data.get("provenance"):
            data["provenance"]["timestamp"] = "<ts>"
        return data

    assert _strip(a.output) == _strip(b.output)


def test_design_json_output_is_phase1_schema_valid(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    out = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--max-per-chemistry",
            "2",
            "--out",
            str(out),
            "--json",
        ],
    )
    assert result.exit_code == 0
    # with --out set, the trailing --json prints the menu, schema-valid (Phase 1).
    menu_json = result.output.split("\n", 1)[1]  # drop the "wrote ..." status line
    menu = RankedMenu.model_validate_json(menu_json)
    assert menu.candidates


# --- batch (cohort) ---------------------------------------------------------

OK_1 = "chr2:26:A>G"  # ABE-installable
OK_2 = "chr2:25:A>G"  # ABE-installable (also an in-window A)
BAD_REF = "chr2:26:C>G"  # asserts ref 'C' where the reference has 'A' -> hard error


def _write_list(tmp_path: Path, *variants: str) -> Path:
    path = tmp_path / "cohort.txt"
    path.write_text("# a cohort\n" + "\n".join(variants) + "\n")
    return path


def test_batch_variant_list_human(runner: CliRunner, cohort_fasta: Path, tmp_path: Path) -> None:
    listing = _write_list(tmp_path, OK_1, BAD_REF)
    result = runner.invoke(
        app,
        ["batch", str(listing), "--reference-fasta", str(cohort_fasta), "--intent", "install"],
    )
    assert result.exit_code == 0
    assert "2 item(s)" in result.output and "1 ok" in result.output and "1 failed" in result.output
    assert "base_abe" in result.output


def test_batch_human_line_shows_the_interval_not_a_bare_estimate(
    runner: CliRunner, cohort_fasta: Path, tmp_path: Path
) -> None:
    """The triage line is where a bare number gets taken at face value."""
    import re

    listing = _write_list(tmp_path, OK_1)
    result = runner.invoke(
        app,
        ["batch", str(listing), "--reference-fasta", str(cohort_fasta), "--intent", "install"],
    )
    assert result.exit_code == 0
    # `eff=0.61 [0.46,0.76]` — the estimate is never printed alone.
    assert re.search(r"eff=\d\.\d\d \[\d\.\d\d,\d\.\d\d\]", result.output), result.output

    payload = json.loads(
        runner.invoke(
            app,
            [
                "batch",
                str(listing),
                "--reference-fasta",
                str(cohort_fasta),
                "--intent",
                "install",
                "--json",
            ],
        ).output
    )
    row = payload["items"][0]
    for field in (
        "best_efficiency_low",
        "best_efficiency_high",
        "best_efficiency_in_distribution",
        "best_caveats",
    ):
        assert field in row, f"{field} missing from the machine-readable cohort row"
    assert row["best_efficiency_low"] <= row["best_efficiency"] <= row["best_efficiency_high"]


def test_batch_json(runner: CliRunner, cohort_fasta: Path, tmp_path: Path) -> None:
    listing = _write_list(tmp_path, OK_1, OK_2)
    result = runner.invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(cohort_fasta),
            "--intent",
            "install",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert (data["total"], data["succeeded"], data["failed"]) == (2, 2, 0)
    assert {it["item_id"] for it in data["items"]} == {OK_1, OK_2}
    assert data["provenance"]["seed"] == 20240501


def test_batch_summary_tsv(runner: CliRunner, cohort_fasta: Path, tmp_path: Path) -> None:
    listing = _write_list(tmp_path, OK_1, BAD_REF)
    out = tmp_path / "summary.tsv"
    result = runner.invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(cohort_fasta),
            "--intent",
            "install",
            "--summary-tsv",
            str(out),
        ],
    )
    assert result.exit_code == 0
    lines = out.read_text().strip().splitlines()
    header = lines[0].split("\t")
    assert header[:2] == ["item_id", "status"]
    assert "best_specificity" in header  # aggregate specificity surfaces in the cohort TSV
    assert len(lines) == 3  # header + 2 items
    assert any("error" not in line and "base_abe" in line for line in lines[1:])


def test_batch_manifest_resume(runner: CliRunner, cohort_fasta: Path, tmp_path: Path) -> None:
    listing = _write_list(tmp_path, OK_1, OK_2)
    manifest = tmp_path / "run.jsonl"
    argv = [
        "batch",
        str(listing),
        "--reference-fasta",
        str(cohort_fasta),
        "--intent",
        "install",
        "--manifest",
        str(manifest),
        "--json",
    ]
    first = runner.invoke(app, argv)
    assert json.loads(first.output)["succeeded"] == 2
    second = runner.invoke(app, argv)
    data = json.loads(second.output)
    assert (data["total"], data["skipped"]) == (0, 2)  # both already recorded -> skipped


def test_batch_output_dir_writes_menus(
    runner: CliRunner, cohort_fasta: Path, tmp_path: Path
) -> None:
    listing = _write_list(tmp_path, OK_1)
    menus = tmp_path / "menus"
    result = runner.invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(cohort_fasta),
            "--intent",
            "install",
            "--output-dir",
            str(menus),
        ],
    )
    assert result.exit_code == 0
    written = list(menus.glob("*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text())["candidates"]


def test_batch_honors_chemistry_and_cell_context_from_config(
    runner: CliRunner, cohort_fasta: Path, tmp_path: Path
) -> None:
    # `chemistry` and `cell_context` are whitelisted config keys (no typo warning), so
    # `batch` must honor them like `design`/`design_many`/the web `/api/batch` do —
    # otherwise a restriction the user set is silently ignored. OK_1 (chr2:26:A>G) makes
    # only base_abe, so restricting to prime must empty the menu, and cell_context must
    # land in each menu's provenance.
    listing = _write_list(tmp_path, OK_1)
    cfg = tmp_path / "batch.toml"
    cfg.write_text('cell_context = "HEK293T"\nchemistry = ["prime"]\n')
    menus = tmp_path / "menus"
    result = runner.invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(cohort_fasta),
            "--intent",
            "install",
            "--config",
            str(cfg),
            "--output-dir",
            str(menus),
        ],
    )
    assert result.exit_code == 0
    assert "unknown config key" not in result.output  # both keys are whitelisted
    written = list(menus.glob("*.json"))
    assert len(written) == 1
    menu = json.loads(written[0].read_text())
    # chemistry=["prime"] is honored: the base_abe-only variant yields no candidates.
    assert menu["candidates"] == []
    # cell_context is honored: it reaches the per-item menu provenance (was None before).
    assert menu["provenance"]["config_snapshot"]["cell_context"] == "HEK293T"


def test_batch_missing_input_is_missing_data(runner: CliRunner, cohort_fasta: Path) -> None:
    result = runner.invoke(
        app, ["batch", "/no/such/cohort.txt", "--reference-fasta", str(cohort_fasta)]
    )
    assert result.exit_code == ExitCode.MISSING_DATA


def test_batch_bad_intent_is_usage_error(
    runner: CliRunner, cohort_fasta: Path, tmp_path: Path
) -> None:
    listing = _write_list(tmp_path, OK_1)
    result = runner.invoke(
        app,
        ["batch", str(listing), "--reference-fasta", str(cohort_fasta), "--intent", "bogus"],
    )
    assert result.exit_code == ExitCode.USAGE


def test_batch_vcf_without_cyvcf2_is_unavailable(
    runner: CliRunner, cohort_fasta: Path, tmp_path: Path
) -> None:
    # A .vcf input routes through iter_vcf; absent cyvcf2 that surfaces as a clean
    # UNAVAILABLE exit, not a crash. (Skip if cyvcf2 happens to be installed.)
    try:
        import cyvcf2  # noqa: F401
    except ImportError:
        vcf = tmp_path / "cohort.vcf"
        vcf.write_text("##fileformat=VCFv4.2\n")
        result = runner.invoke(
            app, ["batch", str(vcf), "--reference-fasta", str(cohort_fasta), "--intent", "install"]
        )
        assert result.exit_code == ExitCode.UNAVAILABLE
        assert "cyvcf2" in result.output or "cyvcf2" in (result.stderr or "")
    else:  # pragma: no cover - only when cyvcf2 is installed
        import pytest

        pytest.skip("cyvcf2 is installed; the UNAVAILABLE branch is unreachable")


def test_batch_parallel_matches_sequential(
    runner: CliRunner, cohort_fasta: Path, tmp_path: Path
) -> None:
    # --max-workers > 1 opens a fresh reference per worker (the .fai built by the
    # initial load is reused); results match the sequential run.
    listing = _write_list(tmp_path, OK_1, OK_2)
    result = runner.invoke(
        app,
        [
            "batch",
            str(listing),
            "--reference-fasta",
            str(cohort_fasta),
            "--intent",
            "install",
            "--max-workers",
            "2",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert (data["total"], data["succeeded"], data["failed"]) == (2, 2, 0)


def test_batch_verbose_reports_to_stderr(
    runner: CliRunner, cohort_fasta: Path, tmp_path: Path
) -> None:
    listing = _write_list(tmp_path, OK_1)
    argv = ["-v", "batch", str(listing), "--reference-fasta", str(cohort_fasta), "--intent"]
    result = runner.invoke(app, [*argv, "install"])
    assert result.exit_code == 0
    assert "designed 1/1" in (result.stderr or result.output)


def test_batch_item_id_for_vcf_record() -> None:
    # The cyvcf2 fast path yields VcfRecords; their id is a clean coordinate string
    # (used for resume de-dup and the per-item output filename).
    from alleleforge.cli.main import _batch_item_id
    from alleleforge.variant.resolver import VcfRecord

    rec = VcfRecord(chrom="chr2", pos=26, ref="A", alt="G", rsid="rs1")
    assert _batch_item_id(rec) == "chr2:26:A>G"
    assert _batch_item_id("chr2:26:A>G") == "chr2:26:A>G"


# --- offtarget --------------------------------------------------------------


def test_offtarget_json(runner: CliRunner, nuclease_fasta: Path) -> None:
    result = runner.invoke(
        app,
        ["offtarget", "ACGTAACGTTACGTAACGTT", "--reference-fasta", str(nuclease_fasta), "--json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "n_sites" in data and "ancestry_stratification" in data
    assert data["spacer"] == "ACGTAACGTTACGTAACGTT"
    assert 0.0 < data["specificity"] <= 1.0  # aggregate genome-wide specificity
    # The honest effective matrix is surfaced, not just the nominal one, so an
    # all-approximation table is never mislabeled as published CFD on this surface.
    assert "effective_matrix" in data
    # Per-site JSON carries the full audit set, at parity with POST /api/offtarget:
    # the MIT score, bulge counts, population frequency/ancestries, and the per-site
    # matrix that reveals a fallback — not just CFD.
    assert data["sites"], "expected at least the on-target-adjacent site"
    site = data["sites"][0]
    audit_fields = (
        "mit_score",
        "dna_bulges",
        "rna_bulges",
        "frequency",
        "ancestries",
        "score_matrix",
    )
    for field in audit_fields:
        assert field in site
    assert site["mit_score"] == 1.0  # ungapped 20-nt perfect match -> recorded, not dropped


def test_offtarget_tuning_knobs_are_honored(runner: CliRunner, nuclease_fasta: Path) -> None:
    # The engine's bulge budget and score thresholds are now CLI options, plumbed
    # through to search(). Raising the thresholds and disallowing bulges can only
    # remove nominations, never add — a fixture-independent check they are honored.
    spacer = "ACGTAACGTTACGTAACGTT"
    base = runner.invoke(
        app, ["offtarget", spacer, "--reference-fasta", str(nuclease_fasta), "--json"]
    )
    strict = runner.invoke(
        app,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(nuclease_fasta),
            "--json",
            "--cfd-threshold",
            "1.0",
            "--mit-threshold",
            "1.0",
            "--dna-bulges",
            "0",
            "--rna-bulges",
            "0",
        ],
    )
    assert base.exit_code == 0 and strict.exit_code == 0
    assert json.loads(strict.output)["n_sites"] <= json.loads(base.output)["n_sites"]


def test_offtarget_states_the_settings_its_site_count_depends_on(
    runner: CliRunner, nuclease_fasta: Path
) -> None:
    """`n_sites` is meaningless without the budgets and cut-offs that produced it.

    `test_offtarget_tuning_knobs_are_honored` proves the knobs change the answer.
    This proves the answer says which knobs it was given — otherwise two runs of the
    same guide report "5 sites" and "1 site" with nothing on either output to explain
    the difference, and neither number can be compared with a collaborator's.
    """
    args = ["offtarget", "ACGTAACGTTACGTAACGTT", "--reference-fasta", str(nuclease_fasta)]
    strict = [
        "--mismatches",
        "3",
        "--dna-bulges",
        "0",
        "--rna-bulges",
        "0",
        "--cfd-threshold",
        "0.05",
        "--mit-threshold",
        "0.01",
    ]

    human = runner.invoke(app, [*args, *strict])
    assert human.exit_code == 0
    assert "search: up to 3 mismatches, 0 DNA / 0 RNA bulges" in human.output
    assert "sites reported at CFD >= 0.05 or MIT >= 0.01" in human.output

    payload = json.loads(runner.invoke(app, [*args, *strict, "--json"]).output)
    assert payload["search"] == {
        "mismatch_threshold": 3,
        "dna_bulge_budget": 0,
        "rna_bulge_budget": 0,
        "cfd_threshold": 0.05,
        "mit_threshold": 0.01,
    }
    # ...and the defaults are reported as the defaults, not as whatever was last used.
    default = json.loads(runner.invoke(app, [*args, "--json"]).output)["search"]
    assert default != payload["search"]
    assert default["dna_bulge_budget"] == 1 and default["cfd_threshold"] == 0.20


def test_offtarget_rows_name_the_pam(runner: CliRunner, nuclease_fasta: Path) -> None:
    """An NGG row and a low-stringency NAG row looked identical on the table."""
    args = ["offtarget", "ACGTAACGTTACGTAACGTT", "--reference-fasta", str(nuclease_fasta)]
    payload = json.loads(runner.invoke(app, [*args, "--json"]).output)
    assert payload["sites"], "fixture produced no sites to check"
    assert all(site["pam"] for site in payload["sites"])

    human = runner.invoke(app, args)
    assert human.exit_code == 0
    assert f"pam={payload['sites'][0]['pam']}" in human.output


def test_offtarget_human(runner: CliRunner, nuclease_fasta: Path) -> None:
    result = runner.invoke(
        app, ["offtarget", "ACGTAACGTTACGTAACGTT", "--reference-fasta", str(nuclease_fasta)]
    )
    assert result.exit_code == 0
    assert "site(s)" in result.output


# --- data -------------------------------------------------------------------


def test_data_list_does_not_call_a_licence_permission_a_shipped_dataset(
    runner: CliRunner,
) -> None:
    """The table printed "vendored" for every redistributable dataset. Almost none ships.

    `redistributable` is a *licence* fact — AlleleForge is permitted to ship this — and
    it was rendered as "vendored", a *presence* claim. gnomAD v4.1 is CC0, so it read
    as bundled while no gnomAD data ships at all; a user reasonably concludes they do
    not need `--gnomad`, which is the exact confusion the reference-only warning exists
    to prevent.
    """
    result = runner.invoke(app, ["data", "list"])
    assert result.exit_code == 0
    assert "vendored" not in result.output

    payload = json.loads(runner.invoke(app, ["data", "list", "--json"]).output)
    rows = {r["name"]: r for r in payload["datasets"]}

    # gnomAD: permitted, and not present.
    assert rows["gnomad"]["redistributable"] is True
    assert rows["gnomad"]["bundled"] is False
    # The CFD matrix is the one that genuinely ships — inside the package, never the
    # cache — so "not cached" would mislead in the other direction.
    assert rows["doench-2016-cfd"]["bundled"] is True
    assert rows["doench-2016-cfd"]["available"] is True
    assert rows["gnomad"]["available"] is False
    # Both directions asserted, so a row that hardcoded either answer is caught.
    assert {r["available"] for r in payload["datasets"]} == {True, False}


def test_data_list(runner: CliRunner) -> None:
    result = runner.invoke(app, ["data", "list"])
    assert result.exit_code == 0
    assert "clinvar" in result.output


def test_data_list_json(runner: CliRunner) -> None:
    result = runner.invoke(app, ["data", "list", "--json"])
    assert result.exit_code == 0
    names = {d["name"] for d in json.loads(result.output)["datasets"]}
    assert "gnomad" in names


def test_data_show(runner: CliRunner) -> None:
    result = runner.invoke(app, ["data", "show", "clinvar", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["name"] == "clinvar"


def test_data_show_unknown_is_missing_data(runner: CliRunner) -> None:
    result = runner.invoke(app, ["data", "show", "nope"])
    assert result.exit_code == ExitCode.MISSING_DATA


# --- bench ------------------------------------------------------------------


def test_bench_no_args_shows_help(runner: CliRunner) -> None:
    # The bench sub-app lists its commands when invoked bare (Phase 14).
    result = runner.invoke(app, ["bench"])
    assert result.exit_code == ExitCode.USAGE
    assert "list" in result.output and "run" in result.output


# --- error paths & misc -----------------------------------------------------


def test_reference_fasta_not_found_is_missing_data(runner: CliRunner) -> None:
    result = runner.invoke(
        app, ["offtarget", "ACGTACGTACGTACGTACGT", "--reference-fasta", "/no/such.fa"]
    )
    assert result.exit_code == ExitCode.MISSING_DATA


def test_config_file_not_found_is_missing_data(runner: CliRunner, prime_fasta: Path) -> None:
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--config",
            "/no/run.toml",
        ],
    )
    assert result.exit_code == ExitCode.MISSING_DATA


def test_non_numeric_weights_is_usage_error(
    runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd
) -> None:
    result = runner.invoke(app, [*design_cmd(prime_fasta, "json"), "--weights", "a,b,c,d"])
    assert result.exit_code == ExitCode.USAGE


def test_invalid_weight_values_are_usage_errors(
    runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd
) -> None:
    # Parseable-but-invalid weights (non-finite, negative) must be a clean usage
    # error, not an uncaught RankingWeights traceback with a success exit code.
    for spec in ("1,1,1,nan", "1,1,1,inf", "-1,1,1,1"):
        result = runner.invoke(app, [*design_cmd(prime_fasta, "json"), "--weights", spec])
        assert result.exit_code == ExitCode.USAGE, f"weights {spec!r} should be a usage error"


def test_offtarget_bad_pam_is_usage_error(runner: CliRunner, nuclease_fasta: Path) -> None:
    result = runner.invoke(
        app,
        [
            "offtarget",
            "ACGTAACGTTACGTAACGTT",
            "--reference-fasta",
            str(nuclease_fasta),
            "--pam",
            "XZ",
        ],
    )
    assert result.exit_code == ExitCode.USAGE


def test_design_verbose_reports_to_stderr(
    runner: CliRunner, prime_fasta: Path, design_cmd: DesignCmd
) -> None:
    result = runner.invoke(app, ["-v", *design_cmd(prime_fasta, "json")])
    assert result.exit_code == 0
    assert "candidate(s)" in result.stderr


# -- aforge verify -----------------------------------------------------------


def _menu_with_provenance(
    tmp_path: Path, *, provenance: bool = True, models: tuple = (), datasets: tuple = ()
) -> Path:
    from datetime import UTC, datetime

    from alleleforge.types.provenance import Provenance

    prov = None
    if provenance:
        prov = Provenance.capture(
            alleleforge_version="1.0.0",
            seed=7,
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            models=models,
            datasets=datasets,
            config_snapshot={"intent": "install"},
        )
    menu = RankedMenu(candidates=(), rationale="test", provenance=prov)
    path = tmp_path / "menu.json"
    path.write_text(menu.model_dump_json())
    return path


def test_verify_passes_on_complete_provenance(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(app, ["verify", str(_menu_with_provenance(tmp_path))])
    assert result.exit_code == 0
    assert "verified" in result.output


def test_verify_does_not_call_an_unrun_check_verified(runner: CliRunner, tmp_path: Path) -> None:
    """ "verified" for a run that hashed nothing is "not measured" printed as "clean".

    `aforge verify result.json` makes two different claims — provenance is complete,
    and the pinned artifacts still hash to what was recorded — and only the first is
    checked without `--cache-dir`. It reported `verified: true` with an empty check
    list, on the one command whose entire purpose is checking.
    """
    path = _menu_with_provenance(tmp_path)

    bare = runner.invoke(app, ["verify", str(path)])
    assert bare.exit_code == 0
    assert "verified" in bare.output
    assert "no artifact bytes were re-hashed" in bare.output
    payload = json.loads(runner.invoke(app, ["verify", str(path), "--json"]).output)
    assert payload["verified"] is True  # provenance really is complete
    assert payload["artifact_verification_run"] is False  # ...and nothing was hashed
    assert payload["artifacts_rehashed"] == 0

    # A cache directory that contains nothing must not read as a successful check
    # either: the flag was given, and still nothing was established.
    empty = runner.invoke(app, ["verify", str(path), "--cache-dir", str(tmp_path / "empty")])
    assert empty.exit_code == 0
    assert "nothing was re-hashed" in empty.output
    with_cache = json.loads(
        runner.invoke(
            app, ["verify", str(path), "--cache-dir", str(tmp_path / "empty"), "--json"]
        ).output
    )
    assert with_cache["artifact_verification_run"] is True
    assert with_cache["artifacts_rehashed"] == 0


def test_verify_fails_without_provenance(runner: CliRunner, tmp_path: Path) -> None:
    path = _menu_with_provenance(tmp_path, provenance=False)
    result = runner.invoke(app, ["verify", str(path)])
    assert result.exit_code == ExitCode.UNAVAILABLE


def test_verify_detects_tampered_checkpoint(runner: CliRunner, tmp_path: Path) -> None:
    import hashlib

    from alleleforge.types.provenance import ModelCheckpoint

    payload = b"weights"
    digest = hashlib.sha256(payload).hexdigest()
    ck = ModelCheckpoint(name="demo", version="1.0", sha256=digest)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "demo.1.0.ckpt").write_bytes(payload)
    path = _menu_with_provenance(tmp_path, models=(ck,))

    ok = runner.invoke(app, ["verify", str(path), "--cache-dir", str(cache)])
    assert ok.exit_code == 0 and "ok" in ok.output

    (cache / "demo.1.0.ckpt").write_bytes(b"tampered")
    bad = runner.invoke(app, ["verify", str(path), "--cache-dir", str(cache)])
    assert bad.exit_code == ExitCode.UNAVAILABLE
    assert "MISMATCH" in bad.output


def test_verify_detects_tampered_dataset(runner: CliRunner, tmp_path: Path) -> None:
    # A pinned dataset (the vendored Doench-2016 CFD matrix is the load-bearing case)
    # is a result-determining artifact: the tamper contract covers a checkpoint *or
    # dataset* whose bytes no longer match its hash, so verify must re-hash it too.
    import hashlib

    from alleleforge.data.registry import DEFAULT_REGISTRY
    from alleleforge.types.provenance import DatasetVersion

    payload = b'{"cfd": "matrix"}'
    digest = hashlib.sha256(payload).hexdigest()
    ds = DatasetVersion(name="doench-2016-cfd", version="2016", sha256=digest)
    cache = tmp_path / "cache"
    ds_path = DEFAULT_REGISTRY.cache_path("doench-2016-cfd", cache_dir=cache)
    ds_path.parent.mkdir(parents=True)
    ds_path.write_bytes(payload)
    path = _menu_with_provenance(tmp_path, datasets=(ds,))

    ok = runner.invoke(app, ["verify", str(path), "--cache-dir", str(cache)])
    assert ok.exit_code == 0 and "ok" in ok.output

    ds_path.write_bytes(b"tampered-cfd-matrix")
    bad = runner.invoke(app, ["verify", str(path), "--cache-dir", str(cache)])
    assert bad.exit_code == ExitCode.UNAVAILABLE
    assert "MISMATCH" in bad.output


# --- offtarget: the on-target locus ------------------------------------------


def _offtarget_fasta(tmp_path: Path) -> tuple[Path, str, str]:
    """Return (fasta, spacer, locus) for a spacer with one perfect reference hit."""
    spacer = "ACGTAACGTTACGTAACGTT"  # no GG, no CC: the only PAM is the planted one
    contig = "T" * 30 + spacer + "TGG" + "T" * 30
    fasta = tmp_path / "ot.fa"
    fasta.write_text(f">chr1\n{contig}\n")
    return fasta, spacer, "chr1:30-50(+)"


def test_offtarget_says_when_the_on_target_is_not_excluded(
    runner: CliRunner, tmp_path: Path
) -> None:
    """A specificity that counts the guide against itself must say so.

    Without a locus the tool cannot know which perfect match is the intended one,
    so reporting all of them is the honest answer to the question asked — but the
    number is then not the quantity a design report prints under the same name.
    """
    fasta, spacer, _ = _offtarget_fasta(tmp_path)
    result = runner.invoke(app, ["offtarget", spacer, "--reference-fasta", str(fasta), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["on_target_excluded"] is False
    assert payload["n_sites"] == 1  # the guide's own locus, counted

    human = runner.invoke(app, ["offtarget", spacer, "--reference-fasta", str(fasta)])
    assert "on-target locus NOT excluded" in human.output


def test_offtarget_excludes_the_locus_when_given(runner: CliRunner, tmp_path: Path) -> None:
    fasta, spacer, locus = _offtarget_fasta(tmp_path)
    result = runner.invoke(
        app,
        ["offtarget", spacer, "--reference-fasta", str(fasta), "--on-target", locus, "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["on_target_excluded"] is True
    assert payload["n_sites"] == 0  # a spotless guide reads as spotless
    assert payload["specificity"] == 1.0

    human = runner.invoke(
        app, ["offtarget", spacer, "--reference-fasta", str(fasta), "--on-target", locus]
    )
    assert "on-target locus NOT excluded" not in human.output


@pytest.mark.parametrize("locus", ["nonsense", "chr1:50-30(+)", "chr1:10", "chr1:5-5(+)"])
def test_offtarget_rejects_a_malformed_locus(runner: CliRunner, tmp_path: Path, locus: str) -> None:
    """A mistyped locus must fail loudly, not silently disable the exclusion."""
    fasta, spacer, _ = _offtarget_fasta(tmp_path)
    result = runner.invoke(
        app, ["offtarget", spacer, "--reference-fasta", str(fasta), "--on-target", locus]
    )
    assert result.exit_code == ExitCode.USAGE


# --- design: the render cap --------------------------------------------------


def test_render_candidates_caps_the_html(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """The cap `render_html` has taken since it was added is now reachable from here."""
    out = tmp_path / "small.html"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--no-offtarget",
            "--format",
            "html",
            "--render-candidates",
            "3",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    html = out.read_text()
    assert "candidates:" in html or "Candidates" in html
    assert "the top 3 by rank plus every Pareto-front candidate" in html


def test_render_candidates_zero_draws_everything(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """`0` is the command-line spelling of "no cap" — a 0-candidate render is useless."""
    common = [
        "design",
        "chr2:71:A>C",
        "--reference-fasta",
        str(prime_fasta),
        "--intent",
        "install",
        "--no-offtarget",
        "--format",
        "html",
    ]
    capped = tmp_path / "capped.html"
    full = tmp_path / "full.html"
    assert runner.invoke(app, [*common, "--out", str(capped)]).exit_code == 0
    assert (
        runner.invoke(app, [*common, "--render-candidates", "0", "--out", str(full)]).exit_code == 0
    )
    assert len(full.read_text()) > len(capped.read_text())
    assert "plus every Pareto-front candidate" not in full.read_text()


def test_the_json_export_ignores_the_render_cap(
    runner: CliRunner, prime_fasta: Path, tmp_path: Path
) -> None:
    """A display cap must never reach the lossless export."""
    out = tmp_path / "all.json"
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--no-offtarget",
            "--format",
            "json",
            "--render-candidates",
            "3",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert len(json.loads(out.read_text())["candidates"]) > 3


@pytest.mark.parametrize(
    ("args", "expect_ood"),
    [([], False), (["--cell-context", "K562"], False), (["--cell-context", "HepG2"], True)],
)
def test_cell_context_flag_drives_the_ood_flag(
    runner: CliRunner, prime_fasta: Path, args: list[str], expect_ood: bool
) -> None:
    """`cell_context` was reachable only from a config file; a flag is the obvious way."""
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:71:A>C",
            "--reference-fasta",
            str(prime_fasta),
            "--intent",
            "install",
            "--no-offtarget",
            "--format",
            "json",
            *args,
        ],
    )
    assert result.exit_code == 0
    top = json.loads(result.output)["candidates"][0]
    assert top["efficiency"]["in_distribution"] is not expect_ood
    assert ("ood" in top["flags"]) is expect_ood


# --- the population-aware off-target search, from the CLI ---------------------


@pytest.fixture
def bias_case(tmp_path: Path) -> tuple[Path, Path, str]:
    """The rs114518452-style reference-bias case, as CLI inputs.

    A spacer with no NRG PAM after it in the reference — so a reference-only scan
    is blind — and an AFR-enriched population allele that creates a de-novo `NGG`.
    """
    spacer = "GACCATGCAACCTTGAACGT"
    pad = "T" * 10
    fasta = tmp_path / "bias.fa"
    fasta.write_text(f">chr2\n{pad}{spacer}CGT{pad}\n")
    sites = tmp_path / "bias.tsv"
    sites.write_text(
        "#chrom\tpos\tref\talt\taf\tafr\tamr\teas\tnfe\tsas\n"
        # 1-based, as in a VCF: 0-based 32 is the base the allele changes.
        "chr2\t33\tT\tG\t0.03\t0.105\t0.012\t0.0\t0.001\t0.0\n"
    )
    return fasta, sites, spacer


def test_offtarget_is_reference_blind_without_population_data(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    fasta, _sites, spacer = bias_case
    result = runner.invoke(app, ["offtarget", spacer, "--reference-fasta", str(fasta), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["n_sites"] == 0  # the blind spot


def test_gnomad_makes_the_cli_search_population_aware(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    """The project's headline claim, reproduced through its primary interface.

    Until `--gnomad` existed there was no way to supply population alleles from the
    CLI at all, so every command-line off-target scan was reference-only — the
    exact safety gap the tool is built to close.
    """
    fasta, sites, spacer = bias_case
    result = runner.invoke(
        app,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(fasta),
            "--gnomad",
            str(sites),
            "--populations",
            "afr,nfe",
            "--json",
        ],
    )
    assert result.exit_code == 0
    body = json.loads(result.output)
    assert body["n_sites"] == 1
    site = body["sites"][0]
    assert site["origin"] == "population"
    assert site["ancestries"]["afr"] > site["ancestries"]["nfe"]  # ancestry-stratified


def test_populations_without_gnomad_warns_that_nothing_was_searched(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    """An empty ancestry breakdown reads like "clean"; say it is "not measured"."""
    fasta, _sites, spacer = bias_case
    result = runner.invoke(
        app,
        ["offtarget", spacer, "--reference-fasta", str(fasta), "--populations", "afr"],
    )
    assert result.exit_code == 0
    assert "REFERENCE-ONLY" in result.stderr
    assert "not measured" in result.stderr


def test_an_unreadable_gnomad_path_is_a_data_error(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    """Fail loudly: silently continuing would give a reference-only scan the user
    believes is population-aware."""
    fasta, _sites, spacer = bias_case
    result = runner.invoke(
        app,
        ["offtarget", spacer, "--reference-fasta", str(fasta), "--gnomad", "/nonexistent.tsv"],
    )
    assert result.exit_code == ExitCode.MISSING_DATA


def test_patient_vcf_personalizes_the_cli_scan(
    runner: CliRunner, bias_case: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """A site present in this genome but not the reference must be nominated."""
    fasta, _sites, spacer = bias_case
    patient = tmp_path / "patient.txt"
    patient.write_text("chr2:33:T>G\n")  # 1-based, the CLI's own variant spelling
    result = runner.invoke(
        app,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(fasta),
            "--patient-vcf",
            str(patient),
            "--json",
        ],
    )
    assert result.exit_code == 0
    body = json.loads(result.output)
    assert body["n_sites"] == 1
    assert body["sites"][0]["origin"] == "patient"


def test_haplotypes_enable_the_haplotype_aware_pass(
    runner: CliRunner, bias_case: tuple[Path, Path, str], tmp_path: Path
) -> None:
    fasta, _sites, spacer = bias_case
    panel = tmp_path / "hap.tsv"
    panel.write_text(
        "#hap_id\tchrom\tstart\tend\tpopulation\tfrequency\tvariants\n"
        # the `variants` column is 0-based, unlike the gnomAD TSV's 1-based pos
        "H1\tchr2\t0\t43\tafr\t0.08\tchr2:32:T>G\n"
        "H1\tchr2\t0\t43\tnfe\t0.001\tchr2:32:T>G\n"
    )
    result = runner.invoke(
        app,
        [
            "offtarget",
            spacer,
            "--reference-fasta",
            str(fasta),
            "--haplotypes",
            str(panel),
            "--json",
        ],
    )
    assert result.exit_code == 0
    body = json.loads(result.output)
    assert body["n_sites"] == 1
    assert body["sites"][0]["causal_allele"]


@pytest.mark.parametrize(
    ("source_flag", "expect_warning"),
    [(None, True), ("--gnomad", False), ("--haplotypes", False)],
)
def test_the_unbacked_ancestry_warning_respects_every_source(
    runner: CliRunner,
    bias_case: tuple[Path, Path, str],
    tmp_path: Path,
    source_flag: str | None,
    expect_warning: bool,
) -> None:
    """The warning must not fire when ancestry data *was* supplied — by any route.

    Its first version keyed only on `--gnomad`, so a run with `--haplotypes` was
    told its scan was "REFERENCE-ONLY" while the haplotype pass was finding sites.
    """
    fasta, sites, spacer = bias_case
    panel = tmp_path / "hap.tsv"
    panel.write_text(
        "#hap_id\tchrom\tstart\tend\tpopulation\tfrequency\tvariants\n"
        "H1\tchr2\t0\t43\tafr\t0.08\tchr2:32:T>G\n"
    )
    args = ["offtarget", spacer, "--reference-fasta", str(fasta), "--populations", "afr"]
    if source_flag == "--gnomad":
        args += ["--gnomad", str(sites)]
    elif source_flag == "--haplotypes":
        args += ["--haplotypes", str(panel)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert ("REFERENCE-ONLY" in result.stderr) is expect_warning


def test_region_restriction_scopes_the_search(
    runner: CliRunner, bias_case: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """Scoping is what makes a real-genome scan practical; it must actually scope.

    `design()` did not accept a region restriction at all until this was wired, so
    the unified entry point — the one the CLI and web API are shells over — could
    not narrow a whole-genome search.
    """
    fasta, sites, spacer = bias_case
    base = ["offtarget", spacer, "--reference-fasta", str(fasta), "--gnomad", str(sites), "--json"]
    everywhere = json.loads(runner.invoke(app, base).output)
    assert everywhere["n_sites"] == 1

    # A window that excludes the site's locus (chr2:10-30) finds nothing...
    away = json.loads(runner.invoke(app, [*base, "--region", "chr2:100-200"]).output)
    assert away["n_sites"] == 0
    # ...and one that contains it still does.
    over = json.loads(runner.invoke(app, [*base, "--region", "chr2:0-43"]).output)
    assert over["n_sites"] == 1

    bed = tmp_path / "panel.bed"
    bed.write_text("# a gene panel\nchr2\t0\t43\n")
    from_bed = json.loads(runner.invoke(app, [*base, "--regions-bed", str(bed)]).output)
    assert from_bed["n_sites"] == 1


def test_a_malformed_region_is_a_usage_error(
    runner: CliRunner, bias_case: tuple[Path, Path, str]
) -> None:
    """A typo must not silently widen the search back to the whole genome."""
    fasta, _sites, spacer = bias_case
    result = runner.invoke(
        app, ["offtarget", spacer, "--reference-fasta", str(fasta), "--region", "nonsense"]
    )
    assert result.exit_code == ExitCode.USAGE


def test_supplied_sources_are_pinned_in_provenance(
    runner: CliRunner, bias_case: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """A user-supplied file has no upstream version, so pin it by what it contained.

    Two runs agree iff the bytes did. Without this a population-aware result names
    neither which data made it so nor whether any was supplied.
    """
    fasta, sites, _spacer = bias_case
    panel = tmp_path / "hap.tsv"
    panel.write_text(
        "#hap_id\tchrom\tstart\tend\tpopulation\tfrequency\tvariants\n"
        "H1\tchr2\t0\t43\tafr\t0.08\tchr2:32:T>G\n"
    )
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:6:T>G",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--no-offtarget",
            "--format",
            "json",
            "--gnomad",
            str(sites),
            "--haplotypes",
            str(panel),
        ],
    )
    assert result.exit_code == 0
    datasets = json.loads(result.output)["provenance"]["datasets"]
    by_name = {d["name"]: d for d in datasets}
    assert "gnomad-sites" in by_name and "haplotype-panel" in by_name
    for name in ("gnomad-sites", "haplotype-panel"):
        assert by_name[name]["version"].startswith("sha256:")
        assert by_name[name]["sha256"]


def test_the_patient_source_is_recorded_without_fingerprinting_it(
    runner: CliRunner, bias_case: tuple[Path, Path, str], tmp_path: Path
) -> None:
    """Record *that* the scan was personalized, not a hash of someone's genotypes.

    A reader needs to know a `patient`-origin site could appear and over how many
    variants; putting a content hash of a personal VCF into a report meant to be
    shared would be an identifier for that file, which reproducibility does not
    require.
    """
    fasta, _sites, _spacer = bias_case
    patient = tmp_path / "patient.txt"
    patient.write_text("chr2:33:T>G\n")
    result = runner.invoke(
        app,
        [
            "design",
            "chr2:6:T>G",
            "--reference-fasta",
            str(fasta),
            "--intent",
            "install",
            "--no-offtarget",
            "--format",
            "json",
            "--patient-vcf",
            str(patient),
        ],
    )
    assert result.exit_code == 0
    datasets = {d["name"]: d for d in json.loads(result.output)["provenance"]["datasets"]}
    assert datasets["patient-variants"]["version"] == "n=1"
    assert datasets["patient-variants"]["sha256"] is None
