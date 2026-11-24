"""ENCODE publishes no bedGraph, and `from_bedgraph` was the only reader.

The last entry in the loader-versus-upstream audit, and the one I got wrong first.

R703 recorded that `encode` was blocked on a dependency decision: ENCODE serves binary
bigWig/bigBed, so reading it would need a C-extension parser in a project that keeps CI
weight-free. That conclusion came from counting formats in **five sampled records** of a
narrow `output_type` query and reporting the result as the distribution. Re-measured with
ENCODE's own facets over all 513,214 DNase-seq files:

| file_format | files |
| --- | --- |
| `bed` | 415,734 |
| `bigBed` | 27,365 |
| `bigWig` | 19,092 |
| `bedGraph` | **0** |

So the dominant published format is **gzipped BED text**, including 6,552 `bed narrowPeak`
(4,431 on GRCh38). No new dependency is needed, and the real obstacle was never binary
formats — it was that `from_bedgraph` wants a five-column `track chrom start end value`
file that ENCODE does not publish in any form.

Fixtures are rows from `ENCFF762IIH.bed.gz`, a real GRCh38 DNase narrowPeak file.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from alleleforge.data.annotations import EncodeTracks
from alleleforge.types.sequence import GenomicInterval, Strand

#: Real rows: ten columns, 0-based half-open, signalValue seventh, and `-1` in the
#: pValue/qValue columns — which is what makes the sentinel worth handling.
_REAL_NARROWPEAK = """\
chr1\t10000\t10200\t.\t0\t.\t0.502928\t-1\t-1\t75
chr1\t191324\t191620\t.\t0\t.\t1.1802\t-1\t-1\t75
chr1\t191768\t191935\t.\t0\t.\t0.911976\t-1\t-1\t75
"""


def _interval(start: int, end: int) -> GenomicInterval:
    return GenomicInterval(chrom="chr1", start=start, end=end, strand=Strand.PLUS)


@pytest.fixture
def narrowpeak(tmp_path: Path) -> Path:
    path = tmp_path / "ENCFF762IIH.bed"
    path.write_text(_REAL_NARROWPEAK)
    return path


def test_the_real_signal_values_arrive_through_the_query(narrowpeak: Path) -> None:
    """Values checked against the file, not against a round number.

    narrowPeak is already 0-based half-open like BED, so no coordinate shift applies —
    an off-by-one here would attribute a peak's accessibility to the wrong window and
    move an efficiency score with it.
    """
    tracks = EncodeTracks.from_narrowpeak(narrowpeak, track="DNase")
    assert tracks.tracks == ("DNase",)
    assert tracks.signal("DNase", _interval(10000, 10200)) == pytest.approx(0.502928)
    assert tracks.signal("DNase", _interval(191324, 191620)) == pytest.approx(1.1802)


def test_a_gap_between_peaks_has_no_signal(narrowpeak: Path) -> None:
    """Absence of a peak is absence of accessibility, which is a real answer here."""
    assert EncodeTracks.from_narrowpeak(narrowpeak, track="DNase").signal(
        "DNase", _interval(50000, 50100)
    ) == pytest.approx(0.0)


def test_the_caller_names_the_track_because_the_format_has_no_column_for_it(
    narrowpeak: Path,
) -> None:
    """narrowPeak carries no track name; `--chromatin-track` already supplies one.

    So the name is a parameter rather than something invented from the filename — an
    accession like `ENCFF762IIH` is not what a reader wants to see in a provenance block
    describing an assay.
    """
    assert EncodeTracks.from_narrowpeak(narrowpeak, track="dnase-k562").tracks == ("dnase-k562",)


def test_a_negative_signal_value_is_skipped(tmp_path: Path) -> None:
    """`-1` is ENCODE's "no value", and negative accessibility is not a measurement.

    A real file's pValue and qValue columns are full of `-1`, so the sentinel is
    unmistakably in use in this format. Recording it as a signal would carry a negative
    number into the open-chromatin efficiency adjustment as though it had been measured.
    """
    path = tmp_path / "sentinel.bed"
    path.write_text("chr1\t100\t200\t.\t0\t.\t-1\t-1\t-1\t50\n" + _REAL_NARROWPEAK)
    tracks = EncodeTracks.from_narrowpeak(path, track="DNase")

    # The real peaks survive; the sentinel region reads as no signal rather than -1.
    assert tracks.signal("DNase", _interval(10000, 10200)) == pytest.approx(0.502928)
    assert tracks.signal("DNase", _interval(100, 200)) == pytest.approx(0.0)


def test_a_file_of_nothing_but_sentinels_defines_no_track(tmp_path: Path) -> None:
    """Separated from the test above, because it is a different situation.

    If every row is `-1` the file carries no accessibility at all, so no track is
    defined — and the CLI already refuses that case by name ("defines no tracks"),
    telling the caller what the format should look like. An empty track is the honest
    outcome; a track of zeros would be a measurement nobody made.
    """
    path = tmp_path / "all_sentinel.bed"
    path.write_text("chr1\t100\t200\t.\t0\t.\t-1\t-1\t-1\t50\n")

    assert EncodeTracks.from_narrowpeak(path, track="DNase").tracks == ()


def test_a_bed3_row_is_refused_rather_than_read_as_signalless(tmp_path: Path) -> None:
    """`bed bed3+` is 401,965 of ENCODE's DNase files and carries no signal column.

    It is the format a caller is most likely to reach for by mistake, and the honest
    answer is a refusal naming the shape: a three-column footprint call has no
    accessibility value to read, so silently producing a track of zeros would report
    "no accessibility anywhere" as a measurement.
    """
    path = tmp_path / "footprints.bed"
    path.write_text("chr1\t100\t200\n")
    with pytest.raises(ValueError, match="narrowPeak has ten") as refused:
        EncodeTracks.from_narrowpeak(path, track="DNase")
    assert "bed3+" in str(refused.value)


# -- dispatch ------------------------------------------------------------------


def test_narrowpeak_and_the_project_format_are_told_apart_by_row_shape(
    tmp_path: Path,
) -> None:
    """No flag needed: the second field is a contig in one format and a coordinate in the other.

    This project's five-column file begins with a track *name*, so its second field is
    `chr1`; narrowPeak begins with the contig, so its second field is `10000`. An integer
    there means narrowPeak.
    """
    project = tmp_path / "project.bedgraph"
    project.write_text("mytrack\tchr1\t100\t200\t2.5\n")
    assert EncodeTracks.load(project, track="ignored").tracks == ("mytrack",)

    peaks = tmp_path / "peaks.bed"
    peaks.write_text(_REAL_NARROWPEAK)
    assert EncodeTracks.load(peaks, track="DNase").tracks == ("DNase",)


def test_the_published_gzipped_file_loads(tmp_path: Path) -> None:
    """ENCODE serves these as `.bed.gz`; `open_text` sniffs gzip by magic bytes (R702)."""
    published = tmp_path / "ENCFF762IIH.bed.gz"
    with gzip.open(published, "wt") as handle:
        handle.write(_REAL_NARROWPEAK)

    tracks = EncodeTracks.load(published, track="DNase")
    assert tracks.signal("DNase", _interval(10000, 10200)) == pytest.approx(0.502928)


def test_ucsc_directive_lines_are_skipped(tmp_path: Path) -> None:
    """A browser-exported file carries `track`/`browser` headers the data does not."""
    path = tmp_path / "with_header.bed"
    path.write_text('track name="DNase"\nbrowser position chr1\n# a note\n' + _REAL_NARROWPEAK)
    assert EncodeTracks.load(path, track="DNase").signal(
        "DNase", _interval(10000, 10200)
    ) == pytest.approx(0.502928)
