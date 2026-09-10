"""Fetch a pinned artifact so a failed download cannot poison the cache.

Both content-addressed registries downloaded straight to the cache path and verified
afterwards::

    (downloader or _default_downloader)(url, path)
    _verify_sha256(path, expected)

A download that fails part-way — a dropped connection, a 502 from the mirror, a full
disk, a Ctrl-C — leaves a truncated file at exactly the path the next run tests with
``path.exists()``. That run skips the download, re-hashes what is there, and reports a
**hash mismatch**, which in this project's vocabulary means the artifact was tampered
with. It says so on every subsequent run, and never retries the download: one dropped
connection permanently bricks a checkpoint, with a message pointing at the wrong cause.

Downloading to a sibling temporary file, verifying *that*, and moving it into place only
once it hashes correctly makes the cache path appear only with correct content. The move
is ``os.replace``, which is atomic within a directory, so a concurrent reader sees either
the old file or the new one and never a partial write.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

__all__ = ["download_verified"]


def download_verified(
    url: str,
    dest: Path,
    *,
    downloader: Callable[[str, Path], None],
    verify: Callable[[Path], object],
) -> None:
    """Download ``url`` and put it at ``dest`` only if ``verify`` accepts it.

    Args:
        url: Where to fetch from.
        dest: The cache path the artifact must end up at.
        downloader: Writes the bytes at ``url`` to the path it is given. Injected by
            both registries so a test can supply the content without a network.
        verify: Called with the downloaded temporary file; raises to reject it.

    Raises:
        Exception: Whatever ``downloader`` or ``verify`` raises, after removing the
            temporary file — the point being that nothing is left at ``dest``.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A sibling, so the final move is a rename within one directory (atomic) rather than
    # a cross-device copy; the pid keeps two concurrent fetches of the same artifact from
    # writing over each other's partial file.
    tmp = dest.with_name(f"{dest.name}.partial-{os.getpid()}")
    try:
        downloader(url, tmp)
        verify(tmp)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, dest)
