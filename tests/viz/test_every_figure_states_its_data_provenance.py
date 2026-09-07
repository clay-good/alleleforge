"""A figure travels alone, so it has to say what it is drawn from.

`SYNTHETIC_DATA_NOTE`'s own docstring makes the argument: "A figure is the artifact most
likely to be seen *alone* — in a slide, an issue, a paper — so a caveat that lives in the
report next to it does not travel with it."

All four shipped figures do state their provenance, and in three different forms, each
right for its source: two carry the bundled-benchmark note, one says its locus is
CONSTRUCTED in the style of a real variant, one says its interval set is a seeded
SYNTHETIC construction. Nothing was wrong here — the guard is the point, because the
failure mode is a *new* figure shipping without a data line, and nothing enumerated the
registry.

Written against the rendered SVG rather than the builder source: the claim is about what a
reader sees in the file that gets pasted into a slide.
"""

from __future__ import annotations

import re

import pytest

from alleleforge.viz.figures import FIGURES, SYNTHETIC_DATA_NOTE

#: The forms a data-provenance statement may take. Each says where the numbers came from;
#: none of them lets a fabricated number pass as a measurement.
_ACCEPTED = (
    SYNTHETIC_DATA_NOTE.strip(),
    "Data: a CONSTRUCTED",
    "Data: a seeded SYNTHETIC",
)


def _texts(svg: str) -> list[str]:
    return re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S)


def test_there_are_figures_to_check() -> None:
    assert len(FIGURES) >= 4, sorted(FIGURES)


@pytest.mark.parametrize("name", sorted(FIGURES))
def test_the_figure_says_where_its_numbers_came_from(name: str) -> None:
    svg = FIGURES[name]()
    text = " ".join(_texts(svg))
    assert any(form in text for form in _ACCEPTED), (
        f"{name}.svg states no data provenance; a figure is seen alone, so a caveat "
        "living beside it in the report does not travel with it"
    )


@pytest.mark.parametrize("name", sorted(FIGURES))
def test_the_statement_is_in_the_drawing_not_a_comment(name: str) -> None:
    """It must be rendered text: a reader sees the picture, not the markup."""
    svg = FIGURES[name]()
    assert any(form in " ".join(_texts(svg)) for form in _ACCEPTED)


def test_the_accepted_forms_are_all_in_use() -> None:
    """A staleness guard: an accepted form no figure uses would be dead permission."""
    rendered = " ".join(" ".join(_texts(build())) for build in FIGURES.values())
    unused = [form for form in _ACCEPTED if form not in rendered]
    assert not unused, f"accepted provenance forms that no figure uses: {unused}"
