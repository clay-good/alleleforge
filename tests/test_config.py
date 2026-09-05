"""Tests for the typed global Settings and its resolution order."""

from __future__ import annotations

from pathlib import Path

import pytest

from alleleforge.config import (
    DEFAULT_MAF_THRESHOLD,
    DEFAULT_REFERENCE,
    DEFAULT_SEED,
    Settings,
    _default_cache_dir,
    _default_config_file,
    get_settings,
)


def test_defaults_match_spec() -> None:
    s = Settings()
    assert s.seed == DEFAULT_SEED == 20240501
    assert s.reference == DEFAULT_REFERENCE == "hg38"
    assert s.interval_level == 0.80
    assert s.maf_threshold == DEFAULT_MAF_THRESHOLD == 0.001
    assert s.allow_network is False


def test_settings_are_frozen() -> None:
    s = Settings()
    try:
        s.seed = 1  # type: ignore[misc]
    except Exception as exc:  # pydantic raises on frozen mutation
        assert "frozen" in str(exc).lower() or "instance" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("settings should be frozen")


def test_overrides_take_precedence() -> None:
    s = Settings(seed=7, reference="t2t-chm13")
    assert s.seed == 7
    assert s.reference == "t2t-chm13"


def test_load_reads_toml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('seed = 99\nreference = "mm39"\n')
    s = Settings.load(config_file=cfg)
    assert s.seed == 99
    assert s.reference == "mm39"


def test_load_override_beats_file(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("seed = 99\n")
    s = Settings.load(config_file=cfg, seed=5)
    assert s.seed == 5


def test_load_missing_file_is_ignored(tmp_path: Path) -> None:
    s = Settings.load(config_file=tmp_path / "absent.toml")
    assert s.seed == DEFAULT_SEED


def test_load_env_beats_file(tmp_path: Path) -> None:
    # Documented precedence: env overrides the config file. A file value must not
    # be injected at init priority (which would outrank the environment).
    import os

    cfg = tmp_path / "config.toml"
    cfg.write_text("seed = 111\n")
    os.environ["ALLELEFORGE_SEED"] = "999"
    try:
        assert Settings.load(config_file=cfg).seed == 999  # env wins over file
        # ...but an explicit override still beats the environment.
        assert Settings.load(config_file=cfg, seed=5).seed == 5
    finally:
        del os.environ["ALLELEFORGE_SEED"]
    # With no env var set, the file still beats the default.
    assert Settings.load(config_file=cfg).seed == 111


def test_env_prefix() -> None:
    import os

    os.environ["ALLELEFORGE_SEED"] = "123"
    try:
        assert Settings().seed == 123
    finally:
        del os.environ["ALLELEFORGE_SEED"]


def test_get_settings_is_singleton() -> None:
    assert get_settings() is get_settings()


def test_default_cache_dir_honors_xdg() -> None:
    import os

    os.environ["XDG_CACHE_HOME"] = "/tmp/xdgcache"
    try:
        assert _default_cache_dir() == Path("/tmp/xdgcache/alleleforge")
    finally:
        del os.environ["XDG_CACHE_HOME"]


def test_default_config_file_path() -> None:
    assert _default_config_file().name == "config.toml"


def test_rng_is_reproducible_and_seed_dependent() -> None:
    # The run-scoped RNG is fully determined by the seed: same seed -> same
    # sequence, different seed -> a different one. This is the seam every
    # stochastic step draws from, so the recorded seed is load-bearing.
    draws = lambda s: [Settings(seed=s).rng().random() for _ in range(5)]  # noqa: E731
    assert draws(20240501) == draws(20240501)
    assert draws(1) != draws(2)


def test_seed_governs_a_stochastic_step() -> None:
    # conformal_demo is the run's one genuine stochastic step. Changing the seed
    # changes its output; fixing the seed reproduces it byte-for-byte.
    from alleleforge.benchmark.calibration import conformal_demo

    baseline = conformal_demo(Settings(seed=20240501).rng())
    assert conformal_demo(Settings(seed=20240501).rng()) == baseline
    assert conformal_demo(Settings(seed=7).rng()) != baseline


def test_allow_network_actually_governs_artifact_downloads() -> None:
    """The setting documented as the download switch was read by nothing.

    `allow_network` had a docstring saying the registries "must never auto-download"
    when it is false, and not one of the three consulted it. It is the standing form
    of the per-call `consent=True`: an environment that has already agreed to download
    should not have to thread consent through every entry point, and one that has not
    should not be silently overridden either way.
    """
    from alleleforge.config import Settings, artifact_download_permitted

    off = Settings(allow_network=False)
    on = Settings(allow_network=True)

    # Explicit consent works regardless — today's behavior, unchanged.
    assert artifact_download_permitted(True, settings=off) is True
    assert artifact_download_permitted(True, settings=on) is True
    # Without consent, the setting is the whole answer. Both directions asserted, or
    # a predicate that ignored `settings` entirely would pass on one of them.
    assert artifact_download_permitted(False, settings=off) is False
    assert artifact_download_permitted(False, settings=on) is True


def test_allow_network_reaches_a_real_registry(tmp_path: Path) -> None:
    """...and the predicate is wired in, not merely defined beside the setting.

    Asserted through `DEFAULT_REGISTRY.resolve` rather than the predicate alone: a
    correct helper that no gate calls is exactly the state this round found.
    """
    from alleleforge.config import Settings
    from alleleforge.data.registry import DEFAULT_REGISTRY, ConsentError

    with pytest.raises(ConsentError, match="allow_network"):
        DEFAULT_REGISTRY.resolve("gnomad", cache_dir=tmp_path)

    # An environment that opted in gets past the consent gate — and lands on the next
    # guard (the checksum pin), which proves it passed the first one rather than
    # short-circuiting somewhere earlier.
    settings = Settings(allow_network=True)
    import alleleforge.config as config

    original = config._SETTINGS
    config._SETTINGS = settings
    try:
        with pytest.raises(Exception) as exc:  # noqa: PT011 - the guard past consent
            DEFAULT_REGISTRY.resolve("gnomad", cache_dir=tmp_path)
        assert not isinstance(exc.value, ConsentError)
    finally:
        config._SETTINGS = original
