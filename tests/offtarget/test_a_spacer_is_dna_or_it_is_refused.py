"""`aforge offtarget '>chr1'` scanned a pasted FASTA header and scored it.

Found by installing the package the documented way and running it. `--pam NZZ` is
refused by name — `PAM` validates its pattern against the IUPAC alphabet — while the
*spacer* argument of the same call was handed to `search()` as a bare `str` and never
checked. So:

    $ aforge offtarget '>chr1' --reference-fasta ref.fa
    spacer >chr1 / PAM NGG: 0 site(s), worst score 0.000, specificity 0.026 ...
      search: ... the spacer is ambiguous at position(s) 1, 3, 4, 5, which cannot be
      scored ... a sub-threshold tail of 5072 further in-budget placement(s) ...
    $ echo $?
    0

Every part of that is wrong in the same way. `>` and `1` are not ambiguity codes, they
are not bases; the tool called them ambiguous because `_sanitize` folds anything outside
`ACGTN` to `N`. `POST /api/offtarget` accepted the same string. A digit typed for a base
(`...CCG0`), a space from a wrapped paste, a trailing hyphen — all scanned, all
`specificity 1.000`, all exit 0.

A safety number computed from a typo, printed with no refusal, is this project's
most-repeated defect class. What makes this instance plain is that the rule was already
enforced on the other argument of the same call, and the types that enforce it —
`Spacer`, `DNASequence` — are constructed from spacers elsewhere in the same module.

Fixed in `_spacer_str`, which is what `search()` puts every caller through, rather than
in the two shells: a check at a shell is one the next caller walks past. Both shells
already turn a `ValueError` from `search()` into their own refusal, so one change gave
the CLI a usage error and the API a 422 carrying the same sentence.

The IUPAC ambiguity codes stay accepted. They are what the "ambiguous at position(s)"
disclosure is for, and refusing them would delete a real capability to fix a typo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.offtarget.engine import search
from alleleforge.types.guide import PAM, Spacer
from alleleforge.types.sequence import DNASequence

_PAM = PAM(pattern="NGG")
_GOOD = "GACGTTGCAAGGCTTACCGT"


@pytest.fixture
def reference(tmp_path: Path) -> ReferenceGenome:
    import random

    rng = random.Random(3)
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "".join(rng.choice("ACGT") for _ in range(4000)) + "\n")
    return ReferenceGenome(fasta, build="hg38")


#: Real ways a spacer argument goes wrong, each seen as a plausible paste or typo.
_REFUSED = {
    ">chr1": "a pasted FASTA header",
    "GACGTTGCAAGGCTTACCG0": "a zero typed for an O, or for a G",
    "GACGTTGCAAGGCTTACC T": "a space from a wrapped paste",
    "GACGTTGCAAGGCTTACCGT-": "a trailing hyphen from a list",
    "GACGTTGCAAGGCTTACCGT\n": "a trailing newline",
    "GACGTTGCAAGGCTTACCGU": "RNA, which this argument is not",
}


@pytest.mark.parametrize("spacer", sorted(_REFUSED))
def test_a_spacer_that_is_not_dna_is_refused(spacer: str, reference: ReferenceGenome) -> None:
    with pytest.raises(ValueError, match="non-IUPAC"):
        search(spacer, _PAM, reference=reference)


def test_the_refusal_names_the_characters_and_the_likely_cause() -> None:
    """A refusal a user can act on: which characters, and what usually produces them."""
    with pytest.raises(ValueError) as caught:
        search(">chr1", _PAM, reference=None)  # type: ignore[arg-type]
    message = str(caught.value)
    assert "'>'" in message and "'1'" in message
    assert "FASTA header" in message


def test_the_ambiguity_codes_are_still_accepted(reference: ReferenceGenome) -> None:
    """`N` is what the "ambiguous at position(s)" disclosure exists for; so are R/Y/K."""
    for spacer in ("GACGTTGCAANNNTTACCGT", "GACGTTGCAARYKTTACCGT"):
        report = search(spacer, _PAM, reference=reference)
        assert report.ambiguous_spacer_positions, spacer


def test_case_is_not_a_reason_to_refuse(reference: ReferenceGenome) -> None:
    """A soft-masked or lower-case paste is ordinary, and scored identically."""
    upper = search(_GOOD, _PAM, reference=reference)
    lower = search(_GOOD.lower(), _PAM, reference=reference)
    assert lower.n_sites == upper.n_sites
    assert lower.specificity_score() == upper.specificity_score()


def test_a_validated_spacer_object_is_not_re_checked(reference: ReferenceGenome) -> None:
    """`Spacer` and `DNASequence` are valid by construction; the check is for the `str`."""
    for form in (Spacer(sequence=DNASequence(_GOOD)), DNASequence(_GOOD), _GOOD):
        assert search(form, _PAM, reference=reference).spacer == _GOOD


def test_the_other_argument_of_the_same_call_was_already_checked() -> None:
    """The asymmetry that made this findable, kept as the reason the fix is symmetric."""
    with pytest.raises(ValueError, match="non-IUPAC"):
        PAM(pattern="NZZ")


# --- and the two shells, because the refusal is only useful where a user types ---


def test_the_cli_reports_it_as_a_usage_error(tmp_path: Path) -> None:
    """Same shape as the PAM refusal it sits beside: a sentence and exit 2."""
    from typer.testing import CliRunner

    from alleleforge.cli.main import ExitCode, app

    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "ACGT" * 500 + "\n")
    result = CliRunner().invoke(app, ["offtarget", ">chr1", "--reference-fasta", str(fasta)])
    assert result.exit_code == ExitCode.USAGE, result.output
    assert "non-IUPAC" in result.output + result.stderr


def test_the_api_answers_with_a_sentence_not_a_traceback(tmp_path: Path) -> None:
    """422 and the same words: a client reads a sentence, not a stack trace."""
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from alleleforge.web.api.app import create_app

    assert fastapi
    fasta = tmp_path / "chr1.fa"
    fasta.write_text(">chr1\n" + "ACGT" * 500 + "\n")
    client = TestClient(
        create_app(reference=ReferenceGenome(fasta, build="hg38")),
        raise_server_exceptions=False,
    )
    response = client.post("/api/offtarget", json={"spacer": ">chr1"})
    assert response.status_code == 422, response.text
    assert "non-IUPAC" in response.json()["detail"]
    ok = client.post("/api/offtarget", json={"spacer": _GOOD})
    assert ok.status_code == 200, ok.text
