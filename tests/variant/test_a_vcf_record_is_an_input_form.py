"""Every shell promised a VCF record as an input form. None of them took one.

The served page's variant box carries the placeholder `chr2:71:A>C · 2 71 . A C`. Its help
says "Coordinates ... or a VCF record". `DesignRequest.variant` and `BatchRequest.variants`
say it. `aforge design --help` and `aforge resolve --help` say "a VCF record work[s]
everywhere". Typing the placeholder into the box the placeholder is in answered:

    unrecognized variant input: '2 71 . A C'

A `VcfRecord` is a **Python object** the resolver has always accepted. The string parser
had no pattern for the text form, so the one audience that types rather than imports —
which is three of the four — could not use it, and the promise sat in five places for as
long as it had existed.

A record pasted out of a terminal has lost its tabs, so the fields are split on whitespace
of any kind; the trailing QUAL/FILTER/INFO/sample columns are ignored, because none of
them says where the variant is; and the ID column is carried when it is an rsID, since a
row identifies its variant and dropping that loses the one field a reader could look the
same variant up by.
"""

from __future__ import annotations

import pytest

from alleleforge.variant.resolver import resolve

_REF, _ALT = "A", "C"


@pytest.mark.parametrize(
    "line",
    [
        "2 71 . A C",  # the page's own placeholder
        "chr2\t71\t.\tA\tC",  # a real tab-separated row
        "chr2 71 rs123 A C . PASS AC=1;AF=0.5",  # with QUAL/FILTER/INFO
        "chr2\t71\t.\tA\tC\t.\t.\t.\tGT\t0/1\t1/1",  # and sample columns
    ],
)
def test_a_vcf_data_line_resolves_to_the_variant_it_names(line: str) -> None:
    resolved = resolve(line)
    assert str(resolved.variant).endswith("70:A>C"), (line, resolved.variant)
    # 1-based in, 0-based out — the same convention `chrom:pos:ref>alt` is read in.
    assert resolved.variant.pos == 70
    assert resolved.source == "vcf"


def test_the_rsid_column_is_carried_when_it_is_one() -> None:
    assert str(resolve("chr2 71 rs123 A C").variant.rsid) == "rs123"
    assert resolve("chr2 71 . A C").variant.rsid is None


def test_a_symbolic_row_is_refused_by_name() -> None:
    """A legitimate VCF row that names no substitution, answered as such.

    `iter_vcf` skips exactly these when reading a file, counting the reason. A row pasted
    by hand used to fall through to "unrecognized variant input", which says the tool
    could not read it — when it read it fine and cannot design for it.
    """
    for alt in ("<DEL>", "<DUP>", "*", "]chr3:1000]A"):
        with pytest.raises(ValueError, match="not a designable substitution") as caught:
            resolve(f"chr2 71 . A {alt}")
        assert alt in str(caught.value), alt


def test_a_line_that_is_not_a_vcf_row_is_still_unrecognized() -> None:
    """The refusal must not widen: four fields is not a record, and prose is not one."""
    # (Trailing columns *are* a record: fields 6+ of a real row are QUAL, FILTER, INFO
    # and the samples, and none of them says where the variant is.)
    for text in ("2 71 . A", "some free text here", "chr2 x . A C", "chr2 71 . A"):
        with pytest.raises(ValueError) as caught:
            resolve(text)
        assert "unrecognized variant input" in str(caught.value), text


def test_the_coordinate_form_is_unaffected() -> None:
    """The shapes that already worked keep working, including the shell-ate-it hint."""
    assert resolve("chr2:71:A>C").source == "coordinates"
    with pytest.raises(ValueError, match="redirects output"):
        resolve("chr2:71:A")
