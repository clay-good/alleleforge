//! k-mer seed kernel for off-target candidate seeding.
//!
//! Native counterpart of `alleleforge.offtarget._kmer.python_seed_positions`:
//! return the reference offsets at which a sequence shares an exact length-`k`
//! substring (a *seed*) with the spacer. Byte-for-byte identical to the Python
//! path (a parity test pins it); the off-target scan uses it to skip anchors that
//! provably contain no in-budget hit.

use std::collections::HashSet;

/// Return sorted start positions `p` where `sequence[p..p+k]` is a spacer k-mer.
///
/// Returns an empty vector for `k == 0` or inputs shorter than `k`. Comparison is
/// over raw bytes (case-sensitive), matching the Python seeding which receives
/// already-upper-cased sequences from the scan.
pub fn seed_positions(sequence: &str, spacer: &str, k: usize) -> Vec<usize> {
    let seq = sequence.as_bytes();
    let sp = spacer.as_bytes();
    if k == 0 || sp.len() < k || seq.len() < k {
        return Vec::new();
    }
    let kmers: HashSet<&[u8]> = (0..=sp.len() - k).map(|i| &sp[i..i + k]).collect();
    (0..=seq.len() - k)
        .filter(|&p| kmers.contains(&seq[p..p + k]))
        .collect()
}
