"""Optional cross-check of the native engine against Cas-OFFinder.

When the external `Cas-OFFinder <https://github.com/snugel/cas-offinder>`_ binary
is installed, the native AlleleForge reference search can be cross-checked
against it and **disagreements flagged** — a guard against bugs in either engine.
Cas-OFFinder is reference-only, so the comparison is scoped to reference-origin
sites; AlleleForge's population/haplotype sites have no Cas-OFFinder counterpart
by design.

The pure functions — :meth:`CasOffinderAdapter.format_input` (build the binary's
input deck) and :meth:`CasOffinderAdapter.parse_output` (read its results,
legacy *and* bulge formats) — are exercised in CI against a recorded fixture. The
actual subprocess invocation is injectable (:meth:`run`'s ``runner`` argument), so
the orchestration is tested without the binary; only the default subprocess call
itself is never run in CI.

**Coordinate convention.** Cas-OFFinder reports the 0-based **leftmost** forward-strand
coordinate of the matched protospacer+PAM, with ``+``/``-`` giving the strand the guide
reads on; loci are compared as ``(chrom, position, strand)``. AlleleForge's
:class:`~alleleforge.types.offtarget.OffTargetSite` locus records the *protospacer*
start (PAM excluded). SpCas9's PAM is 3' of the protospacer on the reading strand, so on
the plus strand the PAM sits at the high-coordinate end and the two anchors coincide, but
on the minus strand the PAM sits at the **low**-coordinate end — the protospacer start is
``pam_len`` bases higher than the whole-match leftmost. :meth:`reference_loci` therefore
shifts a minus-strand locus down by ``pam_len`` so both engines key on the same anchor;
without it every minus-strand reference site would raise a spurious two-way disagreement.
"""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404 - used only via an explicit, opt-in binary invocation
import tempfile
from collections.abc import Callable
from pathlib import Path

from alleleforge.types.guide import PAM
from alleleforge.types.offtarget import OffTargetReport, SiteOrigin
from alleleforge.types.sequence import Strand

#: A locus key for set comparison: ``(chrom, start, strand)``.
LocusKey = tuple[str, int, Strand]

#: A runner takes the Cas-OFFinder input-file path + device flag and returns the
#: binary's stdout. Injected so tests drive :meth:`CasOffinderAdapter.run` without
#: the external binary; the default shells out to the real Cas-OFFinder.
Runner = Callable[[str], str]

_DIRECTION_STRAND = {"+": Strand.PLUS, "-": Strand.MINUS}


class CasOffinderAdapter:
    """Thin adapter that cross-checks reference sites against Cas-OFFinder."""

    def __init__(self, binary: str = "cas-offinder") -> None:
        """Record the Cas-OFFinder binary name (looked up on ``PATH``)."""
        self.binary = binary

    def available(self) -> bool:
        """Return ``True`` if the Cas-OFFinder binary is on ``PATH``."""
        return shutil.which(self.binary) is not None

    @staticmethod
    def reference_loci(report: OffTargetReport) -> set[LocusKey]:
        """Return the reference-origin site loci keyed to Cas-OFFinder's convention.

        Each locus is the leftmost forward-strand coordinate of the whole
        protospacer+PAM match, matching Cas-OFFinder's report so the two sets are
        directly comparable. Because the site locus records only the protospacer
        (PAM excluded), a minus-strand locus is shifted down by the PAM length —
        on the minus strand the PAM lies at the low-coordinate end, so the
        whole-match leftmost is ``pam_len`` below the protospacer start (see the
        module "Coordinate convention" note).
        """
        pam_len = len(report.pam)
        return {
            (
                s.locus.chrom,
                s.locus.start - pam_len if s.locus.strand is Strand.MINUS else s.locus.start,
                s.locus.strand,
            )
            for s in report.sites
            if s.origin is SiteOrigin.REFERENCE
        }

    def disagreements(
        self, report: OffTargetReport, external_loci: set[LocusKey]
    ) -> dict[str, set[LocusKey]]:
        """Return loci the two engines disagree on.

        Args:
            report: An AlleleForge off-target report.
            external_loci: Reference-site loci reported by Cas-OFFinder.

        Returns:
            ``{"only_alleleforge": ..., "only_cas_offinder": ...}`` — empty sets
            when the two agree on every reference locus.
        """
        ours = self.reference_loci(report)
        return {
            "only_alleleforge": ours - external_loci,
            "only_cas_offinder": external_loci - ours,
        }

    @staticmethod
    def format_input(reference: str | Path, spacer: str, pam: PAM, mismatches: int) -> str:
        """Return the Cas-OFFinder input deck for one guide.

        The deck is three lines: the reference path (a FASTA file or a directory
        of chromosome FASTAs), the search pattern (``N`` per spacer base followed
        by the PAM), and the query (the spacer followed by ``N`` per PAM base) with
        the mismatch budget.

        Args:
            reference: Path passed to Cas-OFFinder as its sequence source.
            spacer: The guide spacer, 5'->3'.
            pam: The PAM pattern (e.g. ``NGG``).
            mismatches: Maximum mismatches Cas-OFFinder should allow.
        """
        sp = str(spacer).upper()
        pattern = "N" * len(sp) + pam.pattern
        query = sp + "N" * len(pam.pattern)
        return f"{reference}\n{pattern}\n{query} {mismatches}\n"

    @staticmethod
    def parse_output(text: str) -> set[LocusKey]:
        """Parse Cas-OFFinder output into ``(chrom, position, strand)`` loci.

        Handles both the legacy 6-column layout
        (``crRNA chrom position DNA direction mismatches``) and the bulge-aware
        8-column layout
        (``bulge_type crRNA DNA chrom position direction mismatches bulge_size``).
        Header lines (starting with ``#``) and blanks are ignored.
        """
        loci: set[LocusKey] = set()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cols = line.split()
            if len(cols) >= 8:
                _, _, _, chrom, position, direction = cols[:6]
            elif len(cols) >= 6:
                _, chrom, position, _, direction = cols[:5]
            else:
                continue
            strand = _DIRECTION_STRAND.get(direction)
            if strand is None:
                continue
            loci.add((chrom, int(position), strand))
        return loci

    def _default_runner(self, input_path: str) -> str:  # pragma: no cover - external binary
        """Invoke Cas-OFFinder on ``input_path`` (CPU device) and return stdout."""
        with tempfile.NamedTemporaryFile("r", suffix=".tsv", delete=False) as out:
            out_path = out.name
        subprocess.run(  # noqa: S603 - binary resolved from PATH, args are not user shell input
            [self.binary, input_path, "C", out_path],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(out_path).read_text()

    def run(
        self,
        reference: str | Path,
        spacer: str,
        pam: PAM,
        *,
        mismatches: int = 4,
        runner: Runner | None = None,
    ) -> set[LocusKey]:
        """Run Cas-OFFinder for one guide and return its reference loci.

        Writes the input deck to a temp file, invokes ``runner`` (the real binary
        by default), and parses the result. Inject ``runner`` to drive the
        orchestration without the binary.

        Raises:
            RuntimeError: If the binary is needed (no ``runner`` given) but is not
                installed.
        """
        if runner is None and not self.available():
            raise RuntimeError(f"Cas-OFFinder binary {self.binary!r} is not on PATH")
        deck = self.format_input(reference, spacer, pam, mismatches)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(deck)
            input_path = fh.name
        output = (runner or self._default_runner)(input_path)
        return self.parse_output(output)
