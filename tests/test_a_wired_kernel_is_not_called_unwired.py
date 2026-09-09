"""`SPEC_V2.md` said the native kernels were "not yet on a production hot path".

They are. `offtarget/_search.py` resolves `_NATIVE_REMOVED_BASE` and `_NATIVE_EVALUATE` at
import — deliberately, "so the availability check itself has to stay out of the loop",
because each runs "twice per PAM-positive anchor -- a million times over 2 Mb" — and the
scan's innermost loop calls them when the crate is built. That is the production hot path
of the feature this project describes as its differentiator.

The claim was true when written, which is what makes it the dangerous kind: a round found
the general form of this a while back — *"'not yet implemented' in docs is a claim with an
expiry date and no alarm on it"* — and put an alarm on the web endpoints. This is the same
alarm for the native kernels, and it is derived rather than spelled out: the dispatchers
are found by reading the module, so a third kernel wired in tomorrow is covered without
anyone remembering to add it here.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.prose import prose_text
from tests.test_readme_documents_the_cli import _prose_files

_ROOT = Path(__file__).resolve().parents[1]
_SEARCH = _ROOT / "src" / "alleleforge" / "offtarget" / "_search.py"

#: Phrases that assert the kernels are not yet used. Each is a claim with an expiry date.
_UNWIRED_CLAIMS = (
    "not yet on a production hot path",
    "not yet wired",
    "no production path calls",
)


def _dispatchers() -> list[str]:
    """Return the module-level native dispatchers the scan resolves at import."""
    source = _SEARCH.read_text(encoding="utf-8")
    return re.findall(r"^(_NATIVE_[A-Z_]+) = \($", source, re.M)


def test_the_scan_dispatches_to_native_kernels() -> None:
    """The premise. If this stops being true, the claims below become sayable again."""
    names = _dispatchers()
    assert len(names) >= 2, names
    source = _SEARCH.read_text(encoding="utf-8")
    for name in names:
        # Resolved at import *and* called somewhere: a constant nothing reads is a
        # dispatcher in name only.
        assert len(re.findall(rf"\b{name}\b", source)) >= 3, name


def test_no_document_says_the_kernels_are_unwired() -> None:
    wired = _dispatchers()
    offenders: list[str] = []
    for path in _prose_files():
        text = prose_text(path)
        for claim in _UNWIRED_CLAIMS:
            if claim in text:
                offenders.append(f"{path.relative_to(_ROOT)}: {claim!r}")
    assert not offenders, (
        f"the scan dispatches to {wired} from its innermost loop, and these documents "
        f"still say it does not: {offenders}"
    )


def test_the_claims_are_the_wording_the_documents_used() -> None:
    """Guard the guard: a phrase nobody would write catches nothing.

    The first entry is the sentence this round removed from `SPEC_V2.md`; the others are
    the two paraphrases nearest to it. If the class needs new wording, that is a decision
    to make here rather than a silent miss.
    """
    assert "not yet on a production hot path" in _UNWIRED_CLAIMS
    assert all(claim == claim.lower() for claim in _UNWIRED_CLAIMS)
