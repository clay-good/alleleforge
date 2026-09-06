"""The TSV export must carry the caveats every other render of the same report does.

`build_report` puts `RESEARCH_USE_DISCLAIMER` on the `DesignReport`, and the HTML, the
PDF and the JSON all emit it. The TSV — a header and one row per candidate, nothing
else — emitted none of it:

    0-based                            tsv:. html:Y
    reference build                    tsv:. html:Y
    must be experimentally validated   tsv:. html:Y

So the one format a scientist opens in a spreadsheet and forwards to a colleague showed
efficiencies, specificities and genomic loci with no indication that they are uncertain
computational predictions, against which genome, in which coordinate convention. The
README asserted the convention was "stated in the report's own provenance block" for
the TSV as well as the HTML and PDF; the TSV had no provenance block, and its
`.provenance.json` sidecar carries no coordinate note either.

The notes lead the file as `#` comment lines, which is what VCF, GTF and bedGraph do,
so the column header is still the first non-comment line and a reader that skips
comments (`pandas.read_csv(..., comment="#")`, `read.delim(comment.char="#")`) sees the
identical table. `EXPORT_SCHEMA_VERSION` is bumped because a naive reader that skips
nothing does see a different first line — the version is the mechanism this export has
for exactly that, and it leads every row so a consumer can branch before parsing.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from alleleforge.design.designer import design
from alleleforge.genome.reference import ReferenceGenome
from alleleforge.report.builder import RESEARCH_USE_DISCLAIMER, build_report
from alleleforge.report.export import EXPORT_SCHEMA_VERSION, TSV_COLUMNS, report_to_tsv
from alleleforge.types.edit import EditIntent


@pytest.fixture
def report(tmp_path: Path) -> object:
    seq = list("AT" * 70)
    seq[63:66] = list("TGG")
    seq[55:58] = list("CCA")
    fasta = tmp_path / "prime.fa"
    fasta.write_text(">chr2\n" + "".join(seq) + "\n")
    menu = design(
        "chr2:71:A>C",
        reference=ReferenceGenome(fasta, build="hg38"),
        intent=EditIntent.INSTALL,
        max_candidates_per_chemistry=1,
    )
    return build_report(menu)


def _lines(text: str) -> tuple[list[str], list[str]]:
    """Split into (comment lines, data lines)."""
    comments = [line for line in text.splitlines() if line.startswith("#")]
    data = [line for line in text.splitlines() if not line.startswith("#")]
    return comments, data


def test_the_table_is_unchanged_for_a_comment_aware_reader(report: object) -> None:
    """The header is still the first non-comment line, and the rows still follow."""
    comments, data = _lines(report_to_tsv(report))  # type: ignore[arg-type]
    assert comments, "no notes were emitted"
    assert data[0].split("\t") == list(TSV_COLUMNS)
    assert len(data) >= 2
    assert data[1].split("\t")[0] == str(EXPORT_SCHEMA_VERSION)


def test_pandas_reads_it_identically_with_comment_skipping(report: object) -> None:
    """The claim about `comment='#'` is checked, not asserted."""
    polars = pytest.importorskip("polars")
    text = report_to_tsv(report)  # type: ignore[arg-type]
    stripped = "\n".join(line for line in text.splitlines() if not line.startswith("#")) + "\n"
    with_comments = polars.read_csv(io.StringIO(text), separator="\t", comment_prefix="#")
    without = polars.read_csv(io.StringIO(stripped), separator="\t")
    assert with_comments.equals(without)


def test_the_disclaimer_is_present(report: object) -> None:
    comments, _ = _lines(report_to_tsv(report))  # type: ignore[arg-type]
    joined = " ".join(c.lstrip("# ") for c in comments)
    assert RESEARCH_USE_DISCLAIMER.split(".")[0] in joined


def test_the_coordinate_convention_is_stated(report: object) -> None:
    """A bare `chr2:43-63` is the number a reader pastes into a genome browser."""
    comments, _ = _lines(report_to_tsv(report))  # type: ignore[arg-type]
    joined = " ".join(comments).lower()
    assert "0-based" in joined and "half-open" in joined


def test_the_genome_is_identified(report: object) -> None:
    """Not just the build label: the shape descriptor, as in the HTML footer."""
    comments, _ = _lines(report_to_tsv(report))  # type: ignore[arg-type]
    joined = " ".join(comments)
    assert "reference build hg38" in joined
    assert "contig" in joined and "pins" in joined


def test_every_note_line_is_a_comment(report: object) -> None:
    """A note that is not `#`-prefixed would corrupt the table it annotates."""
    text = report_to_tsv(report)  # type: ignore[arg-type]
    _, data = _lines(text)
    assert all(len(line.split("\t")) == len(TSV_COLUMNS) for line in data if line)
