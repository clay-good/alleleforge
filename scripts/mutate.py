#!/usr/bin/env python3
"""Mutation-testing harness: change the source, run the suite, see what notices.

This is the method `openspec/changes/README.md` records from Round 578 onward. Reading
code went dry; mutating it found a defect almost every round. Four operators have been
built here and each is exhausted repo-wide, so a fifth needs a new hypothesis rather
than a longer list — but the harness is kept because every pass needs it again, and
because rebuilding it from scratch has three times produced a *wrong answer* rather than
no answer.

Operators (``--mode``), each asking a different question:

``ops``
    Swap a comparison, arithmetic or boolean operator. *Is this computation pinned?*
``const``
    Perturb a literal (``n -> n+1``, ``x -> 1.1x``, ``True -> False``). *Is this
    threshold pinned to its source?* Zero floats are skipped: ``0.0 * 1.1`` is not a
    mutant.
``conj``
    Drop one operand of an ``and``/``or`` chain. *Is this condition's other arm tested?*
    For N guards, a fixture where the other N-1 still fire measures nothing.
``del`` / ``side``
    Delete one statement. ``side`` restricts to statements whose *effect* is the point —
    a bare call, a write into a collection — because deleting an ordinary assignment is
    a ``NameError`` on the next line, which measures the interpreter. *Does anything
    observe that this ran?* This is the operator that reaches resources, report
    completeness, output order and liveness.
``isinst``
    Force an ``isinstance`` call to ``True`` and to ``False`` in turn. *Which side of
    this type guard does a fixture supply?* **When both answers survive, the predicate
    is inert, not untested** — one answer surviving is a missing fixture.
``pair``
    Swap a member for its ordered opposite (``start``/``end``, ``low``/``high``,
    ``ref``/``alt``, subscript ``0``/``1``) where the opposite is read off the same
    receiver in the same function. Confusing two *unrelated* fields explodes on the
    first assertion; confusing the two ends of one span stays plausible and silent,
    which is the class this project has shipped more than once.

Three traps, each of which cost a wrong answer and each of which
``tests/test_the_mutation_harness_applies_what_it_reports.py`` now pins:

1. **The collector and the mutator must number sites in the same order.** Both record a
   node's own sites *before* descending. Getting that wrong meant an index named one
   mutation and applied another — once for nested ``BoolOp`` (``a and (b or c)``), once
   for closures in ``del``/``side`` mode.
2. **A failing test manufactures kills.** The run exits non-zero whatever the mutation
   did, so every mutant in that file reports "killed". Run the chosen list green first.
3. **A narrow test list is a filter, not evidence.** Survivors against a module's own
   directory are routinely 50-100% phantom; confirm each against the whole suite before
   reading it as a gap. The phantom rate tracks the module's audience — near zero for a
   pure type, near total for a shell or a renderer.

Usage::

    python scripts/mutate.py --target src/alleleforge/x.py --tests "tests/x" --mode conj
    python scripts/mutate.py --target src/alleleforge/x.py --tests x --mode conj --only 0

``--only 0`` lists the sites without running anything. ``--index 3,7`` re-runs chosen
mutants, which is how a survivor is confirmed against a broader list. The log defaults
into this script's own directory, never the repository root, which a root-contents guard
failed on twice.

Nothing here is part of the shipped package: it mutates a working tree and restores it,
and it traps ``SIGTERM`` so a killed run does not leave the source rewritten. Check
``git diff --stat src/`` after any interrupted sweep.
"""

from __future__ import annotations

import argparse
import ast
import os
import pathlib
import re
import signal
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent

CMP_SWAP = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
BIN_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Div,
}
BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


def _clone(tree: ast.AST) -> ast.AST:
    return ast.parse(ast.unparse(tree))


def _default_sites(fn: ast.AST) -> list[tuple[str, bool]]:
    """Return ``(parameter, current)`` for every boolean default in ``fn``'s signature.

    A boolean keyword default is a *decision the caller did not make*, which is what
    makes it the project's recurring defect shape: a safety posture (`verify=True`,
    `consent=True`, `strict=True`) that every call site inherits silently, so nothing
    fails when it is wrong. `const` mode reaches these too, but it fires on every int
    and float as well and buries them; this operator asks only the one question.

    Positional and keyword-only defaults are walked in signature order so the index is
    stable, and `*args`/`**kwargs` carry no defaults to flip.
    """
    args = getattr(fn, "args", None)
    if args is None:
        return []
    out: list[tuple[str, bool]] = []
    positional = [*getattr(args, "posonlyargs", []), *args.args]
    # `defaults` right-aligns against the positional parameters.
    for arg, default in zip(
        positional[len(positional) - len(args.defaults) :], args.defaults, strict=True
    ):
        if isinstance(default, ast.Constant) and isinstance(default.value, bool):
            out.append((arg.arg, default.value))
    for arg, kw_default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        if isinstance(kw_default, ast.Constant) and isinstance(kw_default.value, bool):
            out.append((arg.arg, kw_default.value))
    return out


class Collector(ast.NodeVisitor):
    """Assign a stable index to every mutable site."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.sites: list[tuple[str, int, str]] = []  # (kind, lineno, detail)

    def visit_Compare(self, node: ast.Compare) -> None:
        if self.mode == "ops":
            for i, op in enumerate(node.ops):
                if type(op) in CMP_SWAP:
                    self.sites.append(("cmp", node.lineno, f"{type(op).__name__}#{i}"))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if self.mode == "ops" and type(node.op) in BIN_SWAP:
            self.sites.append(("bin", node.lineno, type(node.op).__name__))
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if self.mode == "ops":
            self.sites.append(("bool", node.lineno, type(node.op).__name__))
        elif self.mode == "conj":
            for i in range(len(node.values)):
                self.sites.append(
                    ("conj", node.lineno, f"{type(node.op).__name__} drop#{i}/{len(node.values)}")
                )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self.mode in ("del", "side"):
            self._body_sites(node)
        elif self.mode == "pair":
            self._pair_body(node)
        elif self.mode == "dflt":
            self._default_body(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self.mode in ("del", "side"):
            self._body_sites(node)
        elif self.mode == "pair":
            self._pair_body(node)
        elif self.mode == "dflt":
            self._default_body(node)
        self.generic_visit(node)

    def _body_sites(self, fn: ast.AST) -> None:
        """One site per deletable statement in this function, in source order.

        Only statements whose removal leaves valid, non-trivial code: a docstring is
        not a statement anyone observes, and a lone `pass` deletes to nothing.
        """
        for stmt in _deletable(fn, side_only=self.mode == "side"):
            self.sites.append((self.mode, stmt.lineno, _describe(stmt)))

    def _default_body(self, fn: ast.AST) -> None:
        name = getattr(fn, "name", "?")
        for param, current in _default_sites(fn):
            self.sites.append(("dflt", fn.lineno, f"{name}({param}={current} -> {not current})"))

    def _pair_body(self, fn: ast.AST) -> None:
        for receiver, kind, name, other in _pair_sites(fn):
            where = f"{receiver}.{name}" if kind == "attr" else f"{receiver}[{name!r}]"
            self.sites.append(("pair", fn.lineno, f"{where} -> {other!r}"))

    def visit_Call(self, node: ast.Call) -> None:
        if self.mode == "isinst" and _is_isinstance(node):
            label = _describe(ast.Expr(value=node)).removeprefix("isinstance")
            self.sites.append(("isinst", node.lineno, f"always-True {label}"))
            self.sites.append(("isinst", node.lineno, f"always-False {label}"))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if self.mode == "const":
            v = node.value
            if isinstance(v, bool):
                self.sites.append(("const", node.lineno, f"bool {v}"))
            elif isinstance(v, int):
                self.sites.append(("const", node.lineno, f"int {v}"))
            elif isinstance(v, float) and v != 0.0:
                self.sites.append(("const", node.lineno, f"float {v}"))
        self.generic_visit(node)


class Mutator(ast.NodeTransformer):
    """Apply exactly the site at `target`."""

    def __init__(self, mode: str, target: int) -> None:
        self.mode = mode
        self.target = target
        self.n = -1
        self.applied = False

    def _hit(self) -> bool:
        self.n += 1
        return self.n == self.target

    # NOTE: the Collector records a node's own sites BEFORE descending into its
    # children. The Mutator must number them in the same order or the index means a
    # different site -- which it did for NESTED BoolOps (`a > 0 and (b or c)`), where
    # descending first put the inner Or's sites ahead of the outer And's.
    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if self.mode == "ops":
            for i, op in enumerate(node.ops):
                if type(op) in CMP_SWAP and self._hit():
                    node.ops[i] = CMP_SWAP[type(op)]()
                    self.applied = True
                    return node
        self.generic_visit(node)
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if self.mode == "ops" and type(node.op) in BIN_SWAP and self._hit():
            node.op = BIN_SWAP[type(node.op)]()
            self.applied = True
            return node
        self.generic_visit(node)
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        if self.mode == "ops":
            if self._hit():
                node.op = BOOL_SWAP[type(node.op)]()
                self.applied = True
                return node
        elif self.mode == "conj":
            for i in range(len(node.values)):
                if self._hit():
                    kept = [v for j, v in enumerate(node.values) if j != i]
                    self.applied = True
                    # A 1-operand BoolOp is invalid AST: splice in the survivor.
                    return kept[0] if len(kept) == 1 else ast.BoolOp(op=node.op, values=kept)
        self.generic_visit(node)
        return node

    # NOTE: the Collector records a function's own statements and THEN descends into
    # nested defs. Returning early here skipped every closure, so for a module with
    # one the Mutator's numbering ran ahead of the Collector's and an index named a
    # statement that was never deleted. Count ours, then descend.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if self.mode in ("del", "side"):
            self._delete_in(node)
            if not self.applied:
                self.generic_visit(node)
            return node
        if self.mode == "pair":
            self._pair_in(node)
            if not self.applied:
                self.generic_visit(node)
            return node
        if self.mode == "dflt":
            self._default_in(node)
            if not self.applied:
                self.generic_visit(node)
            return node
        self.generic_visit(node)
        return node

    def _default_in(self, fn: ast.AST) -> None:
        """Flip the targeted boolean default in ``fn``'s signature."""
        args = getattr(fn, "args", None)
        if args is None:
            return
        positional = [*getattr(args, "posonlyargs", []), *args.args]
        slots = [
            *zip(positional[len(positional) - len(args.defaults) :], args.defaults, strict=True),
            *zip(args.kwonlyargs, args.kw_defaults, strict=True),
        ]
        for _arg, default in slots:
            if not (isinstance(default, ast.Constant) and isinstance(default.value, bool)):
                continue
            if self._hit():
                default.value = not default.value
                self.applied = True
                return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        if self.mode in ("del", "side"):
            self._delete_in(node)
            if not self.applied:
                self.generic_visit(node)
            return node
        if self.mode == "pair":
            self._pair_in(node)
            if not self.applied:
                self.generic_visit(node)
            return node
        self.generic_visit(node)
        return node

    def _delete_in(self, fn: ast.AST) -> None:
        for stmt in _deletable(fn, side_only=self.mode == "side"):
            if self._hit():
                _remove(fn, stmt)
                self.applied = True
                return

    def _pair_in(self, fn: ast.AST) -> None:
        """Apply the targeted (receiver, member -> other) swap inside ``fn``."""
        for receiver, kind, name, other in _pair_sites(fn):
            if not self._hit():
                continue
            for node in ast.walk(fn):
                if (
                    kind == "attr"
                    and isinstance(node, ast.Attribute)
                    and isinstance(node.ctx, ast.Load)
                    and node.attr == name
                    and _receiver(node.value) == receiver
                ):
                    node.attr = other
                    self.applied = True
                elif (
                    kind in ("key", "index")
                    and isinstance(node, ast.Subscript)
                    and isinstance(node.ctx, ast.Load)
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value == name
                    and _receiver(node.value) == receiver
                ):
                    node.slice = ast.Constant(value=other)
                    self.applied = True
            return

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Force a type guard's answer, to ask which side of it a fixture supplies."""
        if self.mode == "isinst" and _is_isinstance(node):
            for value in (True, False):
                if self._hit():
                    self.applied = True
                    return ast.Constant(value=value)
        self.generic_visit(node)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if self.mode != "const":
            return node
        v = node.value
        if isinstance(v, bool):
            if self._hit():
                self.applied = True
                return ast.Constant(value=not v)
        elif isinstance(v, int):
            if self._hit():
                self.applied = True
                return ast.Constant(value=v + 1)
        elif isinstance(v, float) and v != 0.0:
            if self._hit():
                self.applied = True
                return ast.Constant(value=v * 1.1)
        return node


def _bodies(fn: ast.AST) -> list[list[ast.stmt]]:
    """Every statement list inside ``fn``, including nested blocks but not nested defs."""
    out: list[list[ast.stmt]] = []

    def walk(node: ast.AST) -> None:
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                out.append(block)
                for child in block:
                    if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                        walk(child)
        for handler in getattr(node, "handlers", []):
            walk(handler)

    walk(fn)
    return out


def _is_side_effect(stmt: ast.stmt) -> bool:
    """Whether deleting ``stmt`` removes an effect rather than a value.

    A bare call (`notes.append(...)`, `warnings.warn(...)`) and a write into a
    collection (`provenance["seed"] = seed`) are recorded somewhere and read somewhere
    *else*, which is the shape this project keeps finding broken: a value computed,
    stored, and never looked at. An ordinary assignment is consumed on the next line
    and its deletion is a NameError, which measures nothing.
    """
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return True
    if isinstance(stmt, ast.Assign) and all(
        isinstance(t, ast.Subscript | ast.Attribute) for t in stmt.targets
    ):
        return True
    return isinstance(stmt, ast.AugAssign) and isinstance(
        stmt.target, ast.Subscript | ast.Attribute
    )


def _deletable(fn: ast.AST, *, side_only: bool = False) -> list[ast.stmt]:
    """Statements in ``fn`` whose deletion is a meaningful mutant, in source order."""
    out: list[ast.stmt] = []
    for block in _bodies(fn):
        for stmt in block:
            if isinstance(stmt, ast.Pass):
                continue
            if (
                block is getattr(fn, "body", None)
                and stmt is block[0]
                and isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                continue  # the docstring
            if side_only and not _is_side_effect(stmt):
                continue
            out.append(stmt)
    out.sort(key=lambda s: (s.lineno, s.col_offset))
    return out


def _remove(fn: ast.AST, target: ast.stmt) -> None:
    """Drop ``target`` from whichever block holds it, leaving `pass` if it empties."""
    for block in _bodies(fn):
        for i, stmt in enumerate(block):
            if stmt is target:
                del block[i]
                if not block:
                    block.append(ast.Pass())
                return


def _describe(stmt: ast.stmt) -> str:
    """A short label for a deleted statement, for the log."""
    try:
        text = ast.unparse(stmt).splitlines()[0]
    except Exception:  # noqa: BLE001
        text = type(stmt).__name__
    return (text[:70] + "...") if len(text) > 70 else text


def _is_isinstance(node: ast.Call) -> bool:
    """Whether ``node`` is a bare ``isinstance(x, T)`` call."""
    return isinstance(node.func, ast.Name) and node.func.id == "isinstance"


def _receiver(node: ast.AST) -> str:
    """The unparsed receiver expression, so two accesses on the same object pair up."""
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 - an unparseable receiver simply does not pair
        return "<?>"


#: Ordered opposites. A swap inside one of these pairs is the defect class this project
#: has already shipped twice — an interval printed low-for-high, a coordinate lift
#: reporting a haplotype off-target three bases from where it is. Confusing two *unrelated*
#: fields usually explodes; confusing two ends of one span stays plausible and silent,
#: which is exactly what makes it worth a mutant.
_OPPOSITES: tuple[tuple[str, str], ...] = (
    ("low", "high"),
    ("start", "end"),
    ("min", "max"),
    ("first", "last"),
    ("ref", "alt"),
    ("top", "bottom"),
    ("source", "target"),
    ("left", "right"),
    ("before", "after"),
    ("train", "test"),
    ("5prime", "3prime"),
    ("sense", "antisense"),
    ("forward", "reverse"),
    ("plus", "minus"),
    ("lower", "upper"),
)


def _opposite(name: str) -> str | None:
    """Return ``name`` with one ordered-opposite token flipped, or ``None``.

    Token-wise rather than substring: `start`/`end` must not turn `restart` into
    `reend`, and `interval_low`/`interval_high` must pair while `glow` does not.
    """
    parts = re.split(r"([_0-9]+)", name)
    for index, part in enumerate(parts):
        low = part.lower()
        for a, b in _OPPOSITES:
            if low == a or low == b:
                other = b if low == a else a
                swapped = list(parts)
                swapped[index] = other.upper() if part.isupper() else other
                return "".join(swapped)
    return None


def _receiver_members(fn: ast.AST) -> dict[str, set[tuple[str, object]]]:
    """Map each receiver in ``fn`` to the (kind, member) loads read off it."""
    out: dict[str, set[tuple[str, object]]] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            out.setdefault(_receiver(node.value), set()).add(("attr", node.attr))
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Load)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str | int)
            and not isinstance(node.slice.value, bool)
        ):
            kind = "key" if isinstance(node.slice.value, str) else "index"
            out.setdefault(_receiver(node.value), set()).add((kind, node.slice.value))
    return out


def _pair_sites(fn: ast.AST) -> list[tuple[str, str, object, object]]:
    """One site per (receiver, member -> its ordered opposite) swap.

    Restricted three ways, because the unrestricted version produced eleven thousand
    mutants of which almost all swap two unrelated fields and die instantly:

    * only *within* an ordered-opposite pair (``low``/``high``, ``start``/``end``, …),
      or between subscript ``0`` and ``1`` — the two ends of one span;
    * only on the *same receiver*, so two fields of one object pair up and two fields of
      different objects do not;
    * only when the opposite is itself read somewhere in the same function, which is what
      makes the swap a confusion a reader could plausibly have written.
    """
    sites: list[tuple[str, str, object, object]] = []
    for receiver, members in sorted(_receiver_members(fn).items()):
        for kind, member in sorted(members, key=lambda m: (m[0], str(m[1]))):
            if kind == "index":
                other: object | None = 1 if member == 0 else (0 if member == 1 else None)
            else:
                other = _opposite(str(member))
            if other is None or (kind, other) not in members:
                continue
            sites.append((receiver, kind, member, other))
    return sites


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--tests", required=True)
    ap.add_argument(
        "--mode",
        default="conj",
        choices=["ops", "const", "conj", "del", "side", "isinst", "pair", "dflt"],
    )
    ap.add_argument("--only", type=int, default=-1)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--log", default=str(HERE / "mutants.log"))
    ap.add_argument("--index", default="", help="comma-separated mutant indices to run")
    ap.add_argument("--root", default=os.getcwd())
    args = ap.parse_args()
    root = str(pathlib.Path(args.root).resolve())

    target = pathlib.Path(args.target).resolve()
    original = target.read_text()
    tree = ast.parse(original)
    col = Collector(args.mode)
    col.visit(tree)
    sites = col.sites
    print(f"{len(sites)} {args.mode} mutants in {target.name}", flush=True)
    if args.only == 0:
        for i, s in enumerate(sites):
            print(f"  [{i}] L{s[1]} {s[2]}")
        return 0

    wanted = list(range(len(sites)))
    if args.index:
        wanted = [int(x) for x in args.index.split(",") if x.strip()]
    if args.only > 0:
        wanted = wanted[: args.only]

    tests = args.tests.split()
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    log = pathlib.Path(args.log)
    log.write_text("")

    def restore() -> None:
        target.write_text(original)

    def on_term(signum, frame):  # noqa: ANN001
        restore()
        sys.exit(143)

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    killed = alive = invalid = 0
    try:
        for i in wanted:
            kind, lineno, detail = sites[i]
            m = Mutator(args.mode, i)
            new = m.visit(ast.parse(original))
            if not m.applied:
                invalid += 1
                continue
            try:
                ast.fix_missing_locations(new)
                src = ast.unparse(new)
                compile(src, str(target), "exec")
            except Exception as exc:  # noqa: BLE001
                invalid += 1
                _append(log, f"[{i}] L{lineno} {detail} -> INVALID {exc}")
                continue
            target.write_text(src)
            t0 = time.time()
            try:
                r = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-x",
                        "-q",
                        "-p",
                        "no:randomly",
                        "--no-header",
                        "-o",
                        "addopts=",
                        *tests,
                    ],
                    capture_output=True,
                    env=env,
                    timeout=args.timeout,
                    cwd=root,
                )
                rc = r.returncode
            except subprocess.TimeoutExpired:
                rc = -9
            finally:
                restore()
            dt = time.time() - t0
            if rc == 0:
                alive += 1
                verdict = "ALIVE"
            else:
                killed += 1
                verdict = "killed" if rc != -9 else "killed(TIMEOUT)"
            _append(log, f"[{i}] L{lineno} {detail} -> {verdict} ({dt:.0f}s)")
            print(f"[{i}] L{lineno} {detail} -> {verdict} ({dt:.0f}s)", flush=True)
    finally:
        restore()

    print(f"\n{killed} killed / {alive} ALIVE / {invalid} invalid", flush=True)
    _append(log, f"\n{killed} killed / {alive} ALIVE / {invalid} invalid")
    return 0


def _append(p: pathlib.Path, line: str) -> None:
    with p.open("a") as fh:
        fh.write(line + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
