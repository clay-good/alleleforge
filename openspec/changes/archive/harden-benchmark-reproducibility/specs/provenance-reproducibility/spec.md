## ADDED Requirements

### Requirement: Benchmark results embed the full resolved config snapshot

A `BenchmarkResult` is a top-level result embedding provenance, so its `config_snapshot`
SHALL be the full resolved settings (minus volatile paths) drawn from `Settings.snapshot()`,
not a hand-built subset — identically to the design path. In particular it SHALL record
`interval_level`, which governs the predictive intervals and therefore the calibration
metric the leaderboard ranks on, so two results are comparable only when their governing
settings are visible.

#### Scenario: Benchmark config snapshot is complete
- **WHEN** a benchmark result is produced
- **THEN** its `config_snapshot` reflects the full resolved settings, including
  `interval_level`, not a two-key `{task, split_version}` subset

#### Scenario: Divergent interval levels are detectable
- **WHEN** two benchmark results were produced under different `interval_level` settings
- **THEN** each result's `config_snapshot` records its interval level, so a reviewer can see
  that their calibration columns are not directly comparable
