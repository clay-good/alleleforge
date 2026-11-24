"""A compiled kernel from another version must be refused, not quietly trusted.

`assert_native_matches_python()` guards two things, and the suite covered one of them. The
*staleness* check — the installed extension older than the crate source beside it — has a
test, and the round that added it says so. The *version handshake* did not: deleting its
raise survived the sweep.

The two are not the same check. Staleness compares the build against the source tree, so
it only fires for someone who has the Rust sources. The version handshake compares the
compiled crate's own version against the Python package's, which is the case that reaches
an *installed* user: a wheel upgraded while a previously-built `aforge_native` stayed in
place, or a `maturin develop` from a different checkout. The source tree is not involved,
so the staleness check cannot see it.

What is at stake is not an import error. `aforge_native` exposes scan kernels that the
pure-Python paths mirror, and the project's own parity tests are what make
`prefer_native` safe to default on. Parity is established *between matched versions*. A
kernel built from different source is an unverified implementation of a scan that
decides off-target counts and specificity — and it will not fail to load, it will return
numbers.

The *named* error type is deliberate and is pinned here too. `MissingDependencyError` is
a `RuntimeError` subclass, so what matters is not the base class but that it is
distinguishable: the remedy is an install action the reader takes (`maturin develop`), not
a defect for them to report, and callers key on that distinction — the CLI maps it to
`ExitCode.UNAVAILABLE` rather than letting it surface as a crash.

Found by deleting the refusal (`scripts/mutate.py --mode raise`); it survived its list.
"""

from __future__ import annotations

import pytest

from alleleforge import _native
from alleleforge._native import assert_native_matches_python
from alleleforge.errors import MissingDependencyError


def test_the_build_this_environment_actually_has_is_accepted() -> None:
    """The premise, and the case the guard must not fire on.

    Whether or not the crate is built here, the real environment must pass: a guard that
    refused a correct install would be caught by this and nothing else.
    """
    assert_native_matches_python()


def test_an_unbuilt_crate_is_a_no_op_not_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """`None` means "not built", which is a supported configuration, not a mismatch.

    This is the `nv is not None` half of the condition. A guard written as `nv !=
    __version__` alone would refuse every pure-Python install — the default one — and the
    mismatch test below would still pass.
    """
    monkeypatch.setattr(_native, "native_version", lambda: None)
    monkeypatch.setattr(_native, "missing_native_functions", lambda: [])
    assert_native_matches_python()


@pytest.mark.parametrize(
    "built_version",
    ["0.0.1", "99.0.0", "0.1.0-dev", ""],
    ids=["older", "newer", "pre-release", "empty"],
)
def test_a_crate_built_from_another_version_is_refused(
    monkeypatch: pytest.MonkeyPatch, built_version: str
) -> None:
    """Any disagreement, in either direction.

    A *newer* compiled crate is refused as firmly as an older one, which is the right
    posture: the question is not which is ahead but whether parity was ever established
    between these two, and it was not.
    """
    from alleleforge import __version__

    assert built_version != __version__
    monkeypatch.setattr(_native, "native_version", lambda: built_version)

    with pytest.raises(MissingDependencyError) as refused:
        assert_native_matches_python()

    message = str(refused.value)
    assert built_version in message, message
    assert __version__ in message, (
        "the refusal does not name the version it expected, so the reader cannot tell "
        "which of the two halves of their install is the stale one",
        message,
    )
    assert "maturin develop" in message, (
        "the refusal does not name the command that fixes it; `MissingDependencyError` "
        "is chosen over RuntimeError precisely because there is an action to take",
        message,
    )


def test_the_refusal_is_an_install_action_not_a_defect_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The error *type* carries meaning here, so pin the named class, not its base.

    `MissingDependencyError` is what tells a caller — and the CLI's handler, which maps
    it to `ExitCode.UNAVAILABLE` — that this is a wiring problem with a remedy. It
    subclasses `RuntimeError`, so a test catching `RuntimeError` would pass against a
    regression that raised a bare one and lost exactly that signal.
    """
    monkeypatch.setattr(_native, "native_version", lambda: "0.0.0-not-a-real-version")

    with pytest.raises(MissingDependencyError):
        assert_native_matches_python()

    # The point of the named class: a bare RuntimeError would satisfy a looser test.
    assert issubclass(MissingDependencyError, RuntimeError)
    with pytest.raises(MissingDependencyError):
        assert_native_matches_python()
