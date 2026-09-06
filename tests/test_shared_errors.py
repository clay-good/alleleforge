"""The artifact gates raise one exception type per policy, not one per module."""

from __future__ import annotations

import pytest

from alleleforge import errors


def test_checksum_error_is_one_class_across_every_gate() -> None:
    """Three modules each defined their own `ChecksumError` and exported it by name.

    A caller writing `from alleleforge.genome import ChecksumError` and guarding a
    design run with it caught reference-checksum failures and silently missed the
    model-checkpoint and dataset ones, which escaped as unrelated-looking
    `RuntimeError`s — while the scorers' docstrings promised "ChecksumError from the
    weight gate" as though it named one type.
    """
    from alleleforge.data import ChecksumError as from_data
    from alleleforge.data.registry import ChecksumError as from_data_registry
    from alleleforge.genome import ChecksumError as from_genome
    from alleleforge.model_zoo import ChecksumError as from_model_zoo

    assert from_data is from_genome is from_model_zoo is from_data_registry is errors.ChecksumError
    # The behaviour that was broken: one `except` covers every artifact gate.
    with pytest.raises(from_genome):
        raise from_data("dataset checksum mismatch")


def test_consent_error_is_one_class_across_every_gate() -> None:
    """ "Nothing may be downloaded without my say-so" is one policy, not four."""
    from alleleforge.data import ConsentError as from_data
    from alleleforge.genome import ConsentError as from_genome
    from alleleforge.model_zoo import ConsentError as from_model_zoo
    from alleleforge.variant import ConsentError as from_variant

    assert from_data is from_genome is from_model_zoo is from_variant is errors.ConsentError
    with pytest.raises(from_model_zoo):
        raise from_variant("a VEP fetch needs network consent")


def test_a_missing_dependency_is_never_raised_as_a_bare_runtime_error() -> None:
    """ "This is not installed" and "this has a bug" must not share an exception type.

    The design path treats the first as graceful degradation and the second as a
    defect, and both the CLI's VCF and cohort handlers catch the type to mean "install
    something". While the adapters raised a bare `RuntimeError` for a missing optional
    package, catching it caught defects too — reporting a bug as an installation
    problem and telling the user to install what they already had.

    Nine sites were converted across two rounds, six then three, because the first
    sweep missed the ones outside `scoring/`. This is the check that would have caught
    that: any `raise RuntimeError` whose message is about an absent dependency.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "alleleforge"
    #: Words that mark a message as "a dependency or tool you do not have".
    needles = ("install", "not on PATH", "requires the optional", "needs cyvcf2")
    offenders: list[str] = []

    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id != "RuntimeError":
                continue
            text = " ".join(
                a.value
                for a in ast.walk(call)
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
            )
            if any(needle in text for needle in needles):
                offenders.append(f"{module.relative_to(root)}:{node.lineno}")

    assert not offenders, (
        "these raise a bare RuntimeError for a missing dependency; use "
        f"MissingDependencyError so a defect is not reported as one: {offenders}"
    )
