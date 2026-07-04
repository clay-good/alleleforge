# OpenSpec conventions for AlleleForge

This directory holds the spec-driven source of truth for AlleleForge's behavior, in
the [OpenSpec](https://github.com/Fission-AI/OpenSpec) convention. Read this before
adding or changing a spec.

## Layout

```
openspec/
  project.md                     # project context (stack, principles, conventions)
  AGENTS.md                      # this file
  specs/<capability>/spec.md     # CURRENT truth: what the system does today
  changes/<change-id>/           # a PROPOSED change (delta against specs/)
    proposal.md                  # Why / What Changes / Impact
    tasks.md                     # ordered implementation checklist
    design.md                    # optional: non-obvious technical decisions
    specs/<capability>/spec.md   # the delta (ADDED / MODIFIED / REMOVED requirements)
```

- **`specs/`** is the baseline: the requirements the code already honors. It is
  descriptive of today, written so a reviewer can hold the implementation to it.
- **`changes/`** is forward-looking: each folder is one coherent proposal that
  bulletproofs or enhances a capability. When a change ships, its deltas are folded
  into `specs/` and the change folder is archived.

## Requirement format

Every capability spec has a `## Purpose` and a `## Requirements` section. Each
requirement is a `###` header with at least one `####` scenario:

```markdown
### Requirement: Short imperative name
The system SHALL <observable, testable behavior>. Use SHALL for mandatory behavior,
SHOULD for strong recommendations, MAY for optional.

#### Scenario: A concrete situation
- **WHEN** <trigger / input / precondition>
- **THEN** <observable outcome>
- **AND** <further outcome, optional>
```

Rules:
- One behavior per requirement. If you write "and also," split it.
- Scenarios are the tests. Write them so they map to (or already match) a pytest case.
- Prefer observable outcomes over implementation detail. Name the invariant, not the
  function.
- Cite the scientific source when a requirement encodes a published formula or window.

## Change delta format

A change's `specs/<capability>/spec.md` contains only the deltas, under these headers:

```markdown
## ADDED Requirements
### Requirement: ...
#### Scenario: ...

## MODIFIED Requirements
### Requirement: <existing name, verbatim>
<the full new text of the requirement, not just the diff>

## REMOVED Requirements
### Requirement: <existing name>
Reason: <why it is going away>
```

`MODIFIED` and `REMOVED` must reference a requirement that exists in `specs/` by its
exact name. `proposal.md` follows: `## Why`, `## What Changes`, `## Impact` (affected
specs + code). `tasks.md` is an ordered `- [ ]` checklist grouped by `## N. Section`.

## Capabilities in this repo

Baseline specs live under `specs/`. The current capability set:

`genome-access`, `data-registry`, `variant-resolution`, `offtarget-nomination`,
`offtarget-scoring`, `cas9-design`, `base-editor-design`, `prime-editor-design`,
`candidate-ranking`, `uncertainty-contract`, `model-zoo`, `provenance-reproducibility`,
`benchmark-harness`, `reporting`, `oligo-output`, `visualization`, `cli`, `web-api`,
`native-kernels`.
