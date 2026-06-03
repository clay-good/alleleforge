//! `aforge_native`: performance kernels for AlleleForge.
//!
//! Phase 0 exposes only `version()`, which proves the PyO3 + maturin toolchain
//! end to end against the Python package's single-source version. Later phases
//! add the FM-index off-target search (`bwt`), k-mer hashing (`kmer`), and
//! haplotype walking (`haplotype`) modules referenced in the spec layout.

use pyo3::prelude::*;

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

/// The `aforge_native` Python module.
#[pymodule]
fn aforge_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add("__version__", AFORGE_VERSION)?;
    Ok(())
}
