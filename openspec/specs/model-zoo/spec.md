# model-zoo Specification

## Purpose

Be the single choke point for loading any model checkpoint or backbone: refuse anything
without a complete model card, a permitting license, explicit user consent, and (where
pinned) a verified content hash — so a heavy/ML stack is always opt-in, CI stays
weight-free, and every loaded artifact is traceable and license-clean.

## Requirements

### Requirement: Every model carries a complete, validated card

Loading any model SHALL require a validated `ModelCard` with the fields `name`,
`version`, `chemistry`, `training_data`, `intended_use`, `out_of_scope_use`, `license`,
`citation`, and `known_failure_modes` (now required, so every model's safety-audit
surface is complete). A missing file or non-mapping YAML SHALL raise `CardError`; a card
missing any required field SHALL be rejected at validation.

#### Scenario: Missing required field
- **WHEN** a card omits `intended_use`
- **THEN** card validation rejects it

#### Scenario: Card without failure modes
- **WHEN** a card omits `known_failure_modes`
- **THEN** card validation rejects it

#### Scenario: Absent card
- **WHEN** a model is loaded but its card file is missing
- **THEN** it raises `CardError`

### Requirement: Licenses are enforced before load

`license_permits` SHALL refuse forbidden licenses (`proprietary`, `none`, `unknown`,
`all-rights-reserved`) under any use, and SHALL block commercial use of non-commercial
licenses (markers `-nc`, `noncommercial`, `research-only`). The default use is research.

#### Scenario: Research-only card for commercial use
- **WHEN** a research-only model is loaded with commercial intent
- **THEN** it raises `LicenseError`

### Requirement: Uncached artifacts require consent, a pinned hash, and a source

`ModelRegistry.checkpoint` SHALL, when the artifact is not cached, require
`consent=True` (`ConsentError`), a pinned `checkpoint_sha256` (`ChecksumError`,
"refusing to fetch an unverifiable artifact"), and a `source_url`; downloaded bytes
SHALL be stream-hashed and rejected on mismatch (`ChecksumError`). It SHALL ALSO verify an
**already-cached** artifact against its pinned hash on every load, not only on download,
so a tampered or truncated cache entry cannot pass silently. An **unpinned** card
(`checkpoint_sha256 is None`) SHALL fail closed on **both** paths — a cached file dropped at
the checkpoint path for an unpinned card SHALL raise `ChecksumError`, exactly like the
download path, so "a pinned hash is required to load" holds whether or not the file is
already present.

#### Scenario: No consent
- **WHEN** an uncached checkpoint is requested without consent
- **THEN** it raises `ConsentError` naming the source URL

#### Scenario: Unpinned hash
- **WHEN** a download is required but the card pins no `checkpoint_sha256`
- **THEN** it raises `ChecksumError`

#### Scenario: Corrupted download
- **WHEN** downloaded bytes hash differently from the pinned value
- **THEN** it raises `ChecksumError` and the artifact is rejected

#### Scenario: Tampered cache entry
- **WHEN** a cached checkpoint's bytes no longer match the pinned `checkpoint_sha256`
- **THEN** loading it raises `ChecksumError`

#### Scenario: Cached but unpinned artifact
- **WHEN** a file exists at the checkpoint cache path but the card pins no `checkpoint_sha256`
- **THEN** loading it raises `ChecksumError` (fail-closed), never returns the unverified file

### Requirement: One shared gate resolves weights for provenance

`WeightGate` SHALL be the single resolution flow for trained models: if the card pins a
hash it runs the full download-and-verify path, otherwise it runs the lighter
license-plus-consent `authorize` path (for hub-resolved backbones); either way it stores
the resolved `ModelCheckpoint` (name, version, sha256, chemistry, license, citation,
known failure modes) for provenance.

#### Scenario: Hub-resolved backbone with consent
- **WHEN** a backbone with no pinned artifact is authorized with research consent
- **THEN** the resolved `ModelCheckpoint` is recorded without a network hash check

### Requirement: CI stays weight-free

The default install and CI SHALL exercise the gate, card parsing, and a deterministic
weight-free stub embedder without any ML dependency; the real weighted path SHALL be
reachable only via the appropriate optional extra and the `real_weights` test marker.

#### Scenario: Weight-free run
- **WHEN** the library runs without any ML extra installed
- **THEN** card parsing and gating work and scoring falls back to the stub embedder

#### Scenario: Trained path is opt-in
- **WHEN** a trained-model path is requested without its extra or without consent
- **THEN** it raises from the gate rather than silently downgrading

### Requirement: A card's honesty fields travel with the result and are rendered

The three fields that make a model card honest — what it is for, what it must not be
used for, and how it fails — SHALL travel together into a result's provenance. Carrying
the failure modes without the out-of-scope statement records how a model fails at the
edges of a valid use while omitting that the use may not have been valid at all.

Carrying them is not sufficient. Every human-facing render SHALL print, per model, its
out-of-scope statement and its documented failure modes, so a safety audit does not
require re-opening the cards — which is the stated reason the fields are carried. A model
that documents no limitation SHALL produce no entry and no section heading: an empty
"Model limitations" heading reads as an assertion that there are none.

#### Scenario: A card documenting limits
- **WHEN** a result's provenance names a model whose card states an out-of-scope use
- **THEN** the rendered report states it alongside the model's known failure modes

#### Scenario: A card documenting none
- **WHEN** no model in the result documents a limitation
- **THEN** no limitations section is rendered at all

### Requirement: An unmeasured metric is absent, not zero

A model card SHALL omit a performance metric it has not measured rather than report it
as `0.0`, and SHALL say in a reader-facing field that it is unmeasured. `0.0` is the
floor of every correlation and accuracy scale, so a placeholder there is not neutral —
it claims the model has no predictive value.

#### Scenario: A carded model the project has not scored
- **WHEN** a card describes a model for which no accuracy measurement exists here
- **THEN** its `metrics` carries no accuracy key, and its documented failure modes say
  that none has been measured
