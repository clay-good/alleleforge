"""Direct tests of the content-hashing primitive split integrity rests on.

`_canon` is the single definition of "how an object becomes bytes" that the
generator minting a frozen split and the loader verifying it must agree on. It is
reached almost entirely through those two callers, which exercise the shapes they
happen to produce; its actual contract is broader, and every clause of it is a
claim about *bytes* rather than about values:

* logically equal objects hash identically regardless of key insertion order;
* the same object hashes identically across processes (so a split minted today
  verifies tomorrow, under a different `PYTHONHASHSEED`);
* `reproducibility_digest` additionally tolerates a last-ULP float difference, so
  two platforms agree on a re-derivation, while still separating genuinely
  different numbers.

A silent break in any of these does not raise — it makes a frozen split fail to
verify, or worse, makes two different results claim to be the same re-derivation.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from alleleforge.benchmark._canon import (
    DIGEST_FLOAT_PRECISION,
    canonical_json,
    content_hash,
    reproducibility_digest,
)


def test_key_order_does_not_change_the_hash() -> None:
    """The stated invariant: logically equal objects serialize to identical bytes."""
    a = {"b": 1, "a": {"z": [1, 2], "y": "x"}, "c": True}
    b = {"c": True, "a": {"y": "x", "z": [1, 2]}, "b": 1}
    assert canonical_json(a) == canonical_json(b)
    assert content_hash(a) == content_hash(b)


def test_list_order_does_change_the_hash() -> None:
    """Order-independence applies to mappings, not sequences — a split's membership
    list is ordered, and reordering it is a real difference."""
    assert content_hash([1, 2]) != content_hash([2, 1])


def test_a_different_value_changes_the_hash() -> None:
    """The seal has to actually seal."""
    assert content_hash({"a": 1}) != content_hash({"a": 2})
    assert content_hash({"a": 1}) != content_hash({"a": "1"})
    assert content_hash({"a": 1}) != content_hash({"b": 1})


def test_no_insignificant_whitespace() -> None:
    assert canonical_json({"a": [1, 2]}) == '{"a":[1,2]}'


def test_non_ascii_survives_round_trip() -> None:
    """`ensure_ascii=False` writes UTF-8 directly; it must still decode to the same
    object, or a split with a non-ASCII label would hash to something unloadable."""
    obj = {"citation": "Doudna & Charpentier — 2012", "gene": "CFTR"}
    assert json.loads(canonical_json(obj)) == obj


@pytest.mark.parametrize("seed", ["0", "1", "42"])
def test_the_hash_is_stable_across_hash_seeds(seed: str) -> None:
    """A split minted in one process must verify in another.

    `PYTHONHASHSEED` randomizes dict and set iteration order per process. If the
    canonical form ever depended on it, a frozen split would verify on the machine
    that made it and fail everywhere else — intermittently.
    """
    program = (
        "import sys; sys.path.insert(0, 'src');"
        "from alleleforge.benchmark._canon import content_hash;"
        "print(content_hash({'b': [3, {'d': 4, 'c': 5}], 'a': 1, 'e': {'g': 6, 'f': 7}}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
    )
    expected = content_hash({"b": [3, {"d": 4, "c": 5}], "a": 1, "e": {"g": 6, "f": 7}})
    assert out.stdout.strip() == expected


def test_the_reproducibility_digest_absorbs_a_last_ulp_difference() -> None:
    """Two platforms differing only in the last bit must agree on a re-derivation."""
    body = {"metrics": {"kl": 0.1234567890123, "spearman": 0.5}}
    nudged = {"metrics": {"kl": 0.1234567890123 + 1e-12, "spearman": 0.5}}
    assert reproducibility_digest(body) == reproducibility_digest(nudged)
    # ...but it is a tolerance, not a blur: a real difference still separates.
    bigger = {
        "metrics": {"kl": 0.1234567890123 + 10 ** -(DIGEST_FLOAT_PRECISION - 1), "spearman": 0.5}
    }
    assert reproducibility_digest(body) != reproducibility_digest(bigger)


def test_the_reproducibility_digest_rounds_nested_floats() -> None:
    """Rounding must reach floats inside lists and nested mappings, not just the top."""
    a = {"rows": [{"v": 1.0000000001}, {"v": [2.0000000001]}]}
    b = {"rows": [{"v": 1.0}, {"v": [2.0]}]}
    assert reproducibility_digest(a) == reproducibility_digest(b)


def test_the_two_digests_are_not_interchangeable() -> None:
    """`content_hash` is a tamper seal over exact bytes; the reproducibility digest
    deliberately discards precision. Conflating them would let a tamper check pass
    on a body that had been rounded."""
    body = {"metrics": {"kl": 0.1234567890123}}
    assert content_hash(body) != reproducibility_digest(body)
