"""Every whitelisted config key must actually be honored.

`_load_config` warns on an unknown key, which means a key *inside* the whitelist gets
no warning — so a key that no command reads is silently accepted and silently ignored,
and the user's run differs from the one their config describes. The comment beside the
run-param handling names this exact failure:

    "Without this a config key that _load_config accepts silently (no typo warning)
    would do nothing — the 'config file is honored' contract."

That contract had no test. The cheap half — every whitelisted key is read — lived here
as one module-wide scan, and **that scope was the hole**: it asked whether some command
reads a key, so `vector_scheme` and the four trained-model opt-ins passed it while
`aforge batch` read none of them. It now lives per command in
`test_a_config_key_that_is_accepted_is_read.py`, derived from each command's own source.
What remains here is the expensive half: a config-only run produces the same design as
the equivalent flags.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import app


def test_a_config_only_run_matches_the_equivalent_flags(
    runner: CliRunner, nuclease_fasta: Path, tmp_path: Path
) -> None:
    """The reproducibility claim, tested: a config carries the run, not just settings.

    The README says a run is reproducible from its seed plus config. Whether that is
    true depends on the config actually driving the design rather than being parsed
    and dropped, which is a different question from whether each key is read.
    """
    common = ["--reference-fasta", str(nuclease_fasta), "--format", "json"]

    by_flags = tmp_path / "flags.json"
    assert (
        runner.invoke(
            app,
            [
                "design",
                "chr2:26:A>G",
                *common,
                "--intent",
                "install",
                "--populations",
                "afr,nfe",
                "--weights",
                "0.5,0.2,0.2,0.1",
                "--out",
                str(by_flags),
            ],
        ).exit_code
        == 0
    )

    cfg = tmp_path / "run.toml"
    cfg.write_text('intent = "install"\npopulations = "afr,nfe"\nweights = "0.5,0.2,0.2,0.1"\n')
    by_config = tmp_path / "config.json"
    assert (
        runner.invoke(
            app, ["design", "chr2:26:A>G", *common, "--config", str(cfg), "--out", str(by_config)]
        ).exit_code
        == 0
    )

    flags_menu = json.loads(by_flags.read_text())
    config_menu = json.loads(by_config.read_text())

    # The scientific result, and the record of what produced it. Compared separately
    # from the whole payload so the assertion says which of the two failed — and the
    # wall clock is excluded by construction rather than by popping a key out of a
    # structure whose shape the test would then be asserting.
    assert config_menu["candidates"] == flags_menu["candidates"]
    assert config_menu["rationale"] == flags_menu["rationale"]
    assert (
        config_menu["provenance"]["config_snapshot"] == flags_menu["provenance"]["config_snapshot"]
    )
    assert config_menu["provenance"]["seed"] == flags_menu["provenance"]["seed"]

    # ...and the run really was configured, not defaulted: the flags differ from the
    # defaults, so an ignored config would produce a different snapshot.
    snapshot = config_menu["provenance"]["config_snapshot"]
    assert snapshot["intent"] == "install"
    assert snapshot["weights"]["efficiency"] == pytest.approx(0.5)
    # `populations` is the safety-relevant key, and the one worth proving travels.
    assert snapshot["populations"] == ["afr", "nfe"]
