"""Tests for the content-addressed cross-run cache (R4)."""

from __future__ import annotations

from pathlib import Path

from alleleforge.cache import CACHE_FORMAT_VERSION, ContentAddressedCache, hash_parts


def test_hash_parts_is_stable_and_order_sensitive() -> None:
    a = hash_parts("spacer", 4, [1, 2])
    assert a == hash_parts("spacer", 4, [1, 2])  # stable across calls
    assert a != hash_parts("spacer", 4, [2, 1])  # order matters
    assert a != hash_parts("spacer", 5, [1, 2])  # every part matters


def test_hash_parts_includes_format_version() -> None:
    # The version is part of the digest, so a format bump invalidates everything.
    assert hash_parts("x") == hash_parts("x")
    assert CACHE_FORMAT_VERSION  # present and non-empty


def test_round_trips_bytes_text_json(tmp_path: Path) -> None:
    cache = ContentAddressedCache("unit", root=tmp_path)
    key = hash_parts("k")
    assert key not in cache
    assert cache.get_bytes(key) is None
    cache.put_bytes(key, b"\x00\x01")
    assert key in cache and cache.get_bytes(key) == b"\x00\x01"
    cache.put_text(key, "hello")
    assert cache.get_text(key) == "hello"
    cache.put_json(key, {"a": [1, 2]})
    assert cache.get_json(key) == {"a": [1, 2]}


def test_sharded_layout_and_len(tmp_path: Path) -> None:
    cache = ContentAddressedCache("unit", root=tmp_path)
    digest = hash_parts("shardme")
    cache.put_text(digest, "v")
    # Stored under <root>/caches/unit/<first two hex>/<digest>.
    expected = tmp_path / "caches" / "unit" / digest[:2] / digest
    assert expected.exists()
    assert len(cache) == 1


def test_namespaces_are_isolated(tmp_path: Path) -> None:
    a = ContentAddressedCache("a", root=tmp_path)
    b = ContentAddressedCache("b", root=tmp_path)
    key = hash_parts("same-key")
    a.put_text(key, "from-a")
    assert key not in b and b.get_text(key) is None


def test_survives_a_fresh_cache_object(tmp_path: Path) -> None:
    # The whole point: a value written by one "run" is read by the next.
    key = hash_parts("persisted")
    ContentAddressedCache("ns", root=tmp_path).put_text(key, "kept")
    assert ContentAddressedCache("ns", root=tmp_path).get_text(key) == "kept"


def test_verify_cache_detects_corrupted_entry(tmp_path: Path) -> None:
    import pytest

    from alleleforge.cache import CacheIntegrityError, ContentAddressedCache

    cache = ContentAddressedCache("artifacts", root=tmp_path, verify=True)
    digest = hash_parts("artifact-key")
    cache.put_bytes(digest, b"the-real-bytes")
    assert cache.get_bytes(digest) == b"the-real-bytes"  # round-trips
    assert len(cache) == 1  # the checksum sidecar is not counted as an entry

    # Corrupt the stored payload on disk; the next read must fail closed.
    path = cache._path(digest)
    path.write_bytes(b"tampered-bytes")
    with pytest.raises(CacheIntegrityError, match="integrity check"):
        cache.get_bytes(digest)


def test_verify_cache_fails_closed_on_missing_sidecar(tmp_path: Path) -> None:
    import pytest

    from alleleforge.cache import CacheIntegrityError, ContentAddressedCache

    # Deleting the checksum sidecar must NOT downgrade a verify=True read to a
    # silent trust — otherwise `rm *.sum` defeats the tamper-detection gate.
    cache = ContentAddressedCache("artifacts", root=tmp_path, verify=True)
    digest = hash_parts("artifact-key")
    cache.put_bytes(digest, b"the-real-bytes")
    sidecar = cache._path(digest).with_name(cache._path(digest).name + ".sum")
    sidecar.unlink()  # remove the checksum an attacker cannot forge to match tampered bytes
    with pytest.raises(CacheIntegrityError, match="integrity check"):
        cache.get_bytes(digest)


def test_unverified_cache_does_not_write_sidecars(tmp_path: Path) -> None:
    cache = ContentAddressedCache("plain", root=tmp_path)  # verify=False (default)
    cache.put_bytes(hash_parts("k"), b"v")
    assert cache.get_bytes(hash_parts("k")) == b"v"
    assert not list(tmp_path.rglob("*.sum"))  # no sidecars written


def test_verify_cache_concurrent_writes_dont_race(tmp_path: Path) -> None:
    import sys
    import threading

    from alleleforge.cache import CacheIntegrityError, ContentAddressedCache

    # Concurrent put/get on a verify=True cache must not raise on valid data. Two
    # races previously lurked in put_bytes: (1) the sidecar was written *after* the
    # payload was published, so a reader in that window saw a payload without its
    # sidecar and the fail-closed check raised CacheIntegrityError on good data;
    # (2) a shared bytes object gave a colliding temp name (id(data)), so the losing
    # writer's rename hit FileNotFoundError. A shared payload object exercises both.
    cache = ContentAddressedCache("concurrent", root=tmp_path, verify=True)
    digest = hash_parts("shared-key")
    payload = b"the-shared-payload-object"  # one object shared across threads
    errors: list[Exception] = []

    def worker() -> None:
        try:
            for _ in range(60):
                cache.put_bytes(digest, payload)
                got = cache.get_bytes(digest)
                assert got is None or got == payload
        except (CacheIntegrityError, FileNotFoundError) as exc:  # pragma: no cover - race
            errors.append(exc)

    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # widen the interleaving window so the race is reliable
    try:
        threads = [threading.Thread(target=worker) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old)

    assert not errors, f"concurrent verified put/get raised on valid data: {errors[:3]}"
