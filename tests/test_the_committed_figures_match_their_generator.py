"""The figures in the docs are generated, committed, and were checked by nothing.

`scripts/figures.py` renders four SVGs into `docs/assets/figures/`, which mkdocs serves
and the README and preprint embed. They are committed, and `make figures` is the only
thing that regenerates them — it is not in `make ci`, and no CI job runs it. So a change
to the code behind a figure leaves the docs showing the old one, indefinitely, with every
gate green.

That is not hypothetical here. A previous round changed the SVG label layout and only
noticed a regression — a five-bar chart silently dropping half its task names — because
someone happened to regenerate the figures by hand.

The failure shape is the reproducibility golden's, one artifact over: something committed,
something that generates it, and nothing comparing the two. The figures are deterministic
by construction ("regenerates byte-for-byte from config plus seed"), so the comparison is
exact and cheap.
"""

from __future__ import annotations

from pathlib import Path

from alleleforge.viz import render_all_figures

_COMMITTED = Path(__file__).resolve().parents[1] / "docs" / "assets" / "figures"


def test_the_committed_figures_are_what_the_generator_produces(tmp_path: Path) -> None:
    written = render_all_figures(tmp_path)
    assert written, "the generator produced no figures; this check would be vacuous"

    stale: list[str] = []
    for stem, path in sorted(written.items()):
        committed = _COMMITTED / path.name
        if not committed.is_file():
            stale.append(f"{stem}: not committed")
        elif committed.read_bytes() != path.read_bytes():
            stale.append(f"{stem}: differs from what the generator writes")
    assert not stale, (
        f"the committed figures are out of date: {stale}. The docs and the preprint show "
        "these; regenerate them with `make figures` and commit the result."
    )


def test_every_generated_figure_is_committed(tmp_path: Path) -> None:
    """A new figure that nobody commits is a broken image in the built docs."""
    generated = {path.name for path in render_all_figures(tmp_path).values()}
    committed = {path.name for path in _COMMITTED.glob("*.svg")}
    assert generated <= committed, (
        f"the generator writes {sorted(generated - committed)}, which are not committed"
    )
    assert committed <= generated, (
        f"{sorted(committed - generated)} sit in the figures directory and nothing "
        "regenerates them; either the generator lost a figure or these are orphans"
    )
