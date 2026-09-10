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

/// The concrete bases each IUPAC code admits, matching
/// `alleleforge.types.sequence.IUPAC_EXPAND` intersected with `ACGT`.
///
/// `N` is deliberately not among the admitted bases of any code: the Python scanner
/// builds character classes from the same intersection, so a PAM window holding an `N`
/// is not an anchor on either path. A code this table does not know admits nothing,
/// which makes an unknown pattern find no anchors rather than every anchor.
fn iupac_bases(code: u8) -> &'static [u8] {
    match code {
        b'A' => b"A",
        b'C' => b"C",
        b'G' => b"G",
        b'T' => b"T",
        b'R' => b"AG",
        b'Y' => b"CT",
        b'S' => b"CG",
        b'W' => b"AT",
        b'K' => b"GT",
        b'M' => b"AC",
        b'B' => b"CGT",
        b'D' => b"AGT",
        b'H' => b"ACT",
        b'V' => b"ACG",
        b'N' => b"ACGT",
        _ => b"",
    }
}

/// One hit as the scan reports it: `(proto_start, pam_at, pam_seq, mismatches,
/// dna_bulge, rna_bulge, aligned_spacer, aligned_target)`.
pub type Hit = (usize, usize, String, usize, usize, usize, String, String);

/// Scan one strand: every PAM-positive anchor, evaluated, keeping the in-budget hits.
///
/// The Python counterpart is `_scan_one_strand` without its seed prefilter, and the two
/// are pinned byte-identical. Anchors overlap — `AGGG` holds a PAM at 0 and another at 1
/// — so every position in range is tested, exactly as the Python's zero-width lookahead
/// does; a consuming regex would skip the second.
///
/// The loop lives here because the boundary is the cost: the caller used to build a
/// quarter-million-element anchor list in Python (a `re.Match` and a method call each) to
/// hand back across the FFI, for a scan whose output is two hits.
pub fn scan_strand(
    spacer: &str,
    seq: &str,
    pam: &str,
    max_mm: usize,
    dna_bulges: usize,
    rna_bulges: usize,
) -> Vec<Hit> {
    let seq_bytes = seq.as_bytes();
    let pam_bytes = pam.as_bytes();
    let pam_len = pam_bytes.len();
    let spacer_len = spacer.chars().count();
    let mut hits: Vec<Hit> = Vec::new();
    if pam_len == 0 || seq_bytes.len() < pam_len {
        return hits;
    }
    let classes: Vec<&'static [u8]> = pam_bytes.iter().map(|&code| iupac_bases(code)).collect();
    let first = spacer_len.saturating_sub(1);
    let last = seq_bytes.len() - pam_len;
    for pam_at in first..=last {
        let window = &seq_bytes[pam_at..pam_at + pam_len];
        if !window
            .iter()
            .zip(classes.iter())
            .all(|(base, allowed)| allowed.contains(base))
        {
            continue;
        }
        let Some((start, mm, dna_b, rna_b, aligned_spacer, aligned_target)) =
            evaluate(spacer, seq, pam_at, max_mm, dna_bulges, rna_bulges)
        else {
            continue;
        };
        // Never nominate a site over a padded / unknown region.
        if seq_bytes[start..pam_at].contains(&b'N') {
            continue;
        }
        hits.push((
            start,
            pam_at,
            String::from_utf8_lossy(window).into_owned(),
            mm,
            dna_b,
            rna_b,
            aligned_spacer,
            aligned_target,
        ));
    }
    hits
}
