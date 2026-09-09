"""The integrity sweep only a shell could run.

`aforge cache verify` was built in the CLI, whole: the walk over every content-addressed
namespace, the FM-index load (and optional reconstruction), the re-hash of every pinned
dataset and checkpoint, and the three-way pass/fail/nothing-checked distinction. All of it
in `cli/main.py`.

That is the gap this project treats as its most productive finding class — a capability
the library has that no shell can reach, here in its mirror image — and it was produced by
the very round that closed the same gap for `FMIndex.verify()`. `SPEC.md`'s sixth
principle is unambiguous: "The library is the source of truth; CLI and web are thin
shells. No business logic lives in the CLI or web layers."

`alleleforge.cache_sweep.verify_stores` is the sweep. The command renders it and picks an
exit code, which is a shell's whole job.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alleleforge.cache import ContentAddressedCache
from alleleforge.cache_sweep import FAILURES, UNCHECKED, CacheCheck, held_bytes, verify_stores
from alleleforge.cli.main import ExitCode, app


def test_a_python_caller_can_sweep(tmp_path: Path) -> None:
    """The point: no CLI, no typer, no process."""
    ContentAddressedCache("offtarget/v2", root=tmp_path, verify=True).put_text("a" * 64, "{}")
    checks = verify_stores(tmp_path)

    assert checks, "the sweep found nothing at all"
    assert all(isinstance(check, CacheCheck) for check in checks)
    kinds = {check.kind for check in checks}
    assert {"dataset", "checkpoint"} <= kinds, kinds
    assert any(kind.startswith("offtarget/") for kind in kinds), kinds


def test_a_check_says_which_of_the_three_it_is(tmp_path: Path) -> None:
    """Pass, failure, and nothing-established are different answers."""
    checks = verify_stores(tmp_path)
    for check in checks:
        assert check.failed == (check.status in FAILURES), check
        assert check.checked == (check.status not in UNCHECKED), check
    assert any(not check.checked for check in checks), "nothing was unchecked; too tidy"


def test_a_corrupt_entry_is_reported_to_the_library_caller(tmp_path: Path) -> None:
    store = ContentAddressedCache("offtarget/v2", root=tmp_path, verify=True)
    store.put_text("b" * 64, "{}")
    payload = tmp_path / "caches" / "offtarget" / "v2" / "bb" / ("b" * 64)
    payload.write_text("tampered")

    failures = [check for check in verify_stores(tmp_path) if check.failed]
    assert [check.kind for check in failures] == ["offtarget/v2"], failures


def test_held_bytes_is_a_library_call(tmp_path: Path) -> None:
    ContentAddressedCache("offtarget/v2", root=tmp_path, verify=True).put_text("c" * 64, "{}")
    held = held_bytes(tmp_path)
    assert held and sum(held.values()) > 0, held
    assert set(held) <= {"caches", "fm_index", "data", "models"}, held


def test_the_command_renders_the_library_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same answer through the shell, which is all the shell should add."""
    import alleleforge.config as config

    monkeypatch.setattr(config, "_SETTINGS", None)
    monkeypatch.setenv("ALLELEFORGE_CACHE_DIR", str(tmp_path))
    ContentAddressedCache("offtarget/v2", root=tmp_path, verify=True).put_text("d" * 64, "{}")

    result = CliRunner().invoke(app, ["cache", "verify", "--json"])
    assert result.exit_code == ExitCode.OK, result.output
    rendered = json.loads(result.stdout)["checks"]
    assert len(rendered) == len(verify_stores(tmp_path))


def test_the_command_body_holds_no_sweep() -> None:
    """A thin shell: the walk, the hashing and the loading are not in `cli/main.py`."""
    from alleleforge.cli.main import cache_verify

    body = inspect.getsource(cache_verify)
    for logic in ("hashlib", "stored_entries(", "FMIndex.load(", "DEFAULT_REGISTRY"):
        assert logic not in body, f"{logic} is still in the command body"
    assert "verify_stores(" in body, body
