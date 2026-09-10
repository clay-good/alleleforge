"""One rounding rule for every rendering of a design.

`aforge design --format tsv` published `0.6532`. `aforge design --format json` published
`0.6531868174105568` — of the *same* number, in the *same* run, from the same report
object. The HTML and the PDF publish four places like the TSV, so three renders of one
document agreed and the fourth did not, and a client parsing the JSON got seventeen
significant digits of a heuristic whose own note says "coverage not measured".

This is the defect an earlier round fixed between two *shells* for the off-target report
(`alleleforge.types.offtarget.published`), reappearing between two *formats* of the design
report. The cause is the same: the rounding was a property of each writer, applied by hand
where somebody remembered, rather than a property of the published document.

The stored models keep full precision. This is what a *reader* is given, not what the
engine computed with.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from alleleforge.types.offtarget import AGGREGATE_PRECISION, FREQUENCY_PRECISION

__all__ = ["FREQUENCY_KEYS", "REPORT_PRECISION", "published"]

#: Places every published quantity is rounded to. Four, because that is what the TSV,
#: HTML and PDF writers already published, and because these are scores in `[0, 1]` whose
#: last digits are float noise — the same argument `AGGREGATE_PRECISION` records.
REPORT_PRECISION = AGGREGATE_PRECISION

#: Fields holding allele *frequencies* rather than scores. Four places round a 0.0001
#: carrier frequency to nothing, so these keep six — the same split, under the same
#: names, that the off-target report already makes.
FREQUENCY_KEYS = frozenset({"frequency", "ancestries", "frequencies"})

_M = TypeVar("_M", bound=BaseModel)


def _round(value: Any, places: int) -> Any:
    """Round one node of a dumped model, recursing into containers.

    Deliberately generic rather than a list of fields. A hand-written list of the numeric
    fields of a report with two dozen of them is the shape this project has repeatedly
    found going stale: the next field added is published unrounded, and nothing says so.
    """
    if isinstance(value, bool):  # a bool is an int; leave it alone
        return value
    if isinstance(value, float):
        return round(value, places)
    if isinstance(value, dict):
        return {
            key: _round(item, FREQUENCY_PRECISION if key in FREQUENCY_KEYS else places)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_round(item, places) for item in value)
    return value


def published(model: _M) -> _M:
    """Return ``model`` with every number rounded to the precision surfaces publish.

    Args:
        model: A report or a ranked menu, as the design produced it.

    Returns:
        The same model with its floats rounded. Validation is re-run, so a rounding that
        would break a model's own constraints fails here rather than in a reader.
    """
    return type(model).model_validate(_round(model.model_dump(), REPORT_PRECISION))
