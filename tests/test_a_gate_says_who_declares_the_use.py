"""The licence claim read as automatic, and the gate needs to be told.

The README's principles table says the default backbone is non-commercial "and the license
gate enforces it ... refused for commercial use at load time". Every word is true of the
mechanism and the sentence reads as a property of the tool: install AlleleForge, and a
commercial use of a research-only model is refused.

It cannot be. Nothing here can detect what a run is *for*. The gate refuses the use the
operator declares, and until `ALLELEFORGE_MODEL_USE` existed there was no way for any
shell to declare anything — so the refusal reached a Python caller who already knew to
pass `use=ModelUse.COMMERCIAL`, and nobody else. A reader of that sentence would have
believed themselves protected by a check that never ran.

This pins the honest form: wherever a document claims the licence gate enforces something,
it must also say who declares the use.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = [_ROOT / "README.md", *sorted((_ROOT / "docs").rglob("*.md"))]

#: How an operator states it. Any claim about the gate has to point here.
_DECLARATION = "ALLELEFORGE_MODEL_USE"

#: A claim that the licence gate refuses something.
_ENFORCEMENT = re.compile(
    r"(licen[sc]e gate[^.|]*(?:enforc|refus)|refused for commercial use)", re.I
)


def _claiming_paragraphs() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in _DOCS:
        for block in path.read_text(encoding="utf-8").split("\n\n"):
            for line in block.splitlines():
                if _ENFORCEMENT.search(line):
                    found.append((path.name, line))
    return found


def test_there_is_a_claim_to_check() -> None:
    claims = _claiming_paragraphs()
    assert claims, "no licence-gate claim found in the docs; this check would be vacuous"


@pytest.mark.parametrize(("source", "line"), _claiming_paragraphs(), ids=lambda v: str(v)[:40])
def test_a_gate_claim_names_who_declares_the_use(source: str, line: str) -> None:
    assert _DECLARATION in line or "declare" in line.lower(), (
        f"{source} says the licence gate refuses a use without saying who tells it which "
        f"use this is: {line[:200]}. Nothing here can detect commercial use; "
        f"{_DECLARATION} is how an operator states it."
    )


def test_the_setting_the_docs_name_is_the_one_the_code_reads() -> None:
    from alleleforge.config import Settings

    assert "model_use" in Settings.model_fields
    assert Settings.model_config["env_prefix"] + "MODEL_USE" == _DECLARATION
