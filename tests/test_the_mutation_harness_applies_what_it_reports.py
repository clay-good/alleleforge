"""The index a mutant is logged under must name the mutation that was applied.

`scripts/mutate.py` is the harness behind the method `openspec/changes/README.md`
records from Round 578 on. Its collector assigns an index to every mutable site and its
mutator applies the one at a given index; a *survivor* is then read as evidence about
that site. If the two disagree, the log is confidently wrong — not silent, wrong — and
every conclusion drawn from it is about a mutation that never ran.

That has happened three times, and each time cost a round's worth of reasoning about a
defect that did not exist:

* **Nested booleans.** The collector recorded a node's own sites before descending into
  its children; the mutator descended first. For `a and (b or c)` the inner `or`'s sites
  came back ahead of the outer `and`'s, so an index past the first nesting named a
  different mutation than it applied.
* **Closures.** In statement-deletion mode the mutator returned early from a function
  and never visited nested `def`s, while the collector did — so for a module with a
  closure the mutator ran out of sites early and reported them "invalid".
* **Both-ways operators.** `isinstance` and ordered-opposite swaps produce two mutants
  per site, and the pair has to stay in a fixed order for an index to mean anything.

So this file does not test that mutation finds bugs. It tests the one property the
harness's output rests on: for every mode, applying index *i* produces exactly the change
the collector described at index *i*. The fixtures are deliberately the shapes that
broke it — a nested boolean, a closure, a span with two ends.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_HARNESS = Path(__file__).resolve().parents[1] / "scripts" / "mutate.py"


@pytest.fixture(scope="module")
def harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_af_mutate", _HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_af_mutate"] = module
    spec.loader.exec_module(module)
    return module


#: A nested boolean, a closure, a two-ended span, a type guard and a literal — every
#: shape that has broken the index mapping, in one module.
_SOURCE = '''
def outer(a, b, c, iv, d, strict=True, *, verify=True, quiet=False):
    """Doc."""
    out = []
    if a > 0 and (b or c):
        out.append("x")
    if isinstance(a, str):
        out.append("y")

    def inner(y, loud=False):
        out.append("z")
        return y

    return f"{d.low}-{d.high} {iv[0]}..{iv[1]} {len(out)} {inner(1)}"
'''


def _sites(harness: ModuleType, mode: str) -> list[tuple[str, int, str]]:
    collector = harness.Collector(mode)
    collector.visit(ast.parse(_SOURCE))
    return list(collector.sites)


def _applied(harness: ModuleType, mode: str, index: int) -> str:
    mutator = harness.Mutator(mode, index)
    tree = mutator.visit(ast.parse(_SOURCE))
    assert mutator.applied, f"{mode}[{index}] applied nothing"
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


@pytest.mark.parametrize("mode", ["ops", "const", "conj", "del", "side", "isinst", "pair", "dflt"])
def test_every_site_the_collector_reports_can_be_applied(harness: ModuleType, mode: str) -> None:
    """The floor: an index that applies nothing is an index that measured nothing."""
    sites = _sites(harness, mode)
    assert sites, f"{mode} found no sites in a module written to contain them"
    for index in range(len(sites)):
        mutant = _applied(harness, mode, index)
        assert mutant != _SOURCE.strip(), f"{mode}[{index}] changed nothing"


@pytest.mark.parametrize("mode", ["ops", "const", "conj", "del", "side", "isinst", "pair", "dflt"])
def test_each_index_changes_the_source_differently(harness: ModuleType, mode: str) -> None:
    """Two indices producing one mutant means the numbering collapsed somewhere."""
    sites = _sites(harness, mode)
    seen: dict[str, int] = {}
    for index in range(len(sites)):
        mutant = _applied(harness, mode, index)
        if mutant in seen:
            pytest.fail(
                f"{mode}[{index}] and {mode}[{seen[mutant]}] produce the same mutant: "
                f"{sites[index]} vs {sites[seen[mutant]]}"
            )
        seen[mutant] = index


def test_a_nested_boolean_numbers_the_outer_operand_first(harness: ModuleType) -> None:
    """`a > 0 and (b or c)`: the outer `and` before the inner `or`, in both halves."""
    sites = [s for s in _sites(harness, "conj") if "And" in s[2] or "Or" in s[2]]
    labels = [s[2] for s in sites]
    assert labels[:2] == ["And drop#0/2", "And drop#1/2"], labels
    assert labels[2:4] == ["Or drop#0/2", "Or drop#1/2"], labels

    # Dropping the outer `and`'s second operand removes the whole parenthesised group.
    assert "if a > 0:" in _applied(harness, "conj", 1)
    # Dropping the inner `or`'s first operand leaves the outer `and` intact.
    assert "if a > 0 and c:" in _applied(harness, "conj", 2)


def test_a_closure_is_reached_in_deletion_mode(harness: ModuleType) -> None:
    """The mutator must descend into nested defs, or it runs out of sites early."""
    sites = _sites(harness, "side")
    inner = [i for i, s in enumerate(sites) if "z" in s[2]]
    assert inner, f"the closure's append was never collected: {[s[2] for s in sites]}"
    mutant = _applied(harness, "side", inner[0])
    assert "'z'" not in mutant and '"z"' not in mutant, mutant
    assert "'x'" in mutant and "'y'" in mutant, "it deleted the wrong append"


def test_a_type_guard_is_forced_both_ways_in_a_fixed_order(harness: ModuleType) -> None:
    sites = _sites(harness, "isinst")
    assert [s[2].split()[0] for s in sites] == ["always-True", "always-False"], sites
    assert "if True:" in _applied(harness, "isinst", 0)
    assert "if False:" in _applied(harness, "isinst", 1)


def test_an_ordered_opposite_swap_touches_only_its_own_member(harness: ModuleType) -> None:
    """`d.low -> high` must not also rewrite `d.high`, or the pair is unobservable."""
    sites = _sites(harness, "pair")
    labels = [s[2] for s in sites]
    assert "d.low -> 'high'" in labels, labels
    mutant = _applied(harness, "pair", labels.index("d.low -> 'high'"))
    assert "{d.high}-{d.high}" in mutant, mutant


def test_an_index_past_the_last_site_applies_nothing(harness: ModuleType) -> None:
    """A run that silently applied *something* for an out-of-range index would be worse."""
    sites = _sites(harness, "conj")
    mutator = harness.Mutator("conj", len(sites) + 5)
    mutator.visit(ast.parse(_SOURCE))
    assert not mutator.applied


def test_the_default_log_stays_out_of_the_repository_root(harness: ModuleType) -> None:
    """A counting run once wrote `mutants.log` into the root, failing a root guard twice."""
    import inspect

    source = inspect.getsource(harness.main)
    assert 'default=str(HERE / "mutants.log")' in source, (
        "the default log path must be beside the script, not the working directory"
    )


def test_a_boolean_default_is_flipped_only_in_its_own_slot(harness: ModuleType) -> None:
    """`defaults` right-aligns against the parameter list, which is the trap here.

    `outer(a, b, c, iv, d, strict=True, *, verify=True, quiet=False)` has five
    parameters with no default and three with one. Zipping `args.args` against
    `args.defaults` from the left would pair `strict`'s default with `a`, so the index
    would name a parameter the mutator did not touch -- the same class of defect as the
    three the rest of this file pins.
    """
    sites = _sites(harness, "dflt")
    assert [detail for _, _, detail in sites] == [
        "outer(strict=True -> False)",
        "outer(verify=True -> False)",
        "outer(quiet=False -> True)",
        "inner(loud=False -> True)",
    ]


def test_each_flipped_default_changes_only_that_parameter(harness: ModuleType) -> None:
    """A flip that moved another parameter's default would be measured as this one's."""
    expected = [
        ("strict=False", "verify=True", "quiet=False"),
        ("strict=True", "verify=False", "quiet=False"),
        ("strict=True", "verify=True", "quiet=True"),
    ]
    for index, signature in enumerate(expected):
        mutant = _applied(harness, "dflt", index)
        for fragment in signature:
            assert fragment in mutant, f"dflt[{index}] lost {fragment}"
        assert "loud=False" in mutant, "the closure's default must be untouched"


def test_a_closure_default_is_reached(harness: ModuleType) -> None:
    """Deletion mode once skipped closures entirely; the same walk feeds this mode."""
    mutant = _applied(harness, "dflt", 3)
    assert "loud=True" in mutant
    assert "strict=True" in mutant and "verify=True" in mutant and "quiet=False" in mutant
