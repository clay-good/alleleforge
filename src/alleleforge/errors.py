"""Canonical exception types shared across AlleleForge's artifact gates.

``ConsentError`` and ``ChecksumError`` are the two failures a caller most plausibly
wants to handle uniformly — "nothing may be downloaded without my say-so" and "an
artifact did not hash to what it was pinned at" are single policies, not per-module
ones. They were each defined independently in every module that raises them: four
``ConsentError`` classes (model zoo, genome reference, data registry, VEP) and three
``ChecksumError`` classes (model zoo, genome reference, data registry), all exported
under the same name from three public packages.

Seven distinct classes wearing two names is a trap with no visible edge. A caller who
writes ``from alleleforge.genome import ChecksumError`` and guards a design run with it
catches reference-checksum failures and silently misses the model-checkpoint and
dataset ones, which escape as unrelated-looking ``RuntimeError``s — and the scorers'
own docstrings promise "ConsentError / LicenseError / ChecksumError from the weight
gate" as though each named one type.

Each module still re-exports these names, so every existing import keeps working; what
changes is that they now refer to one class each, and ``isinstance`` says so.
"""

from __future__ import annotations

__all__ = [
    "AnnotationServiceError",
    "ChecksumError",
    "ConsentError",
    "MissingDependencyError",
    "ReferenceIndexError",
    "reason",
]


class ConsentError(RuntimeError):
    """Raised when a download or network fetch is needed but consent was withheld."""


class ChecksumError(RuntimeError):
    """Raised when an artifact's content hash does not match its pinned value."""


class MissingDependencyError(RuntimeError):
    """Raised when an optional dependency or artifact a feature needs is absent.

    A `RuntimeError` subclass so existing handlers keep working, and a *named* type so
    a caller can tell "this feature is not installed here" from "this code has a bug".
    The design path treats the first as graceful degradation and must not treat the
    second that way — it was catching bare `RuntimeError` for both, which reported a
    genuine defect in a vertical with the same word ("skipped") as a chemistry that
    simply did not apply.
    """


class AnnotationServiceError(RuntimeError):
    """Raised when a request-time annotation service cannot be reached or answers badly.

    `--vep` is the one flag that makes a network call while a design runs, and it had no
    handler at all: a 400, a 429 from Ensembl's rate limiter, a 503, a timeout, or simply
    being offline surfaced as a raw `requests` traceback with the query URL in it. A
    *named* type so the CLI and the web can say which flag asked for the annotation and
    that the design did not happen, rather than reporting a `requests` internal as if the
    tool had a bug.
    """


class ReferenceIndexError(OSError):
    """Raised when a reference FASTA has no ``.fai`` and one cannot be created.

    Opening a reference writes ``<fasta>.fai`` beside it when none exists — a file
    the caller did not name. That is ordinary when the directory is writable and
    impossible when it is not, which is the case this project's own
    `docker-compose.yml` creates by mounting the reference read-only.

    An `OSError` subclass so existing handlers that catch `OSError` around a
    reference open keep working, and a *named* type so the actionable message
    (`samtools faidx <path>`) can be raised in place of pyfaidx's advice about a
    Python API the caller is not using.
    """


def reason(exc: BaseException) -> str:
    """Return the human half of ``exc``: what went wrong, without the machinery.

    `pydantic.ValidationError` subclasses `ValueError`, so every boundary in this
    project that catches `ValueError` and prints `str(exc)` — the CLI's twenty error
    sites, the cohort's per-item `error` column, the designer's per-vertical skip
    note — prints pydantic's full report instead of a sentence::

        error: 1 validation error for PAM
        pattern
          Value error, PAM has non-IUPAC characters: ['X', 'Z'] [type=value_error,
          input_value='XYZ', input_type=str]
            For further information visit https://errors.pydantic.dev/2.13/v/value_error

    The sentence a person needs is on the third line. The rest names an internal model,
    a field, a framework's error taxonomy, and a library the caller never imported. One
    call site had been patched by hand for one model; the class stayed.

    Every other exception renders as it always did, so this is safe to apply at any
    boundary that already printed `str(exc)`.
    """
    errors = getattr(exc, "errors", None)
    if not callable(errors) or not isinstance(exc, ValueError):
        return str(exc)
    try:
        details = errors()
    except Exception:  # noqa: BLE001 - a look-alike `errors()` is not ours to interpret
        return str(exc)
    messages = [
        # Pydantic prefixes a message raised by a field validator with its own
        # category; the category is already implied by the sentence that follows it.
        str(detail.get("msg", "")).removeprefix("Value error, ")
        for detail in details
        if isinstance(detail, dict) and detail.get("msg")
    ]
    return "; ".join(messages) if messages else str(exc)
