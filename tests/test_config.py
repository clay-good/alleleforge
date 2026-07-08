"""Tests for the typed global Settings and its resolution order."""

from __future__ import annotations

from pathlib import Path

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
