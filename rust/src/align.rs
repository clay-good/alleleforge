//! Bulged-alignment kernel for the off-target scan.
//!
//! Native counterpart of `alleleforge.offtarget._search._python_best_with_removed_base`:
//! the best single-base removal from `longer` that aligns it to `shorter` within a
//! mismatch budget. Byte-for-byte identical to the Python path (a parity test pins it).
//!
//! This is the innermost function of the scan — two calls per PAM-positive anchor, one
//! per bulge direction, a million of them over 2 Mb — and profiling put it at 57% of the
//! scan's self time. The algorithm is the same two-pass decomposition the Python uses:
//! removing base `r` leaves the first `r` comparisons untouched and shifts every later
//! one by one, so the mismatch count splits into a prefix sum and a suffix sum and two
//! linear passes price every removal. Both passes stop as soon as the budget is blown,
//! which on random sequence is after a handful of bases.
//!
//! Comparison is over raw bytes, matching `kmer.rs` and the Python path, which receives
//! already-upper-cased ACGTN sequences from the scan.

/// Best `(mismatches, reduced_longer)` over removing one base from `longer`.
///
/// `longer` must be exactly one byte longer than `shorter`; anything else is not a
/// single-base bulge and returns `None`, as the Python does by refusing to build an
/// alignment it cannot score. Returns `None` when every removal is over budget.
pub fn best_with_removed_base(
    longer: &str,
    shorter: &str,
    max_mm: usize,
) -> Option<(usize, String)> {
    let lo = longer.as_bytes();
    let sh = shorter.as_bytes();
    if lo.len() != sh.len() + 1 {
        return None;
    }
    let n = sh.len();

    // prefix[r]: mismatches over the first r positions, which removing r leaves intact.
    // It only grows, so once it passes the budget no larger r can qualify.
    let mut prefix = vec![0usize; n + 1];
    let mut running = 0usize;
    let mut r_max = n;
    for i in 0..n {
        running += usize::from(lo[i] != sh[i]);
        if running > max_mm {
            r_max = i;
            break;
        }
        prefix[i + 1] = running;
    }

    // suffix[r]: mismatches between longer[r+1..] and shorter[r..], the shifted tail.
    // It only grows as r decreases, so the same bound applies from the other end.
    let mut suffix = vec![0usize; n + 1];
    running = 0;
    let mut r_min = 0usize;
    for r in (0..n).rev() {
        running += usize::from(lo[r + 1] != sh[r]);
        if running > max_mm {
            r_min = r + 1;
            break;
        }
        suffix[r] = running;
    }
    if r_min > r_max {
        return None; // no removal position is within budget from both ends
    }

    let mut best: Option<(usize, usize)> = None; // (mismatches, r)
    for r in r_min..=r_max {
        let mm = prefix[r] + suffix[r];
        if mm <= max_mm && best.is_none_or(|(b, _)| mm < b) {
            best = Some((mm, r));
        }
    }
    let (mm, r) = best?;

    // Built from bytes rather than by slicing the &str: a removal that split a
    // multi-byte character would panic on a char boundary, and `from_utf8` turning it
    // into `None` is a refusal rather than a crash. For the ASCII sequence data this
    // kernel is given, the two are the same thing.
    let mut reduced = Vec::with_capacity(n);
    reduced.extend_from_slice(&lo[..r]);
    reduced.extend_from_slice(&lo[r + 1..]);
    String::from_utf8(reduced).ok().map(|s| (mm, s))
}
