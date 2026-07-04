# native-kernels Specification

## Purpose

Provide optional Rust (PyO3) kernels that accelerate the three off-target hot paths —
FM-index PAM anchoring, k-mer seeding, and haplotype-window materialization — whose
results are byte-identical to a proven pure-Python fallback, so the genome-scale path is
fast without ever diverging from the CI-tested reference behavior.

## Requirements

### Requirement: The library runs with or without the extension

The library SHALL import and run cleanly whether or not the `aforge_native` crate is
built, exposing `NATIVE_AVAILABLE` and returning `None` from `native_version()` when
absent; every native branch SHALL be gated so CI never depends on the compiled extension.

#### Scenario: Extension absent
- **WHEN** the crate is not built
- **THEN** `import alleleforge` succeeds, `NATIVE_AVAILABLE` is `False`, and every path
  uses the Python fallback

### Requirement: Native output is byte-identical to Python

The FM-index, k-mer-seed, and haplotype kernels SHALL each produce output byte-identical
to their pure-Python equivalent, enforced by `native`-marked parity tests over fixed
vectors, low-complexity stress inputs, and seeded fuzz.

#### Scenario: FM-index parity
- **WHEN** the same text is indexed and searched with and without the native extension
- **THEN** the content hash, length, and all count/locate/PAM-site results are equal

#### Scenario: Haplotype parity under fuzz
- **WHEN** thousands of randomized haplotype cases (including indels, N, lowercase,
  out-of-window) run through both kernels
- **THEN** native and Python results agree exactly

### Requirement: Suffix-array construction is provably correct

The suffix array SHALL be built by linear-time SA-IS and SHALL match a ground-truth
direct sort exactly, guaranteed by a unique sentinel that makes every suffix distinct.

#### Scenario: SA-IS equivalence
- **WHEN** fuzzed inputs are indexed
- **THEN** the SA-IS suffix array equals the direct-sort suffix array

### Requirement: The build asserts version agreement

`assert_native_matches_python()` SHALL raise if the compiled crate's version disagrees
with the Python package (a no-op when unbuilt), proving the single-source maturin/PyO3
wiring.

#### Scenario: Version skew
- **WHEN** the crate version differs from the Python package version
- **THEN** the assertion raises with a rebuild hint

### Requirement: Linear and native paths agree on dirty input

The pure-Python linear scan and the FM-index/native path SHALL handle non-`ACGTN` input
identically — both skipping it, or both rejecting it with the same error — so a region
containing unexpected characters cannot produce different results depending on which path
ran. Parity SHALL be exercised at genome scale, including low-complexity poly-N and poly-A
runs.

#### Scenario: Non-ACGTN region
- **WHEN** a region contains a base outside `ACGTN`
- **THEN** the linear and FM/native paths produce the same outcome (both skip or both
  raise), not a crash on one path and a silent skip on the other

#### Scenario: Genome-scale parity
- **WHEN** a multi-megabase reference with poly-N/poly-A runs is searched
- **THEN** the FM/native hits are byte-identical to the linear-scan hits
