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
    "ChecksumError",
    "ConsentError",
    "MissingDependencyError",
    "ReferenceIndexError",
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
