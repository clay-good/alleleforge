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
