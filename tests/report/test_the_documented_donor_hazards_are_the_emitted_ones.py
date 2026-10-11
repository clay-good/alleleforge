"""The ordering page lists the donor's hazards; the code decides them.

`donor_oligo` is the guard at the ordering boundary, where being wrong costs a
synthesized reagent, and `docs/api/report.md` is where a reader learns which hazards it
will warn about. The page listed two of them. A third was added when `recut_blocked`
gained its unassessed state, and a fourth — the unrequested base change a blocked donor
carries permanently — had been emitted for some time without ever being documented.

Prose and code agreed by hand and drifted the moment either moved, which is the failure
this repository keeps finding. Each documented hazard is now matched to a warning the
module really produces, and each branch that produces one is matched back to the page.
"""

from __future__ import annotations

import re
from pathlib import Path

from alleleforge.report import oligos

_PAGE = Path(__file__).resolve().parents[2] / "docs" / "api" / "report.md"

#: One distinctive phrase per documented hazard, and the source phrase it describes.
_HAZARDS = {
    "Longer than a vendor synthesizes as one oligo": "beyond the ~",
    "The repaired product is still cuttable by its own guide": ("still a substrate for this guide"),
    "The re-cut disposition was never **assessed**": "was not assessed",
    "The donor carries a second, unrequested base change": "second, unrequested change",
}


def _page() -> str:
    return _PAGE.read_text(encoding="utf-8")


def _source() -> str:
    return Path(oligos.__file__).read_text(encoding="utf-8")


def test_every_documented_hazard_names_a_warning_the_code_emits() -> None:
    page, source = _page(), _source()
    for documented, emitted in _HAZARDS.items():
        assert documented in page, f"the ordering page no longer lists: {documented}"
        assert emitted in source, (
            f"the page documents {documented!r} but no warning in report/oligos.py "
            f"contains {emitted!r} any more"
        )


def test_every_warning_the_donor_can_raise_is_documented() -> None:
    """The direction that catches a hazard added to the code and not to the page."""
    body = _source()
    start = body.index("def donor_oligo(")
    end = body.index("\ndef ", start + 1)
    appends = re.findall(r"warnings\.append\(", body[start:end])
    assert len(appends) == len(_HAZARDS), (
        f"`donor_oligo` raises {len(appends)} warnings but the ordering page documents "
        f"{len(_HAZARDS)}. Add the new hazard to docs/api/report.md and to this test."
    )


def test_the_page_explains_that_unassessed_is_not_unblocked() -> None:
    page = _page()
    assert "`recut_blocked` is `None` rather than `False`" in page
    assert "a boolean cannot hold both" in page
