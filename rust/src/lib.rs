//! `aforge_native`: performance kernels for AlleleForge.
//!
//! Exposes `version()` (proving the PyO3 + maturin toolchain against the Python
//! package's single-source version) and the **FM-index off-target search**
//! kernels (`bwt`): `fm_build`, `fm_count`, `fm_locate`, and a `NativeFmIndex`
//! object whose `count` / `locate` / `pam_sites` results are byte-identical to the
//! pure-Python fallback in `alleleforge.genome.index` (pinned by a parity test).
//! The `kmer` (off-target seeding), `haplotype` (haplotype-walk materialization)
//! and `align` (the scan's innermost bulged alignment) kernels build on this same
//! fallback-plus-parity pattern.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::pybacked::PyBackedStr;

mod align;
mod bwt;
mod evaluate;
mod haplotype;
mod kmer;
mod sais;

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
fn fm_build(py: Python<'_>, text: PyBackedStr) -> PyResult<NativeFmIndex> {
    // Minutes on a chromosome, and none of it touches Python: a parallel cohort building
    // indexes would otherwise serialize on the interpreter.
    py.detach(|| bwt::FmIndex::build(&text))
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

/// The SA-IS suffix array of `text` upper-cased + the appended sentinel.
///
/// Exposed so a parity test can pin the linear-time build byte-for-byte against
/// the ground-truth direct sort.
#[pyfunction]
fn fm_suffix_array(py: Python<'_>, text: PyBackedStr) -> Vec<usize> {
    py.detach(|| {
        let mut data = text.to_ascii_uppercase().into_bytes();
        data.push(0); // the FM-index sentinel: smaller than every base
        sais::suffix_array(&data)
    })
}

/// Bulged alignment: best single-base removal from `longer` aligning it to `shorter`.
#[pyfunction]
fn align_best_with_removed_base(
    longer: &str,
    shorter: &str,
    max_mm: usize,
) -> Option<(usize, String)> {
    align::best_with_removed_base(longer, shorter, max_mm)
}

/// Per-anchor protospacer evaluation: the edit-minimal in-budget alignment 5' of a PAM.
///
/// Returns `(proto_start, mismatches, dna_bulge, rna_bulge, aligned_spacer,
/// aligned_target)`, or `None` when nothing is within budget. Subsumes the ungapped
/// comparison and both bulge alignments, so the scan crosses the FFI boundary once per
/// anchor instead of three times.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn evaluate_anchor(
    spacer: &str,
    seq: &str,
    pam_at: usize,
    max_mm: usize,
    dna_bulges: usize,
    rna_bulges: usize,
) -> Option<(usize, usize, usize, usize, String, String)> {
    evaluate::evaluate(spacer, seq, pam_at, max_mm, dna_bulges, rna_bulges)
}

/// Evaluate every anchor of one scan in a single crossing, keeping only the hits.
///
/// The per-anchor entry point above is called once for every PAM occurrence in the
/// contig — 498,957 of them on 2 Mb, roughly 180 million on hg38 — and the scan keeps
/// two. Each of those calls is a Python frame, an argument tuple and an FFI crossing
/// spent on an anchor that is almost always rejected, so this takes the whole anchor
/// list and returns only what survived, with the anchor position carried in the tuple
/// so the caller does not have to pair the two lists back up.
///
/// Identical results to calling `evaluate_anchor` in a loop, which a parity test pins.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn evaluate_anchors(
    py: Python<'_>,
    spacer: PyBackedStr,
    seq: PyBackedStr,
    anchors: Vec<usize>,
    max_mm: usize,
    dna_bulges: usize,
    rna_bulges: usize,
) -> Vec<(usize, usize, usize, usize, usize, String, String)> {
    py.detach(|| {
        anchors
            .into_iter()
            .filter_map(|pam_at| {
                evaluate::evaluate(&spacer, &seq, pam_at, max_mm, dna_bulges, rna_bulges).map(
                    |(start, mm, dna_b, rna_b, aligned_spacer, aligned_target)| {
                        (
                            pam_at,
                            start,
                            mm,
                            dna_b,
                            rna_b,
                            aligned_spacer,
                            aligned_target,
                        )
                    },
                )
            })
            .collect()
    })
}

/// Whole-strand scan: PAM anchoring, evaluation and the `N`-window rejection, in one call.
///
/// The batched evaluator above still needs its caller to enumerate anchors in Python —
/// a quarter of a million `re.Match` objects and method calls per 2 Mb strand, which
/// profiling showed as the single largest cost left in the scan. This does the whole
/// loop, and is pinned byte-identical to `_scan_one_strand` (without its seed prefilter,
/// which stays in Python and only applies at tight budgets).
/// The GIL is **released** for the scan itself (`Python::detach` in PyO3 0.29). This is the one kernel that runs long
/// enough for that to matter — tens of milliseconds per strand of a 2 Mb contig, and
/// minutes on a chromosome — and it is what a cohort's worker threads spend their time
/// in: with the GIL held, `aforge batch --workers 4` was 1.6x rather than ~4x, because
/// four threads were queueing for the interpreter to run Rust that never touches it.
///
/// `PyBackedStr` keeps the Python `str` alive without copying, which matters here: the
/// sequence is a whole contig, and copying it per scan would trade the GIL for a memcpy
/// of the genome.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn scan_strand(
    py: Python<'_>,
    spacer: PyBackedStr,
    seq: PyBackedStr,
    pam: PyBackedStr,
    max_mm: usize,
    dna_bulges: usize,
    rna_bulges: usize,
) -> Vec<evaluate::Hit> {
    py.detach(|| evaluate::scan_strand(&spacer, &seq, &pam, max_mm, dna_bulges, rna_bulges))
}

/// How many bases of a sequence are unambiguous A/C/G/T — the report's "searched" count.
///
/// One pass, no copy. The Python makes eight `str.count` passes over the contig and
/// deliberately does not upper-case first (a copy of a chromosome is a quarter-gigabyte
/// transient in a bounded-memory path); this keeps that and costs one pass.
#[pyfunction]
fn resolved_base_count(seq: &str) -> usize {
    evaluate::resolved_base_count(seq)
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
    m.add_function(wrap_pyfunction!(fm_suffix_array, m)?)?;
    m.add_function(wrap_pyfunction!(align_best_with_removed_base, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_anchor, m)?)?;
    m.add_function(wrap_pyfunction!(evaluate_anchors, m)?)?;
    m.add_function(wrap_pyfunction!(scan_strand, m)?)?;
    m.add_function(wrap_pyfunction!(resolved_base_count, m)?)?;
    m.add_function(wrap_pyfunction!(kmer_seed_positions, m)?)?;
    m.add_function(wrap_pyfunction!(haplotype_apply_variants, m)?)?;
    m.add_class::<NativeFmIndex>()?;
    m.add_class::<NativePamHit>()?;
    m.add("__version__", AFORGE_VERSION)?;
    Ok(())
}
