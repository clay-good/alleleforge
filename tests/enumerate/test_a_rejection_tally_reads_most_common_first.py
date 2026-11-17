"""The tally sentence promises "most common reason first", on a tally nobody shuffled.

`summarize` renders an enumerator's rejection tally as one sentence and its docstring
says the order: most common first, ties broken by key for determinism. A
statement-deletion sweep removed the `sort` with the whole suite green, because every
tally the suite builds has one reason in it, or arrives already in that order — a
`dict` keeps insertion order, and an enumerator that counts in a fixed sequence
produces a tally that happens to be sorted often enough.

It is the sentence a reader gets when a chemistry returns nothing: *"the PAM is not in
range (41); the edit is too large for a synthesizable RTT (3)"*. Unsorted, the same run
reports whichever rejection the enumerator happened to count first, and the reader
takes the leading clause as the main obstacle — which is the only reason the sentence
is ordered at all.
"""

from __future__ import annotations

from alleleforge.enumerate._reasons import summarize

_REASONS = {
    "pam": "the PAM is not in range",
    "rtt": "the edit is too large for a synthesizable RTT",
    "gc": "the spacer GC content is out of range",
}


def test_the_most_common_reason_leads() -> None:
    sentence = summarize({"gc": 2, "pam": 41, "rtt": 3}, _REASONS)
    assert sentence.startswith("the PAM is not in range (41)"), sentence
    assert sentence.index("(41)") < sentence.index("(3)") < sentence.index("(2)"), sentence


def test_a_tie_is_broken_by_key_so_the_sentence_is_reproducible() -> None:
    """Two runs of the same tally in a different insertion order read the same."""
    first = summarize({"rtt": 5, "gc": 5, "pam": 5}, _REASONS)
    second = summarize({"pam": 5, "gc": 5, "rtt": 5}, _REASONS)
    assert first == second, (first, second)
    assert first.index("GC content") < first.index("PAM") < first.index("RTT"), first


def test_a_zero_count_is_not_a_reason() -> None:
    """The other half of the comprehension, kept visible beside the ordering."""
    assert (
        summarize({"pam": 0, "rtt": 2}, _REASONS)
        == "the edit is too large for a synthesizable RTT (2)"
    )


def test_an_empty_tally_says_so() -> None:
    assert summarize({}, _REASONS) == "no candidate was examined"
