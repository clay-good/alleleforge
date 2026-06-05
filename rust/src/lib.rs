//! `aforge_native`: performance kernels for AlleleForge.
//!
//! Exposes `version()` (proving the PyO3 + maturin toolchain against the Python
//! package's single-source version) and the **FM-index off-target search**
//! kernels (`bwt`): `fm_build`, `fm_count`, `fm_locate`, and a `NativeFmIndex`
//! object whose `count` / `locate` / `pam_sites` results are byte-identical to the
//! pure-Python fallback in `alleleforge.genome.index` (pinned by a parity test).
//! The `kmer` (off-target seeding) and `haplotype` (haplotype-walk
//! materialization) kernels build on this same fallback-plus-parity pattern.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

mod bwt;
mod haplotype;
mod kmer;

/// Single-source version string, kept byte-identical to
/// `src/alleleforge/_version.py::__version__` so the toolchain check passes.
/// (Cargo's package version must be valid SemVer and cannot carry the `.dev0`
/// suffix, so the exposed version is a dedicated constant.)
const AFORGE_VERSION: &str = "0.1.0.dev0";

/// Return the native extension version.
#[pyfunction]
fn version() -> &'static str {
    AFORGE_VERSION
}

/// A PAM-anchored protospacer placement (mirrors `genome.index.PamHit`).
#[pyclass(frozen)]
struct NativePamHit {
    #[pyo3(get)]
    protospacer_start: usize,
    #[pyo3(get)]
    pam_start: usize,
    #[pyo3(get)]
    pam_end: usize,
    #[pyo3(get)]
    pam_sequence: String,
}

/// A content-addressed FM-index (the native counterpart of `genome.index.FMIndex`).
#[pyclass]
struct NativeFmIndex {
    inner: bwt::FmIndex,
}

#[pymethods]
impl NativeFmIndex {
    /// Length of the indexed text including the sentinel (mirrors `FMIndex.length`).
    #[getter]
    fn length(&self) -> usize {
        self.inner.length
    }

    /// SHA-256 of the indexed text (matches the Python content hash).
    #[getter]
    fn content_hash(&self) -> &str {
        &self.inner.content_hash
    }

    /// Number of times `pattern` occurs in the indexed text.
    fn count(&self, pattern: &str) -> usize {
        self.inner.count(pattern)
    }

    /// Sorted 0-based start positions of `pattern` occurrences.
    fn locate(&self, pattern: &str) -> Vec<usize> {
        self.inner.locate(pattern)
    }

    /// PAM-anchored protospacer placements for a `PAM`-like object (`.pattern`).
    fn pam_sites(
        &self,
        pam: &Bound<'_, PyAny>,
        spacer_length: usize,
    ) -> PyResult<Vec<NativePamHit>> {
        let pattern: String = pam.getattr("pattern")?.extract()?;
        Ok(self
            .inner
            .pam_sites(&pattern, spacer_length)
            .into_iter()
            .map(|h| NativePamHit {
                protospacer_start: h.protospacer_start,
                pam_start: h.pam_start,
                pam_end: h.pam_end,
                pam_sequence: h.pam_sequence,
            })
            .collect())
    }

    /// Release resources (no-op for the native index; mirrors `FMIndex.close`).
    fn close(&self) {}

    fn __enter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    #[pyo3(signature = (*_args))]
    fn __exit__(&self, _args: &Bound<'_, PyAny>) -> bool {
        false
    }
}

/// Build an FM-index over `text` (alphabet `ACGTN`).
#[pyfunction]
fn fm_build(text: &str) -> PyResult<NativeFmIndex> {
    bwt::FmIndex::build(text)
        .map(|inner| NativeFmIndex { inner })
        .map_err(PyValueError::new_err)
}

/// Count occurrences of `pattern` in `text` (builds a transient index).
#[pyfunction]
fn fm_count(text: &str, pattern: &str) -> PyResult<usize> {
    let index = bwt::FmIndex::build(text).map_err(PyValueError::new_err)?;
    Ok(index.count(pattern))
}

/// Locate occurrences of `pattern` in `text` (builds a transient index).
#[pyfunction]
fn fm_locate(text: &str, pattern: &str) -> PyResult<Vec<usize>> {
    let index = bwt::FmIndex::build(text).map_err(PyValueError::new_err)?;
    Ok(index.locate(pattern))
}

/// Off-target seeding: reference offsets sharing an exact k-mer with `spacer`.
#[pyfunction]
fn kmer_seed_positions(sequence: &str, spacer: &str, k: usize) -> Vec<usize> {
    kmer::seed_positions(sequence, spacer, k)
}

/// Haplotype walking: materialize a haplotype's alternative sequence.
///
/// `variants` is a list of `(pos, ref, alt)` tuples (0-based `pos`). Returns the
/// sequence with every variant applied, or `None` on a reference-base clash.
#[pyfunction]
fn haplotype_apply_variants(
    seq: &str,
    window_start: i64,
    variants: Vec<(i64, String, String)>,
) -> Option<String> {
    haplotype::apply_variants(seq, window_start, &variants)
}

/// The `aforge_native` Python module.
#[pymodule]
fn aforge_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(fm_build, m)?)?;
    m.add_function(wrap_pyfunction!(fm_count, m)?)?;
    m.add_function(wrap_pyfunction!(fm_locate, m)?)?;
    m.add_function(wrap_pyfunction!(kmer_seed_positions, m)?)?;
    m.add_function(wrap_pyfunction!(haplotype_apply_variants, m)?)?;
    m.add_class::<NativeFmIndex>()?;
    m.add_class::<NativePamHit>()?;
    m.add("__version__", AFORGE_VERSION)?;
    Ok(())
}
