"""The served frontend must load nothing from a third party.

The README and the deployment guide both promise it, and the page says so to the
user: "All compute is local and user-controlled… The served frontend loads no
third-party scripts." That is a privacy claim about a page a lab opens while pasting
patient variants into it — a font from a CDN or an analytics snippet leaks the fact
and timing of every visit, and a third-party script leaks whatever it likes.

Nothing checked it. The claim holds today (every `src`, `href` and `fetch` in the
bundle is a same-origin relative path), and it is one `<script src="https://…">` from
being false with no test to notice — the shape R150 named: a promise about what is
*absent* needs a test about absence.

The first version of this scanned the static asset directory, and the *page the user
actually sees* is not in it: the frontend embeds a server-rendered design report, and
that report pulled Plotly from `cdn.plot.ly`. So the guard passed while a lab opening
the local UI to analyse a patient variant issued a request to a CDN at that moment.
The report is now scanned too — the surface, not the directory.

A link the *user* clicks is not a load, so `<a href="https://…">` is allowed; what is
forbidden is anything the browser fetches on its own.
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[2] / "src" / "alleleforge" / "web" / "frontend"

#: Attributes and calls that make the browser fetch something without being asked.
#: `href` is included only for `<link>` (stylesheets, preloads, icons) — an `<a href>`
#: is navigation the user chose and does not load anything into this page.
_LOADERS = (
    re.compile(r"""<link\b[^>]*\bhref\s*=\s*["']([^"']+)""", re.I),
    re.compile(r"""\bsrc\s*=\s*["']([^"']+)""", re.I),
    re.compile(r"""\bsrcset\s*=\s*["']([^"']+)""", re.I),
    re.compile(r"""@import\s+(?:url\()?["']?([^"')\s]+)""", re.I),
    re.compile(r"""\burl\(\s*["']?((?!data:)[^"')]+)""", re.I),
    re.compile(r"""\b(?:fetch|importScripts)\(\s*["'`]([^"'`]+)""", re.I),
    re.compile(r"""new\s+(?:WebSocket|EventSource|Worker)\(\s*["'`]([^"'`]+)""", re.I),
    re.compile(r"""\.open\(\s*["'][A-Z]+["']\s*,\s*["']([^"']+)""", re.I),
)


def _is_off_origin(target: str) -> bool:
    """Return ``True`` if the browser would fetch ``target`` from another origin."""
    t = target.strip()
    return t.startswith(("http://", "https://", "//")) and not t.startswith("///")


def test_the_frontend_fetches_nothing_off_origin() -> None:
    assets = sorted(p for p in _FRONTEND.iterdir() if p.is_file())
    assert assets, f"no frontend assets found under {_FRONTEND} — this check is vacuous"

    offenders: list[str] = []
    for asset in assets:
        text = asset.read_text()
        for pattern in _LOADERS:
            offenders += [
                f"{asset.name}: {target}"
                for target in pattern.findall(text)
                if _is_off_origin(target)
            ]
    assert not offenders, (
        "the served frontend loads third-party resources, which the README, the "
        f"deployment guide and the page itself promise it does not: {offenders}"
    )


def test_the_check_would_notice_a_cdn_script() -> None:
    """Guard the guard: the patterns must actually match a real CDN reference."""
    sample = '<script src="https://cdn.example.com/x.js"></script>'
    found = [t for p in _LOADERS for t in p.findall(sample) if _is_off_origin(t)]
    assert found == ["https://cdn.example.com/x.js"]
    # ...and a user-clickable link is still allowed.
    link = '<a href="https://github.com/clay-good/alleleforge">source</a>'
    assert not [t for p in _LOADERS for t in p.findall(link) if _is_off_origin(t)]


def test_the_report_iframe_denies_script_form_and_same_origin() -> None:
    """The report is server-generated HTML built from user-supplied strings.

    It is escaped, and since the charts became inlined SVG it contains no script
    element at all — but a sandbox is what makes an escaping bug in the renderer
    unexploitable rather than merely unlikely, and the frame had none. `srcdoc` in an
    unsandboxed frame runs with the application's own origin, which is how a report
    defect would have become an application compromise.
    """
    html = (_FRONTEND / "index.html").read_text()
    frame = re.search(r"<iframe[^>]*id=[\"']report[\"'][^>]*>", html)
    assert frame, "the report iframe was not found — this check would be vacuous"

    sandbox = re.search(r'sandbox="([^"]*)"', frame.group(0))
    assert sandbox, f"the report iframe is not sandboxed: {frame.group(0)}"
    tokens = set(sandbox.group(1).split())
    # The three that would give the report the application's privileges back.
    assert "allow-scripts" not in tokens
    assert "allow-same-origin" not in tokens
    assert "allow-forms" not in tokens


def test_an_external_link_in_a_report_does_not_hand_over_the_opener() -> None:
    """The report's one outbound link opens in a new tab, which needs `rel=noopener`."""
    from alleleforge.report import html as report_html

    source = Path(report_html.__file__).read_text()
    for match in re.finditer(r"<a href='(https?://[^']+)'([^>]*)>", source):
        attrs = match.group(2)
        assert "target='_blank'" in attrs, f"{match.group(1)} should open in a new tab"
        assert "noopener" in attrs, f"{match.group(1)} lacks rel=noopener"
