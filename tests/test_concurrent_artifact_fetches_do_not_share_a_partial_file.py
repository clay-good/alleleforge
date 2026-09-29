"""Concurrent artifact fetches must not write the same temporary file.

The shared dataset/model downloader once named a partial file with only the process ID.
That separates processes, but every thread in one process received the same path. A
parallel first load or refresh could therefore replace the file while its sibling was
still verifying it, or verify bytes written by the other transfer.
"""

from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from alleleforge._fetch import download_verified


def test_concurrent_fetches_use_distinct_sibling_files(tmp_path: Path) -> None:
    payload = b"verified artifact"
    digest = hashlib.sha256(payload).hexdigest()
    destination = tmp_path / "artifact.bin"
    barrier = threading.Barrier(2)
    partials: list[Path] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def downloader(url: str, partial: Path) -> None:
        with lock:
            partials.append(partial)
        barrier.wait()
        partial.write_bytes(payload)

    def verify(partial: Path) -> None:
        assert hashlib.sha256(partial.read_bytes()).hexdigest() == digest

    def fetch() -> None:
        try:
            download_verified(
                "https://example.invalid/artifact.bin",
                destination,
                downloader=downloader,
                verify=verify,
            )
        except Exception as exc:  # the assertion below reports both workers together
            with lock:
                errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fetch) for _ in range(2)]
        for future in futures:
            future.result()

    assert len(set(partials)) == 2, partials
    assert not errors, errors
    assert destination.read_bytes() == payload
    assert not list(tmp_path.glob("*.partial-*"))
