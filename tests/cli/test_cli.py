"""End-to-end tests for the ``aforge`` Typer CLI (Phase 12)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

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


def test_offtarget_human(runner: CliRunner, nuclease_fasta: Path) -> None:
    result = runner.invoke(
        app, ["offtarget", "ACGTAACGTTACGTAACGTT", "--reference-fasta", str(nuclease_fasta)]
    )
    assert result.exit_code == 0
    assert "site(s)" in result.output


# --- data -------------------------------------------------------------------


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
