"""One PDF text extractor for the tests that read a rendered report.

Six test modules reassembled the page's prose from its `(...) Tj` payloads, each with
its own copy of the regex. Four of them unescaped PDF's `\\(` and `\\)`; two did not, and
the difference is invisible until a note the writer emits happens to contain a
parenthesis — at which point the check fails against correct output, or worse, a
substring assertion silently stops matching.

The escaping is not incidental: the research-use disclaimer this project prints on every
render contains "(e.g. GUIDE-seq / CHANGE-seq / amplicon sequencing)", so every one of
those extractors was already mangling the sentence it exists to protect.

The regex also refuses to stop at an *escaped* closing parenthesis, which the shared copy
did: `(a \\) b) Tj` is one run, and treating it as two produces text that reads fine and
is not what the page says.
"""

from __future__ import annotations

import re

#: A text-showing operator's string payload. `(?<!\\)` so an escaped `\)` inside the
#: string does not end the match.
_RUN = re.compile(r"\((.*?)(?<!\\)\) Tj")


def pdf_runs(pdf: bytes, *, encoding: str = "cp1252") -> list[str]:
    """Return the page's text runs, unescaped, in order.

    cp1252 by default, not latin-1: the writer encodes an em dash as ``0x97``, which is
    an em dash in cp1252 and an unprintable control character in latin-1.
    """
    text = pdf.decode(encoding, errors="ignore")
    return [
        run.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
        for run in _RUN.findall(text)
    ]


def pdf_text(pdf: bytes, *, encoding: str = "cp1252") -> str:
    """Return the page's prose: every run joined, whitespace collapsed.

    The writer hard-wraps to a measured column, so a substring assertion against the raw
    bytes is really an assertion about where a line happens to break.
    """
    return " ".join(" ".join(pdf_runs(pdf, encoding=encoding)).split())
