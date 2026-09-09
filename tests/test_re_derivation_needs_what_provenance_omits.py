"""`SPEC.md` required a result to be re-derivable from its provenance block. It is not.

`Provenance` carries the version, seed, reference build, timestamp, the pinned datasets
and checkpoints, and a config snapshot. It does **not** carry the variant, and neither
does the snapshot — `build_report` says so where it records one: "recorded verbatim (no
provenance fallback — the config snapshot carries no variant field)". So the block says
*how* a run was configured and not *what* was asked of it, and a bare `.provenance.json`
sidecar cannot be re-derived from.

That is a defensible design — a patient variant in a file meant to be handed around is a
different artifact — and every other document says the true, narrower thing: "re-derivable
from **config + seed**", "reproducible from its inputs". The one that stated the broad
version is `SPEC.md`, in the numbered principle that *requires* it.

The guard is derived: while `Provenance` has no variant field, no document may claim
re-derivability from the block alone. Add the field and the guard stops asking.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge.types.provenance import Provenance
from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_ROOT = Path(__file__).resolve().parents[1]

#: A claim that the provenance block alone is enough.
_BROAD = re.compile(
    r"re-derivable from (its |the )?provenance( block)?(?! .{0,40}(plus|and) )"
    r"|reproducible from (its |the )?provenance( block)?(?! .{0,40}(plus|and) )",
    re.I,
)


def test_provenance_carries_no_variant() -> None:
    """The premise, and the reason the broad claim is false."""
    assert "variant" not in Provenance.model_fields
    snapshot_keys = set(Provenance.model_fields)
    assert "config_snapshot" in snapshot_keys


def test_the_config_snapshot_has_no_variant_either() -> None:
    """The other place someone would look for it, checked on a real run."""
    from alleleforge.config import get_settings

    provenance = Provenance.capture(
        alleleforge_version="0",
        seed=1,
        config_snapshot=get_settings().snapshot(),
    )
    assert "variant" not in (provenance.config_snapshot or {}), provenance.config_snapshot


def test_no_document_claims_the_block_is_enough() -> None:
    offenders: list[str] = []
    for path in _prose_files():
        for match in _BROAD.finditer(prose_text(path)):
            offenders.append(f"{path.relative_to(_ROOT)}: {match.group(0)!r}")
    assert not offenders, (
        "`Provenance` carries no variant, so a result cannot be re-derived from the "
        f"block alone; these documents say it can: {offenders}"
    )


def test_the_spec_says_what_else_is_needed() -> None:
    """Not claiming the wrong thing is half of it; the reader needs the right one."""
    spec = (_ROOT / "SPEC.md").read_text(encoding="utf-8")
    principle = next(block for block in spec.split("\n\n") if "Reproducible to the byte" in block)
    assert "variant" in principle, principle
    assert "sidecar" in principle or "top level" in principle, principle
