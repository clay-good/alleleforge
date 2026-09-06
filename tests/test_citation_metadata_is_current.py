"""The citation files must describe the package they ship with.

`CITATION.cff` and `.zenodo.json` are how AlleleForge is cited, and both restate
metadata that lives authoritatively elsewhere — the version in `_version.py`, the
license and repository URL in `pyproject.toml`, and the title, authors and keywords in
each other. Nothing checked any of it, so the next version bump would leave
`CITATION.cff` naming a release that no longer exists and every citation of the
software pointing at the wrong one. For a project whose stated purpose is
reproducible open science, a stale citation is not a cosmetic defect.

These pin only what is mechanically derivable. They cannot tell whether the abstract
is *good*, only whether the facts still agree.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _citation_cff() -> dict[str, str]:
    """Return the scalar top-level keys of CITATION.cff.

    A deliberately small reader rather than a YAML dependency: only the flat
    `key: value` lines matter here, and the file is checked into this repository, so
    the parsing risk is nil and the test stays dependency-free like the rest of CI.
    """
    out: dict[str, str] = {}
    for line in (_ROOT / "CITATION.cff").read_text().splitlines():
        m = re.fullmatch(r'([a-z-]+): "?(.*?)"?', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _pyproject() -> dict[str, object]:
    return tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"]


def _zenodo() -> dict[str, object]:
    return json.loads((_ROOT / ".zenodo.json").read_text())


def test_citation_version_matches_the_package() -> None:
    """A release bump that forgets this file makes every citation name a dead version."""
    from alleleforge._version import __version__

    cff = _citation_cff()
    assert cff.get("version") == __version__, (
        f"CITATION.cff says version {cff.get('version')!r} but the package is "
        f"{__version__!r}; update the file when bumping src/alleleforge/_version.py"
    )


def test_citation_license_matches_the_project() -> None:
    license_ = _pyproject()["license"]
    assert _citation_cff().get("license") == license_
    assert _zenodo()["license"] == license_
    assert (_ROOT / "LICENSE").is_file()


def test_the_two_citation_files_agree_on_the_facts() -> None:
    """Zenodo and CFF describe one artifact; a reader may see either."""
    cff, zenodo = _citation_cff(), _zenodo()
    assert cff["title"] == zenodo["title"]
    assert cff["repository-code"] == _pyproject()["urls"]["Repository"]  # type: ignore[index]

    cff_text = (_ROOT / "CITATION.cff").read_text()
    cff_keywords = set(re.findall(r"^  - (.+)$", cff_text.split("keywords:")[1], re.M))
    assert set(zenodo["keywords"]) == cff_keywords, (  # type: ignore[arg-type]
        f"the two citation files list different keywords: {set(zenodo['keywords']) ^ cff_keywords}"  # type: ignore[arg-type]
    )

    cff_authors = set(
        re.findall(r'name[s]?: "(.+)"', cff_text.split("authors:")[1].split("repository-code")[0])
    )
    zenodo_authors = {str(c["name"]).split(", ")[0] for c in zenodo["creators"]}  # type: ignore[index,union-attr]
    assert {a.split(", ")[0] for a in cff_authors} >= zenodo_authors, (
        f"author lists diverge: CFF {cff_authors} vs Zenodo {zenodo_authors}"
    )
