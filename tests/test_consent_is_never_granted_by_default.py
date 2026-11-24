"""Every consent gate was tested with an answer, and never with silence.

`consent: bool = False` is this library's most load-bearing default. It appears on every
gate that can reach the network — the model registry, the data registry, the reference
genome, the gnomad loader, each trained scorer's `__init__` — and it is written `False`
so that a caller who *says nothing* is refused. That is the whole point of the default:
forgetting it must be safe.

Nothing measured it. Grepping the suite for these gates finds `consent=False` and
`consent=True` at every call site and never an omission, so flipping the declared default
to `True` left the entire suite green on `ModelRegistry.authorize`,
`ReferenceGenome.from_build` and `gnomad.load_default`. A gate whose refusal is only ever
tested by explicitly asking to be refused is not a gate with a safe default; it is a gate
whose default has never been read.

Found by flipping the defaults (`scripts/mutate.py --mode dflt`). The direction matters:
the surviving mutation is the one that turns a refusal into a download, and no production
call site changes behaviour — which is precisely why it is invisible. The damage would be
done by the *next* caller, who omits the keyword and is silently granted consent they
never gave.

The two halves below are deliberate. The static sweep is total: it covers paths this
suite cannot execute, including `gnomad.load_default`, which sits behind
`pragma: no cover - requires the fetched release` and can be pinned no other way. The
behavioural half is what keeps the static one honest, because a check implemented as a
scan over source cannot tell a declaration from a decision — this project has been caught
by that exact blindness before.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from alleleforge.errors import ConsentError
from alleleforge.genome.reference import BuildDescriptor, ReferenceGenome
from alleleforge.model_zoo.registry import default_registry

_SRC = Path(__file__).resolve().parents[1] / "src" / "alleleforge"

#: How many `consent` parameters the library is known to declare. A floor, not an exact
#: count: it stops the sweep going vacuous if the parameter is renamed away, without
#: failing every time a new gate is added.
_KNOWN_CONSENT_PARAMS = 8


def _consent_defaults() -> list[tuple[str, int, str, object]]:
    """Return `(file, line, function, default)` for every `consent` parameter in src."""
    found: list[tuple[str, int, str, object]] = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            positional = args.posonlyargs + args.args
            # `args.defaults` right-aligns against the positional parameters, so the
            # pairing has to be built from the right. Zipping from the left pairs the
            # first default with the first parameter and silently reads the wrong one.
            # `strict=True` on both: the right-aligned slice is the same length as
            # `defaults` by construction, and `kw_defaults` holds one entry per
            # keyword-only parameter (``None`` where there is no default). A length
            # mismatch would mean the pairing is wrong, which is the bug being avoided.
            pairs: list[tuple[ast.arg, ast.expr | None]] = list(
                zip(
                    positional[len(positional) - len(args.defaults) :],
                    args.defaults,
                    strict=True,
                )
            )
            pairs += list(zip(args.kwonlyargs, args.kw_defaults, strict=True))
            for param, default in pairs:
                if param.arg != "consent" or default is None:
                    continue
                value = default.value if isinstance(default, ast.Constant) else default
                found.append((str(path.relative_to(_SRC)), node.lineno, node.name, value))
    return found


def test_every_consent_parameter_defaults_to_refusal() -> None:
    """No `consent` parameter anywhere in the library may default to `True`."""
    declared = _consent_defaults()
    assert len(declared) >= _KNOWN_CONSENT_PARAMS, (
        f"found only {len(declared)} `consent` parameters, expected at least "
        f"{_KNOWN_CONSENT_PARAMS}; if the gates were renamed this sweep is measuring "
        "nothing and the floor needs revisiting deliberately"
    )
    granted = [
        f"{path}:{line} {func}(consent={value!r})"
        for path, line, func, value in declared
        if value is not False
    ]
    assert not granted, (
        f"these gates grant consent to a caller who did not ask for it: {granted}. "
        "The default is the fail-safe — forgetting the keyword must be refused, never "
        "permitted."
    )


def test_the_model_gate_refuses_a_caller_who_says_nothing() -> None:
    """`authorize` with no `consent` keyword at all must refuse.

    Not `consent=False` — *omitted*. That is the call the default exists for and the one
    the suite never made.
    """
    registry = default_registry()
    name = next(iter(registry.names))
    with pytest.raises(ConsentError):
        registry.authorize(name)


def test_the_reference_gate_refuses_a_caller_who_says_nothing(tmp_path: Path) -> None:
    """`from_build` with no `consent` keyword at all must refuse."""
    desc = BuildDescriptor(
        name="synth", version="v1", source_url="http://x/y.fa", citation="c", sha256="00"
    )
    with pytest.raises(ConsentError):
        ReferenceGenome.from_build("synth", cache_dir=tmp_path, descriptor=desc)
