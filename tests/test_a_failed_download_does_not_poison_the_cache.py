"""A download that fails part-way used to brick a pinned artifact permanently.

Both content-addressed registries fetched straight to the cache path and verified after::

    (downloader or _default_downloader)(url, path)
    _verify_sha256(path, expected)

A dropped connection, a 502 from the mirror, a full disk or a Ctrl-C leaves a truncated
file at exactly the path the next run tests with `path.exists()`. That run skips the
download, re-hashes what is there, and raises `ChecksumError` — which in this project's
vocabulary means the artifact was **tampered with**. It says so on every subsequent run and
never retries the download, so one network blip costs a checkpoint forever and points the
reader at the wrong cause.

Downloading to a sibling temporary file and moving it into place only once it hashes
correctly means the cache path appears only with correct content.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from alleleforge.data.registry import DatasetDescriptor, DatasetRegistry
from alleleforge.errors import ChecksumError
from alleleforge.model_zoo.registry import ModelCard, ModelRegistry
from alleleforge.types.provenance import ModelUse

_GOOD = b"a checkpoint's worth of bytes"
_SHA = hashlib.sha256(_GOOD).hexdigest()


def _card() -> ModelCard:
    return ModelCard(
        name="toy",
        version="1",
        task="cas9-efficiency",
        chemistry="cas9_nuclease",
        source_url="https://example.invalid/toy.ckpt",
        checkpoint_sha256=_SHA,
        license="MIT",
        citation="none",
        intended_use="a test",
        out_of_scope_use="anything else",
        known_failure_modes=("it is not a model",),
        training_data="none",
    )


def _registry() -> ModelRegistry:
    reg = ModelRegistry()
    reg.register(_card())
    return reg


def _fetch(reg: ModelRegistry, cache: Path, downloader: object) -> Path:
    path, _record = reg.checkpoint(
        "toy",
        cache_dir=cache,
        consent=True,
        use=ModelUse.RESEARCH,
        downloader=downloader,  # type: ignore[arg-type]
    )
    return path


def test_a_connection_that_drops_leaves_nothing_behind(tmp_path: Path) -> None:
    def half_a_download(url: str, dest: Path) -> None:
        dest.write_bytes(_GOOD[:10])
        raise ConnectionError("connection reset by peer")

    with pytest.raises(ConnectionError):
        _fetch(_registry(), tmp_path, half_a_download)

    # The cache path must not exist, and no partial file may be left lying beside it.
    assert not (tmp_path / "toy.1.ckpt").exists()
    assert list(tmp_path.glob("*")) == []


def test_a_truncated_but_complete_download_is_rejected_without_caching_it(
    tmp_path: Path,
) -> None:
    """The mirror answered, the bytes were wrong. Same requirement: nothing cached."""

    def wrong_bytes(url: str, dest: Path) -> None:
        dest.write_bytes(b"an error page from a captive portal")

    with pytest.raises(ChecksumError):
        _fetch(_registry(), tmp_path, wrong_bytes)
    assert not (tmp_path / "toy.1.ckpt").exists()
    assert list(tmp_path.glob("*")) == []


def test_the_next_attempt_succeeds_rather_than_reporting_tampering(tmp_path: Path) -> None:
    """The whole point: a blip costs one retry, not the artifact.

    Before, the second call found the first call's truncated file, skipped the download,
    and raised `ChecksumError` — forever.
    """
    reg = _registry()

    def half_a_download(url: str, dest: Path) -> None:
        dest.write_bytes(_GOOD[:10])
        raise TimeoutError("read timed out")

    with pytest.raises(TimeoutError):
        _fetch(reg, tmp_path, half_a_download)

    def a_good_download(url: str, dest: Path) -> None:
        dest.write_bytes(_GOOD)

    path = _fetch(reg, tmp_path, a_good_download)
    assert path.read_bytes() == _GOOD


def test_a_cached_artifact_is_still_reused(tmp_path: Path) -> None:
    """The fix must not turn every resolve into a re-download."""
    reg = _registry()
    calls: list[str] = []

    def counted(url: str, dest: Path) -> None:
        calls.append(url)
        dest.write_bytes(_GOOD)

    _fetch(reg, tmp_path, counted)
    _fetch(reg, tmp_path, counted)
    assert len(calls) == 1


def _dataset_registry() -> DatasetRegistry:
    reg = DatasetRegistry()
    reg.register(
        DatasetDescriptor(
            name="toy-data",
            version="1",
            source_url="https://example.invalid/toy.tsv",
            license="CC0",
            sha256=_SHA,
            citation="none",
            filename="toy.tsv",
        )
    )
    return reg


def test_the_dataset_registry_has_the_same_guarantee(tmp_path: Path) -> None:
    """The two registries are the same code twice; a fix to one is a fix to neither."""
    reg = _dataset_registry()

    def half_a_download(url: str, dest: Path) -> None:
        dest.write_bytes(_GOOD[:10])
        raise ConnectionError("connection reset by peer")

    with pytest.raises(ConnectionError):
        reg.resolve("toy-data", cache_dir=tmp_path, consent=True, downloader=half_a_download)  # type: ignore[arg-type]
    assert list(tmp_path.rglob("*.tsv")) == []
    assert not any(p.is_file() for p in tmp_path.rglob("*"))

    def a_good_download(url: str, dest: Path) -> None:
        dest.write_bytes(_GOOD)

    path, _version = reg.resolve(
        "toy-data", cache_dir=tmp_path, consent=True, downloader=a_good_download
    )  # type: ignore[arg-type]
    assert path.read_bytes() == _GOOD


def test_the_cache_path_never_holds_a_partial_write(tmp_path: Path) -> None:
    """Not only afterwards: *during* the download the cache path must not exist.

    Cleaning up on failure is not enough on its own. A second process resolving the same
    artifact while the first is mid-download tests `path.exists()`, and a download writing
    straight to the cache path makes that true from the first byte — so the reader skips
    the download and hashes a file still being written.
    """
    dest = tmp_path / "toy.1.ckpt"
    seen: list[bool] = []

    def a_slow_download(url: str, target: Path) -> None:
        target.write_bytes(_GOOD[:10])
        seen.append(dest.exists())  # what a concurrent reader would see
        target.write_bytes(_GOOD)

    _fetch(_registry(), tmp_path, a_slow_download)
    assert seen == [False]
    assert dest.read_bytes() == _GOOD
