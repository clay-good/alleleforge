"""`download_verified` opened a descriptor per fetch and closed it on one line.

`tempfile.mkstemp` returns an *open* descriptor as well as a path, and this function
wants only the path — the unique sibling that keeps the final move atomic. So it closes
the descriptor immediately and uses the name. A statement-deletion sweep removed that
`os.close(fd)` with the whole suite green: the download still works, the checksum still
verifies, the file still lands at its destination, and every assertion in the suite is
about those. One descriptor is leaked per call.

A design run fetches a handful of artifacts and nobody notices. A long-running server
resolving datasets and model checkpoints on demand, or a cohort over a few thousand
items, runs into its open-file limit — and the failure surfaces somewhere else entirely,
as an unrelated `OSError` from whatever code next tries to open something.

This is the third resource line this sweep has found in as many rounds — a FASTA handle,
a reference opened per item, and now a descriptor per download. None changes an answer.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from alleleforge._fetch import download_verified

_FD_DIR = Path("/dev/fd")


def _open_descriptors() -> int:
    if not _FD_DIR.is_dir():  # pragma: no cover - platform without /dev/fd
        pytest.skip("no /dev/fd on this platform")
    return len(os.listdir(_FD_DIR))


def test_the_probe_can_see_a_descriptor_open_and_close(tmp_path: Path) -> None:
    """The premise: without a probe that moves, the check below measures nothing."""
    before = _open_descriptors()
    handle = (tmp_path / "probe").open("w")
    try:
        assert _open_descriptors() > before
    finally:
        handle.close()
    assert _open_descriptors() == before


@pytest.mark.parametrize("repeats", [8])
def test_repeated_downloads_do_not_accumulate_descriptors(tmp_path: Path, repeats: int) -> None:
    payload = b"artifact bytes"

    def downloader(url: str, dest: Path) -> None:
        dest.write_bytes(payload)

    def verify(path: Path) -> None:
        assert path.read_bytes() == payload

    # One warm-up so any lazily-opened module state is not counted as a leak.
    download_verified(
        "https://example.invalid/a", tmp_path / "warm", downloader=downloader, verify=verify
    )
    before = _open_descriptors()
    for i in range(repeats):
        download_verified(
            "https://example.invalid/a", tmp_path / f"a{i}", downloader=downloader, verify=verify
        )
    assert _open_descriptors() == before, (
        f"{_open_descriptors() - before} descriptor(s) left open after {repeats} downloads"
    )


def test_a_failed_download_leaks_nothing_either(tmp_path: Path) -> None:
    """The error path unlinks the temp file; it must release the descriptor too."""

    def downloader(url: str, dest: Path) -> None:
        raise RuntimeError("the network went away")

    def verify(path: Path) -> None:  # pragma: no cover - never reached
        raise AssertionError

    download_verified(
        "https://example.invalid/warm",
        tmp_path / "warm",
        downloader=lambda u, d: d.write_bytes(b"x"),
        verify=lambda p: None,
    )
    before = _open_descriptors()
    for i in range(8):
        with pytest.raises(RuntimeError):
            download_verified(
                "https://example.invalid/a",
                tmp_path / f"b{i}",
                downloader=downloader,
                verify=verify,
            )
    assert _open_descriptors() == before
