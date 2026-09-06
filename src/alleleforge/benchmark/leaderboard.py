"""CRISPR-Bench leaderboard — model-card-gated submissions and a static board.

A submission is only admissible if it carries a **model card** (a name, a
license, and a citation, mirroring the model-zoo gate) and if every result it
contains **verifies its own signature**. That keeps the board honest: an entry
cannot claim a number it did not sign, and it cannot hide what model produced it.

Ranking respects metric direction — Spearman/AUROC and friends rank descending,
KL and ECE ascending (lower is better) — and the rendered board surfaces the
calibration column and split version next to every score, so calibration is read
as a first-class result rather than a footnote.

Ranks never cross a **comparison group**: the ``(primary_metric, split_version,
dataset_is_synthetic)`` triple a score was computed under. Two models measured on
different splits, or one on the synthetic stand-in and one on a real corpus, are
not competitors, and a single 1-2-3 column over them asserts an ordering that the
numbers do not support. The board ranks within each group and renders one table
per group.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict

from alleleforge._version import __version__
from alleleforge.benchmark.runner import BenchmarkResult, ModelInfo
from alleleforge.report.builder import RESEARCH_USE_CORE

#: Metrics for which a lower value is better (everything else ranks descending).
LOWER_IS_BETTER = frozenset({"kl", "ece"})


#: Markdown inline metacharacters backslash-escaped in a table cell so submitter
#: text cannot form a link, emphasis, code span, or break the table.
_MD_METACHARS = "`*_[]()|"


def _md_cell(value: object) -> str:
    """Escape a value for a GitHub-flavored Markdown table cell.

    A submitter handle or model name is attacker-controlled text; a raw ``|``
    breaks the table and raw markup injects into the static board. Escaping only
    the pipe left ``<img onerror=…>`` (raw HTML) and ``[x](javascript:…)`` (an
    inline link) intact — active content on the shareable leave-behind if the
    Markdown is rendered by any HTML-passing renderer. HTML-escape the angle
    brackets and ampersand, backslash-escape every Markdown inline metacharacter,
    and flatten newlines, so a cell can only ever be data.
    """
    text = html.escape(str(value), quote=False)  # < > & -> entities: no raw HTML
    text = text.replace("\\", "\\\\")  # escape backslash first, before we add any
    for ch in _MD_METACHARS:
        text = text.replace(ch, "\\" + ch)
    return text.replace("\r", " ").replace("\n", " ")


def _html_cell(value: object) -> str:
    """Escape a value for an HTML table cell (attacker-controlled text)."""
    return html.escape(str(value))


def _fmt_ece(ece: float | None) -> str:
    """Format an ECE cell, showing ``n/a`` for an undefined (``None``) value."""
    return "n/a" if ece is None else f"{ece:.4f}"


def _synthetic_mark(entry: LeaderboardEntry) -> str:
    """Return a visible mark when a row's number came from the synthetic stand-in.

    A board mixing synthetic and real rows without saying which is which ranks them
    against each other, which is the one thing a leaderboard must not do silently.
    """
    return " **(synthetic)**" if entry.dataset_is_synthetic else ""


def _fmt_ood(entry: LeaderboardEntry) -> str:
    """Format the out-of-distribution cell as a share of the scored test fold.

    ``n/a`` when the submission predates the field or scored nothing — deliberately
    distinct from ``0%``, which is a model asserting it stood behind every prediction.
    """
    fraction = entry.ood_fraction
    if fraction is None:
        return "n/a"
    return f"{fraction:.0%} ({entry.n_out_of_distribution}/{entry.n_test})"


#: Printed above a task whose submissions span more than one comparison group, so a
#: reader does not carry a rank across the boundary between two tables.
_INCOMPARABLE_NOTE = (
    "Ranked separately per comparison group — these scores were measured on "
    "different splits, corpora, or metrics and are not comparable across groups."
)


def metric_is_descending(metric: str) -> bool:
    """Return ``True`` if higher values of ``metric`` rank ahead of lower ones."""
    return metric not in LOWER_IS_BETTER


class SubmissionError(ValueError):
    """Raised when a submission lacks a model card or carries a bad signature."""


class Submission(BaseModel):
    """A leaderboard submission: a carded model plus its signed results.

    The model-card gate and signature checks run when the submission is admitted
    to a :class:`Leaderboard` (see :meth:`Leaderboard.add`) rather than at
    construction, so the container stays a plain, serializable record.

    Attributes:
        submitter: Who is submitting (a name or handle).
        model: The model-card facts; all of name/license/citation are required.
        results: One or more signed :class:`BenchmarkResult` records.
        submitted_at: UTC submission time.
    """

    model_config = ConfigDict(frozen=True)

    submitter: str
    model: ModelInfo
    results: tuple[BenchmarkResult, ...]
    submitted_at: datetime

    def validate_admissible(self) -> None:
        """Enforce the model-card gate and verify every result signature.

        Raises:
            SubmissionError: If the model card is incomplete, no result is
                present, a result fails signature verification, a result's model
                does not match the submission's model, or two results cover the
                same task (a duplicate that would let one model rank twice).
        """
        if not (self.model.name and self.model.license and self.model.citation):
            raise SubmissionError(
                "a submission requires a model card with a name, license, and citation"
            )
        if not self.results:
            raise SubmissionError("a submission must include at least one result")
        tasks_seen: set[str] = set()
        for r in self.results:
            if not r.verify_signature():
                raise SubmissionError(
                    f"result for task {r.task!r} fails signature verification; "
                    "it was edited after signing"
                )
            if r.model.name != self.model.name:
                raise SubmissionError(
                    f"result model {r.model.name!r} does not match submission model "
                    f"{self.model.name!r}"
                )
            if r.task in tasks_seen:
                raise SubmissionError(
                    f"submission has two results for task {r.task!r}; one result per (model, task)"
                )
            tasks_seen.add(r.task)


class ComparisonGroup(NamedTuple):
    """The population a score was computed over — the unit a rank is valid within.

    Two entries are competitors only if all three fields agree: the same metric,
    measured on the same frozen split, over the same kind of corpus. A rank column
    spanning more than one group states an ordering nothing measured.

    Attributes:
        primary_metric: The metric the rank is on. Different metrics are different
            scales; ranking a Spearman against an AUROC is meaningless arithmetic.
        split_version: The frozen split the score came from. Different splits are
            different test sets.
        synthetic: Whether the corpus was the bundled synthetic stand-in.
    """

    primary_metric: str
    split_version: str
    synthetic: bool

    def label(self) -> str:
        """Return a human-readable name for this group, for a table caption."""
        corpus = "synthetic stand-in" if self.synthetic else "real corpus"
        return f"{self.primary_metric} · split {self.split_version} · {corpus}"


class LeaderboardEntry(BaseModel):
    """One row on the board: a model's result on a single task."""

    model_config = ConfigDict(frozen=True)

    task: str
    submitter: str
    model_name: str
    split_version: str
    primary_metric: str
    primary_value: float
    ece: float | None
    metrics: dict[str, float | None]
    #: Test-fold size and how many of those predictions the model self-flagged as
    #: out-of-distribution. Carried because a leaderboard that shows a score without
    #: it puts two very different models on the same row: one that stood behind every
    #: prediction, and one that disclaimed nine in ten of them and scored the same.
    #: The uncertainty contract makes models declare this; the board hid it.
    n_test: int = 0
    n_out_of_distribution: int = 0
    #: Whether this row's number came from the bundled synthetic stand-in. A board that
    #: mixes synthetic and real rows without saying which is which ranks them together.
    dataset_is_synthetic: bool = False

    @property
    def ood_fraction(self) -> float | None:
        """Return the share of test predictions self-flagged OOD, if measurable."""
        if self.n_test <= 0:
            return None
        return self.n_out_of_distribution / self.n_test

    @property
    def comparison_group(self) -> ComparisonGroup:
        """Return the population this row's score was computed over."""
        return ComparisonGroup(
            primary_metric=self.primary_metric,
            split_version=self.split_version,
            synthetic=self.dataset_is_synthetic,
        )


def _context_lines() -> list[str]:
    """Return the lines every rendered board carries, whatever its format.

    A leaderboard is the artifact this tool produces that is most likely to be
    published, linked, screenshotted and quoted. It already marks a synthetic split
    on every row and in every section heading — the fact it most needs — and carried
    nothing else: no research-use disclaimer, no version, no generation time. A
    ranked table of CRISPR models to four decimal places, with nothing saying what
    produced it or what it is for.

    Shared by both renders, and by the empty board, so a fact added to one cannot go
    missing from the others — which is how this same gap reached four other artifacts
    in this codebase.
    """
    return [
        RESEARCH_USE_CORE,
        "Scores are benchmark metrics on frozen splits, not evidence that any model "
        "is fit for a therapeutic decision. A split marked (synthetic) is a stand-in "
        "fixture, and a number measured on one says nothing about real performance.",
        f"Rendered by AlleleForge {__version__} at {datetime.now(UTC).isoformat()}.",
    ]


def _rank_within(entries: list[LeaderboardEntry]) -> list[LeaderboardEntry]:
    """Order one comparison group best-first (see :meth:`Leaderboard.rankings`)."""
    descending = metric_is_descending(entries[0].primary_metric)
    return sorted(
        entries,
        key=lambda e: (
            -e.primary_value if descending else e.primary_value,
            float("inf") if e.ece is None else e.ece,
            e.model_name,
        ),
    )


class Leaderboard:
    """An in-memory leaderboard that ranks carded submissions per task."""

    def __init__(self) -> None:
        """Initialise an empty leaderboard."""
        self._entries: list[LeaderboardEntry] = []

    def add(self, submission: Submission) -> None:
        """Validate and admit a submission, flattening it into per-task entries.

        Raises:
            SubmissionError: If the submission fails the model-card or signature
                gate (see :meth:`Submission.validate_admissible`).
        """
        submission.validate_admissible()
        for r in submission.results:
            self._entries.append(
                LeaderboardEntry(
                    task=r.task,
                    submitter=submission.submitter,
                    model_name=submission.model.name,
                    split_version=r.split_version,
                    primary_metric=r.primary_metric,
                    primary_value=r.primary_value,
                    ece=r.metrics.get("ece"),
                    metrics=r.metrics,
                    n_test=r.n_test,
                    n_out_of_distribution=r.n_out_of_distribution,
                    dataset_is_synthetic=r.dataset_is_synthetic,
                )
            )

    @property
    def tasks(self) -> tuple[str, ...]:
        """Return the tasks with at least one entry, sorted."""
        return tuple(sorted({e.task for e in self._entries}))

    def comparison_groups(self, task: str) -> list[tuple[ComparisonGroup, list[LeaderboardEntry]]]:
        """Return ``task``'s entries partitioned into comparison groups, each ranked.

        A rank is only meaningful inside a :class:`ComparisonGroup`. Groups are
        ordered real-corpus-first, then by split version, then by metric name, so a
        rendered board is deterministic and leads with the rows that measured
        something real.
        """
        groups: dict[ComparisonGroup, list[LeaderboardEntry]] = {}
        for e in self._entries:
            if e.task == task:
                groups.setdefault(e.comparison_group, []).append(e)
        return [
            (g, _rank_within(groups[g]))
            for g in sorted(groups, key=lambda g: (g.synthetic, g.split_version, g.primary_metric))
        ]

    def rankings(self, task: str) -> list[LeaderboardEntry]:
        """Return ``task``'s entries, ranked within each comparison group.

        Ties on the primary metric break toward lower (better) ECE, then by
        model name for determinism. An **undefined** ECE (``None`` — a model that
        made no scorable prediction) sorts last on the calibration key, so a
        degenerate model can never win the honesty tie-break by claiming a perfect
        ``0.0`` it never earned.

        Entries from different comparison groups are concatenated, never
        interleaved: position in this list is a rank only relative to the rows
        sharing a group. Callers that render a rank number should iterate
        :meth:`comparison_groups` and restart the count per group.
        """
        return [e for _, ranked in self.comparison_groups(task) for e in ranked]

    def render_markdown(self) -> str:
        """Render the whole board as GitHub-flavored Markdown."""
        lines = ["# CRISPR-Bench Leaderboard", ""]
        for note in _context_lines():
            # Not `_md_cell`: that escapes every inline metacharacter for an
            # attacker-controlled *table cell*, and turns this project's own prose
            # into "validated \\(e.g. GUIDE-seq\\)". These lines are literals from
            # this module, not submitter input.
            lines.append(f"> {note}")
            lines.append("")
        if not self._entries:
            # The empty board is the one most likely to be published first, so it is
            # the one that least deserves to be the page with no context on it.
            lines.append("_No submissions yet._")
            return "\n".join(lines) + "\n"
        for task in self.tasks:
            groups = self.comparison_groups(task)
            lines.append(f"## {_md_cell(task)}")
            lines.append("")
            if len(groups) > 1:
                lines.append(_INCOMPARABLE_NOTE)
                lines.append("")
            for group, ranked in groups:
                metric = group.primary_metric
                arrow = "↓" if not metric_is_descending(metric) else "↑"
                lines.append(f"### {_md_cell(group.label())}")
                lines.append("")
                lines.append(
                    f"| Rank | Model | Submitter | {_md_cell(metric)} {arrow} | "
                    "ECE ↓ | OOD ↓ | Split |"
                )
                lines.append("| ---: | :--- | :--- | ---: | ---: | ---: | :--- |")
                for i, e in enumerate(ranked, start=1):
                    lines.append(
                        f"| {i} | {_md_cell(e.model_name)} | {_md_cell(e.submitter)} | "
                        f"{e.primary_value:.4f} | {_fmt_ece(e.ece)} | {_fmt_ood(e)} | "
                        f"{_md_cell(e.split_version)}{_synthetic_mark(e)} |"
                    )
                lines.append("")
        return "\n".join(lines)

    def render_html(self) -> str:
        """Render the board as a minimal, self-contained static HTML page."""
        parts = [
            "<!doctype html>",
            '<html lang="en"><head><meta charset="utf-8">',
            "<title>CRISPR-Bench Leaderboard</title></head><body>",
            "<h1>CRISPR-Bench Leaderboard</h1>",
            *(f"<p><em>{_html_cell(note)}</em></p>" for note in _context_lines()),
        ]
        if not self._entries:
            parts.append("<p>No submissions yet.</p>")
        for task in self.tasks:
            groups = self.comparison_groups(task)
            parts.append(f"<h2>{_html_cell(task)}</h2>")
            if len(groups) > 1:
                parts.append(f"<p><strong>{_html_cell(_INCOMPARABLE_NOTE)}</strong></p>")
            for group, ranked in groups:
                parts.append(f"<h3>{_html_cell(group.label())}</h3>")
                parts.append(
                    "<table><thead><tr><th>Rank</th><th>Model</th><th>Submitter</th>"
                    f"<th>{_html_cell(group.primary_metric)}</th><th>ECE</th>"
                    '<th title="share of test predictions the model self-flagged '
                    'out-of-distribution">OOD</th><th>Split</th></tr></thead><tbody>'
                )
                for i, e in enumerate(ranked, start=1):
                    parts.append(
                        f"<tr><td>{i}</td><td>{_html_cell(e.model_name)}</td>"
                        f"<td>{_html_cell(e.submitter)}</td>"
                        f"<td>{e.primary_value:.4f}</td><td>{_fmt_ece(e.ece)}</td>"
                        f"<td>{_fmt_ood(e)}</td>"
                        f"<td>{_html_cell(e.split_version)}"
                        + ("<strong> (synthetic)</strong>" if e.dataset_is_synthetic else "")
                        + "</td></tr>"
                    )
                parts.append("</tbody></table>")
        parts.append("</body></html>")
        return "\n".join(parts)
