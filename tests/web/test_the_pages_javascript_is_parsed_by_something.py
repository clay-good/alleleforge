"""Seven guards read `app.js` as text; nothing had ever parsed it.

The served page's behaviour lives in `app.js`, and this suite checks it by regex: which
fields `readForm()` builds, which formats the download buttons fetch, whether every
`getElementById` matches an id in the markup. Every one of those reads the file as a
string, so a missing brace or a stray character ships a page whose script dies on load —
a blank form, no downloads, no results — with all seven still green. There is no
package.json, no linter, and no JavaScript step in CI: the only thing that had ever
executed this file was a person opening the page.

`node --check` parses it wherever node exists, which is most developer machines. Because a
test that quietly skips is how the native parity suite went dark for months, CI also runs
the check as an explicit step, and a test here asserts that step still exists — so the
guarantee does not rest on a runner happening to ship a JavaScript engine.

A first attempt added a hand-rolled brace-balance check to cover node-less machines. It
reported two unclosed delimiters in a file `node --check` accepts, because the "comment"
it was skipping was a regex literal — `.replace(/</g, "&lt;")`. Telling a regex from
division needs a real tokenizer, so the fallback is gone rather than approximately right.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"
_SCRIPTS = sorted(_FRONTEND.glob("*.js"))


def test_there_is_javascript_to_check() -> None:
    assert _SCRIPTS, "no frontend scripts found; this check would be vacuous"
    assert any(p.name == "app.js" for p in _SCRIPTS)


def test_the_check_is_not_quietly_absent() -> None:
    """A skip has to be legible, which is the half of this that keeps failing elsewhere.

    When node is missing the parse check skips, and CI runs an explicit `node --check`
    step so the guarantee does not depend on a runner happening to have it. This asserts
    the arrangement is still in place: a workflow that stops running node would otherwise
    leave the file parsed by nothing again, silently, exactly as before.
    """
    workflow = (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert "node --check" in workflow, (
        "CI no longer parses the frontend script explicitly; without it the suite's "
        "check skips wherever node is absent and nothing says so"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed here")
@pytest.mark.parametrize("script", _SCRIPTS, ids=lambda p: p.name)
def test_a_real_parser_accepts_it(script: Path) -> None:
    """The authoritative check, wherever a JavaScript engine exists."""
    result = subprocess.run(
        [str(shutil.which("node")), "--check", str(script)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"{script.name} is not valid JavaScript:\n{result.stderr}"
