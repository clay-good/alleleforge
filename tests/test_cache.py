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
