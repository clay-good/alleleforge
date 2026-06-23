//! FM-index over reference sequence (the genome-scale off-target search path).
//!
//! This is the native counterpart of the pure-Python fallback in
//! `alleleforge.genome.index`. The construction and query algorithms mirror that
//! module **line for line** — same sentinel, same C-table, same checkpointed
//! occ/rank table, same sampled suffix array and LF-walk — so the two produce
//! byte-identical results. A parity test in `tests/genome/test_native.py` pins
//! that equivalence.
//!
//! The suffix array is built by **SA-IS** (`crate::sais`), the linear-time
//! induced-sorting algorithm — replacing the earlier prefix-doubling
//! (`O(n log² n)`) build behind this same interface. The unique sentinel makes
//! every suffix distinct, so the result is byte-identical to the direct sort the
//! Python fallback uses (pinned by a parity test against the ground-truth SA and
//! by the FM-index `count`/`locate` parity over low-complexity and random inputs).

use std::collections::HashMap;

use sha2::{Digest, Sha256};

use crate::sais::suffix_array;

/// Sentinel terminator, sorted before every base (never appears in input).
const SENTINEL: u8 = 0;
/// Checkpoint spacing for the rank (occ) table — matches the Python default.
const OCC_RATE: usize = 64;
/// Sampling rate for the suffix array — matches the Python default.
const SA_RATE: usize = 32;

/// A PAM-anchored protospacer placement (0-based half-open offsets).
pub struct PamHit {
    pub protospacer_start: usize,
    pub pam_start: usize,
    pub pam_end: usize,
    pub pam_sequence: String,
}

/// A content-addressed FM-index supporting exact and PAM-anchored search.
pub struct FmIndex {
    bwt: Vec<u8>,
    /// Length of the indexed text **including** the sentinel (mirrors Python `length`).
    pub length: usize,
    c_table: HashMap<u8, usize>,
    occ: HashMap<u8, Vec<usize>>,
    sa_samples: HashMap<usize, usize>,
    /// SHA-256 of the uppercased input text (matches the Python content hash).
    pub content_hash: String,
}

/// Expand one IUPAC code to its sorted concrete bases (matches `IUPAC_EXPAND`).
fn iupac_expand(code: u8) -> &'static [u8] {
    match code.to_ascii_uppercase() {
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

impl FmIndex {
    /// Build an FM-index over `text` (alphabet `ACGTN`).
    ///
    /// Returns an error for an empty sequence or a disallowed base, mirroring the
    /// Python fallback's `ValueError` messages so the contract is identical.
    pub fn build(text: &str) -> Result<FmIndex, String> {
        let s = text.to_ascii_uppercase();
        if s.is_empty() {
            return Err("cannot index an empty sequence".to_string());
        }
        for b in s.bytes() {
            if !matches!(b, b'A' | b'C' | b'G' | b'T' | b'N') {
                return Err(format!(
                    "index alphabet is ACGTN; got disallowed ['{}']",
                    b as char
                ));
            }
        }
        let content_hash: String = Sha256::digest(s.as_bytes())
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect();

        let mut data = s.into_bytes();
        data.push(SENTINEL);
        let n = data.len();

        // Suffix array by SA-IS — linear time, no degradation on the long
        // low-complexity runs (poly-A / poly-N) real genomes are full of. The
        // unique sentinel makes every suffix distinct, so the result is identical
        // to the direct sort (and to the Python fallback) — a parity test pins that.
        let sa = suffix_array(&data);
        let bwt: Vec<u8> = sa.iter().map(|&i| data[(i + n - 1) % n]).collect();

        let mut alphabet: Vec<u8> = data.clone();
        alphabet.sort_unstable();
        alphabet.dedup();

        // C-table: cumulative counts in sorted-alphabet order.
        let mut c_table: HashMap<u8, usize> = HashMap::new();
        let mut running = 0usize;
        for &c in &alphabet {
            c_table.insert(c, running);
            running += bwt.iter().filter(|&&x| x == c).count();
        }

        // Checkpointed occ table. The outer loop coordinates several occ vectors
        // by checkpoint index, so an index loop is the clearest form here.
        let n_checkpoints = n / OCC_RATE + 1;
        let mut occ: HashMap<u8, Vec<usize>> = alphabet
            .iter()
            .map(|&c| (c, vec![0usize; n_checkpoints]))
            .collect();
        let mut seen: HashMap<u8, usize> = alphabet.iter().map(|&c| (c, 0usize)).collect();
        #[allow(clippy::needless_range_loop)]
        for k in 0..n_checkpoints {
            for &c in &alphabet {
                occ.get_mut(&c).unwrap()[k] = seen[&c];
            }
            let end = usize::min((k + 1) * OCC_RATE, n);
            for &b in &bwt[(k * OCC_RATE)..end] {
                *seen.get_mut(&b).unwrap() += 1;
            }
        }

        // Sampled suffix array.
        let mut sa_samples: HashMap<usize, usize> = HashMap::new();
        for (row, &pos) in sa.iter().enumerate() {
            if pos % SA_RATE == 0 {
                sa_samples.insert(row, pos);
            }
        }

        Ok(FmIndex {
            bwt,
            length: n,
            c_table,
            occ,
            sa_samples,
            content_hash,
        })
    }

    /// Number of `c` in `bwt[..i]` (occ checkpoint + remainder), mirroring Python.
    fn rank(&self, c: u8, i: usize) -> usize {
        if i == 0 {
            return 0;
        }
        let k = i / OCC_RATE;
        let base = self.occ.get(&c).map_or(0, |v| v[k]);
        base + self.bwt[(k * OCC_RATE)..i]
            .iter()
            .filter(|&&x| x == c)
            .count()
    }

    /// Half-open BWT row range `[lo, hi)` matching `pattern`.
    fn bw_search(&self, pattern: &[u8]) -> (usize, usize) {
        let (mut lo, mut hi) = (0usize, self.length);
        for &ch in pattern.iter().rev() {
            let base = match self.c_table.get(&ch) {
                Some(&b) => b,
                None => return (0, 0),
            };
            lo = base + self.rank(ch, lo);
            hi = base + self.rank(ch, hi);
            if lo >= hi {
                return (lo, hi);
            }
        }
        (lo, hi)
    }

    /// Walk LF from `row` to a sampled suffix and return its text position.
    fn locate_row(&self, row: usize) -> usize {
        let mut steps = 0usize;
        let mut r = row;
        while !self.sa_samples.contains_key(&r) {
            let c = self.bwt[r];
            r = self.c_table[&c] + self.rank(c, r);
            steps += 1;
        }
        (self.sa_samples[&r] + steps) % self.length
    }

    /// Number of times `pattern` occurs in the indexed text.
    pub fn count(&self, pattern: &str) -> usize {
        if pattern.is_empty() {
            return 0;
        }
        let p = pattern.to_ascii_uppercase().into_bytes();
        let (lo, hi) = self.bw_search(&p);
        hi - lo
    }

    /// Sorted 0-based start positions of `pattern` occurrences.
    pub fn locate(&self, pattern: &str) -> Vec<usize> {
        if pattern.is_empty() {
            return Vec::new();
        }
        let p = pattern.to_ascii_uppercase().into_bytes();
        let (lo, hi) = self.bw_search(&p);
        let mut positions: Vec<usize> = (lo..hi).map(|r| self.locate_row(r)).collect();
        positions.sort_unstable();
        positions
    }

    /// PAM-anchored protospacer placements, sorted by `(protospacer_start, pam)`.
    pub fn pam_sites(&self, pam_pattern: &str, spacer_length: usize) -> Vec<PamHit> {
        let pam = pam_pattern.as_bytes();
        let pam_len = pam.len();
        let mut hits: Vec<PamHit> = Vec::new();
        for concrete in expand_pattern(pam) {
            for pam_start in self.locate(&concrete) {
                if pam_start < spacer_length {
                    continue;
                }
                hits.push(PamHit {
                    protospacer_start: pam_start - spacer_length,
                    pam_start,
                    pam_end: pam_start + pam_len,
                    pam_sequence: concrete.clone(),
                });
            }
        }
        hits.sort_by(|a, b| {
            (a.protospacer_start, &a.pam_sequence).cmp(&(b.protospacer_start, &b.pam_sequence))
        });
        hits
    }
}

/// Expand an IUPAC pattern into every concrete ACGT instantiation.
fn expand_pattern(pattern: &[u8]) -> Vec<String> {
    let mut out = vec![String::new()];
    for &code in pattern {
        let bases = iupac_expand(code);
        let mut next = Vec::with_capacity(out.len() * bases.len().max(1));
        for prefix in &out {
            for &b in bases {
                let mut s = prefix.clone();
                s.push(b as char);
                next.push(s);
            }
        }
        out = next;
    }
    out
}
