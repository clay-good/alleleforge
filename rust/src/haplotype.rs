//! Haplotype walking kernel: materialize a haplotype's alternative sequence.
//!
//! Native counterpart of `alleleforge.offtarget._haplotype.python_apply_variants`:
//! apply a haplotype's full variant set to a reference window, returning the
//! materialized alternative sequence the off-target engine then scans, or `None`
//! when a variant's asserted reference base does not match the window (a phasing /
//! coordinate clash the engine must skip, not silently mis-apply).
//!
//! Byte-for-byte identical to the Python fallback (a parity test pins it). The
//! variants are applied **right-to-left** (descending position, stably) so each
//! edit's coordinates stay valid as earlier edits to its right change the length;
//! the reference assertion is ASCII-case-insensitive to match the Python `.upper()`
//! comparison, while the alt allele is spliced in verbatim (its case preserved).

/// Apply `variants` (each `(pos, ref, alt)`, 0-based `pos`) to `seq`, a window
/// starting at `window_start`. Returns the materialized sequence, or `None` on a
/// reference-base clash or out-of-window variant.
pub fn apply_variants(
    seq: &str,
    window_start: i64,
    variants: &[(i64, String, String)],
) -> Option<String> {
    // Stable sort indices by descending position (matches Python's
    // `sorted(..., reverse=True)`, which keeps the original order for ties).
    let mut order: Vec<usize> = (0..variants.len()).collect();
    order.sort_by(|&a, &b| variants[b].0.cmp(&variants[a].0));

    let mut out: Vec<u8> = seq.as_bytes().to_vec();
    for &i in &order {
        let (pos, ref_allele, alt_allele) = &variants[i];
        let rel = pos - window_start;
        if rel < 0 || (rel as usize) + ref_allele.len() > out.len() {
            return None;
        }
        let rel = rel as usize;
        let ref_bytes = ref_allele.as_bytes();
        if !out[rel..rel + ref_bytes.len()]
            .iter()
            .zip(ref_bytes)
            .all(|(a, b)| a.eq_ignore_ascii_case(b))
        {
            return None;
        }
        let mut next = Vec::with_capacity(out.len() + alt_allele.len());
        next.extend_from_slice(&out[..rel]);
        next.extend_from_slice(alt_allele.as_bytes());
        next.extend_from_slice(&out[rel + ref_bytes.len()..]);
        out = next;
    }
    String::from_utf8(out).ok()
}
