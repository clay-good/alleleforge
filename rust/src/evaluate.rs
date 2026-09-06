//! Per-anchor protospacer evaluation for the off-target scan.
//!
//! Native counterpart of `alleleforge.offtarget._search._evaluate`: given a PAM at
//! `pam_at`, score the ungapped alignment and the two single-bulge alignments 5' of
//! it and return the **edit-minimal** one. Byte-for-byte identical to the Python path
//! (a parity test pins it).
//!
//! This is the per-anchor entry point of the scan — 500,000 calls over 2 Mb — and it
//! subsumes three functions that were previously called across the FFI boundary
//! separately: the ungapped comparison (Python), and two calls into
//! `align_best_with_removed_base` (native). Moving the whole decision here removes a
//! million boundary crossings as well as the interpreter loop.
//!
//! Comparison is over raw bytes, matching `align.rs`, `kmer.rs` and the Python path,
//! all of which receive already-upper-cased ACGTN sequences from the scan.

use crate::align;

/// One candidate alignment: `(proto_start, mismatches, dna_bulge, rna_bulge,
/// aligned_spacer, aligned_target)`.
pub type Alignment = (usize, usize, usize, usize, String, String);

/// Mismatch count of an equal-length alignment, or `None` when over budget.
///
/// Stops the moment the budget is blown, as the Python does — on random sequence
/// that is after a handful of bases.
fn best_ungapped(spacer: &[u8], window: &[u8], max_mm: usize) -> Option<usize> {
    if spacer.len() != window.len() {
        return None;
    }
    let mut mm = 0usize;
    for (a, b) in spacer.iter().zip(window.iter()) {
        if a != b {
            mm += 1;
            if mm > max_mm {
                return None;
            }
        }
    }
    Some(mm)
}

/// Rank key: fewest total edits, then fewest bulges, then DNA bulge before RNA.
///
/// A total, deterministic order — the same tuple the Python's `_rank` builds.
fn rank(c: &Alignment) -> (usize, usize, usize) {
    let (_start, mm, dnab, rnab, _asp, _atg) = c;
    (mm + dnab + rnab, dnab + rnab, *rnab)
}

/// Evaluate the protospacer 5' of a PAM at `pam_at`, returning the edit-minimal
/// alignment within budget.
///
/// Every in-budget alignment (ungapped, one DNA bulge, one RNA bulge) is considered
/// and the fewest-edit one returned, so a bulged near-perfect match wins over a
/// many-mismatch ungapped one and a site's risk is never under-stated.
pub fn evaluate(
    spacer: &str,
    seq: &str,
    pam_at: usize,
    max_mm: usize,
    dna_bulges: usize,
    rna_bulges: usize,
) -> Option<Alignment> {
    let sp = spacer.as_bytes();
    let sq = seq.as_bytes();
    let n = sp.len();
    if pam_at > sq.len() {
        return None;
    }
    let mut best: Option<Alignment> = None;
    let mut consider = |cand: Alignment| {
        // `min` in Python keeps the FIRST of equal-ranking candidates, and they are
        // appended ungapped -> DNA -> RNA. A strict `<` preserves that.
        if best.as_ref().is_none_or(|b| rank(&cand) < rank(b)) {
            best = Some(cand);
        }
    };

    // Ungapped: exactly n bases immediately 5' of the PAM.
    if pam_at >= n {
        let start = pam_at - n;
        let window = &sq[start..pam_at];
        if let Some(mm) = best_ungapped(sp, window, max_mm) {
            consider((
                start,
                mm,
                0,
                0,
                spacer.to_string(),
                String::from_utf8_lossy(window).into_owned(),
            ));
        }
    }
    // DNA bulge: n+1 genomic bases; remove one so the aligned target is n bases.
    if dna_bulges >= 1 && pam_at > n {
        let start = pam_at - (n + 1);
        let window = &seq[start..pam_at];
        if let Some((mm, reduced_target)) = align::best_with_removed_base(window, spacer, max_mm) {
            consider((start, mm, 1, 0, spacer.to_string(), reduced_target));
        }
    }
    // RNA bulge: n-1 genomic bases; remove the extra spacer base instead.
    if rna_bulges >= 1 && n >= 2 && pam_at >= n - 1 {
        let start = pam_at - (n - 1);
        let window = &seq[start..pam_at];
        if let Some((mm, reduced_spacer)) = align::best_with_removed_base(spacer, window, max_mm) {
            consider((start, mm, 0, 1, reduced_spacer, window.to_string()));
        }
    }
    best
}
