"""Every whitelisted config key must actually be honored.

`_load_config` warns on an unknown key, which means a key *inside* the whitelist gets
no warning — so a key that no command reads is silently accepted and silently ignored,
and the user's run differs from the one their config describes. The comment beside the
run-param handling names this exact failure:

    "Without this a config key that _load_config accepts silently (no typo warning)
    would do nothing — the 'config file is honored' contract."

That contract had no test. The keys are all honored today; this keeps them that way,
and it is the cheap half. The expensive half — that a config-only run produces the same
design as the equivalent flags — is asserted end to end below.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cli.main import _RUN_PARAM_KEYS, app

_SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "cli" / "main.py"
).read_text()


def test_every_whitelisted_config_key_is_read_somewhere() -> None:
    """A whitelisted key nothing reads is accepted without warning and does nothing."""
    # Both access forms: `cfg.get("k")` and `cfg["k"]`. The first version of this
    # check recognized only `.get`, and reported `run_offtarget` as unread — it is
    # honored by subscript, in a helper whose docstring says so. A guard narrower than
    # the code it guards accuses working code, which is worse than not guarding.
    consumed = set(re.findall(r'cfg\.get\(\s*"([a-z_]+)"', _SOURCE))
    consumed |= set(re.findall(r'cfg\[\s*"([a-z_]+)"\s*\]', _SOURCE))
    consumed |= set(re.findall(r'"([a-z_]+)"\s+in\s+cfg', _SOURCE))
    assert consumed, "no config reads found — the check below would be vacuous"

    unread = sorted(key for key in _RUN_PARAM_KEYS if key not in consumed)
    assert not unread, (
        f"config keys accepted without a warning and never read: {unread}. "
        "Either honor them or drop them from _RUN_PARAM_KEYS, so an unknown key warns."
    )


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
