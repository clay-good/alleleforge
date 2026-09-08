"""Four gates ask for consent to download; one of them ignored the environment's answer.

`artifact_download_permitted(consent)` exists because the check "may I download this?"
had been written out three times identically and the setting meant to govern it,
`allow_network`, was read by none of them. That round unified three registries.

`ModelRegistry.authorize` — the lighter gate for models whose weights come from their own
loader rather than a pinned artifact — is in the same file as one of the three, sixty
lines away, and kept `if not consent`. So an environment that had opted in got weights for
a pinned-artifact model and was refused for a loader-driven one, by the same registry, in
the same run.

Its message is the tell. The other three ended with "or set allow_network for this
environment" and this one did not, because there was no environment answer to name. Even
those three named a *setting*, which is the library's vocabulary: a command-line user
reading "set allow_network" still has to guess `ALLELEFORGE_ALLOW_NETWORK`. The resolver's
`DATABASE_REMEDY` is held to this standard already — a remedy the surface does not have is
not a remedy — and these gates were not.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from alleleforge.config import DOWNLOAD_REMEDY, Settings, artifact_download_permitted
from alleleforge.errors import ConsentError
from alleleforge.model_zoo.registry import default_registry

_SRC = Path(__file__).resolve().parents[1] / "src" / "alleleforge"
_GATE_FILES = (
    _SRC / "model_zoo" / "registry.py",
    _SRC / "data" / "registry.py",
    _SRC / "genome" / "reference.py",
)


def test_the_remedy_names_something_each_caller_can_do() -> None:
    assert "consent=True" in DOWNLOAD_REMEDY, "a Python caller passes the keyword"
    assert "ALLELEFORGE_ALLOW_NETWORK=1" in DOWNLOAD_REMEDY, (
        "a command-line or HTTP deployment sets the variable, and has to be told its "
        "name rather than the name of the setting behind it"
    )
    assert "config file" in DOWNLOAD_REMEDY, "and the persistent form of the same answer"


def test_every_download_gate_consults_the_shared_predicate() -> None:
    """A gate with its own consent check is a gate the environment cannot answer."""
    offenders: list[str] = []
    for path in _GATE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            if not isinstance(call, ast.Call) or getattr(call.func, "id", "") != "ConsentError":
                continue
            enclosing = [
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.If) and node in ast.walk(n) and n.test is not None
            ]
            guards = " ".join(ast.dump(n.test) for n in enclosing)
            if "artifact_download_permitted" not in guards:
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        f"these ConsentErrors are raised without consulting artifact_download_permitted: "
        f"{offenders}. An environment that opted in with allow_network is refused there "
        "and permitted everywhere else."
    )


def test_every_download_refusal_carries_the_shared_remedy() -> None:
    for path in _GATE_FILES:
        source = path.read_text(encoding="utf-8")
        raises = source.count("raise ConsentError(")
        assert raises, f"{path.name} raises no ConsentError; this check would be vacuous"
        assert source.count("DOWNLOAD_REMEDY") >= raises, (
            f"{path.name} raises {raises} ConsentError(s) and uses DOWNLOAD_REMEDY "
            f"{source.count('DOWNLOAD_REMEDY')} time(s); a refusal wording its own "
            "remedy is how three of them came to say something a shell cannot act on"
        )


def test_an_opted_in_environment_is_permitted_by_the_lighter_gate() -> None:
    """The behaviour that differed: same registry, same run, two answers."""
    opted_in = Settings(allow_network=True)
    assert artifact_download_permitted(False, settings=opted_in)

    registry = default_registry()
    name = next(iter(registry.names))
    with pytest.raises(ConsentError) as refused:
        registry.authorize(name, consent=False)
    assert "ALLELEFORGE_ALLOW_NETWORK=1" in str(refused.value)
    assert "artifact_download_permitted" in inspect.getsource(registry.authorize), (
        "the lighter gate must ask the shared predicate, not `consent` alone"
    )
