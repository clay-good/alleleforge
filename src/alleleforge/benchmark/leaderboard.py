"""CRISPR-Bench leaderboard — model-card-gated submissions and a static board.

A submission is only admissible if it carries a **model card** (a name, a
license, and a citation, mirroring the model-zoo gate) and if every result it
contains **verifies its own signature**. That keeps the board honest: an entry
cannot claim a number it did not sign, and it cannot hide what model produced it.

Ranking respects metric direction — Spearman/AUROC and friends rank descending,
KL and ECE ascending (lower is better) — and the rendered board surfaces the
calibration column and split version next to every score, so calibration is read
as a first-class result rather than a footnote.
"""

from __future__ import annotations

import html
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from alleleforge.benchmark.runner import BenchmarkResult, ModelInfo

#: Metrics for which a lower value is better (everything else ranks descending).
LOWER_IS_BETTER = frozenset({"kl", "ece"})


def _md_cell(value: object) -> str:
    """Escape a value for a GitHub-flavored Markdown table cell.

    A submitter handle or model name is attacker-controlled text; a raw ``|``
    breaks the table and raw markup injects into the static board. Escape the
    pipe and backslash and flatten newlines so a cell can only ever be data.
    """
    return (
        str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    )


def _html_cell(value: object) -> str:
    """Escape a value for an HTML table cell (attacker-controlled text)."""
    return html.escape(str(value))


def _fmt_ece(ece: float | None) -> str:
    """Format an ECE cell, showing ``n/a`` for an undefined (``None``) value."""
    return "n/a" if ece is None else f"{ece:.4f}"


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
                )
            )

    @property
    def tasks(self) -> tuple[str, ...]:
        """Return the tasks with at least one entry, sorted."""
        return tuple(sorted({e.task for e in self._entries}))

    def rankings(self, task: str) -> list[LeaderboardEntry]:
        """Return entries for ``task`` ordered best-first by the primary metric.

        Ties on the primary metric break toward lower (better) ECE, then by
        model name for determinism. An **undefined** ECE (``None`` — a model that
        made no scorable prediction) sorts last on the calibration key, so a
        degenerate model can never win the honesty tie-break by claiming a perfect
        ``0.0`` it never earned.
        """
        entries = [e for e in self._entries if e.task == task]
        if not entries:
            return []
        descending = metric_is_descending(entries[0].primary_metric)
        return sorted(
            entries,
            key=lambda e: (
                -e.primary_value if descending else e.primary_value,
                float("inf") if e.ece is None else e.ece,
                e.model_name,
            ),
        )

    def render_markdown(self) -> str:
        """Render the whole board as GitHub-flavored Markdown."""
        if not self._entries:
            return "# CRISPR-Bench Leaderboard\n\n_No submissions yet._\n"
        lines = ["# CRISPR-Bench Leaderboard", ""]
        for task in self.tasks:
            ranked = self.rankings(task)
            metric = ranked[0].primary_metric
            arrow = "↓" if not metric_is_descending(metric) else "↑"
            lines.append(f"## {_md_cell(task)}")
            lines.append("")
            lines.append(
                f"| Rank | Model | Submitter | {_md_cell(metric)} {arrow} | ECE ↓ | Split |"
            )
            lines.append("| ---: | :--- | :--- | ---: | ---: | :--- |")
            for i, e in enumerate(ranked, start=1):
                lines.append(
                    f"| {i} | {_md_cell(e.model_name)} | {_md_cell(e.submitter)} | "
                    f"{e.primary_value:.4f} | {_fmt_ece(e.ece)} | {_md_cell(e.split_version)} |"
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
        ]
        if not self._entries:
            parts.append("<p>No submissions yet.</p>")
        for task in self.tasks:
            ranked = self.rankings(task)
            metric = ranked[0].primary_metric
            parts.append(f"<h2>{_html_cell(task)}</h2>")
            parts.append(
                "<table><thead><tr><th>Rank</th><th>Model</th><th>Submitter</th>"
                f"<th>{_html_cell(metric)}</th><th>ECE</th><th>Split</th></tr></thead><tbody>"
            )
            for i, e in enumerate(ranked, start=1):
                parts.append(
                    f"<tr><td>{i}</td><td>{_html_cell(e.model_name)}</td>"
                    f"<td>{_html_cell(e.submitter)}</td>"
                    f"<td>{e.primary_value:.4f}</td><td>{_fmt_ece(e.ece)}</td>"
                    f"<td>{_html_cell(e.split_version)}</td></tr>"
                )
            parts.append("</tbody></table>")
        parts.append("</body></html>")
        return "\n".join(parts)
