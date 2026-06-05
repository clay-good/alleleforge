//! Linear-time suffix array construction by SA-IS (induced sorting).
//!
//! SA-IS (Nong, Zhang & Chan, 2009) builds the suffix array in `O(n)` by
//! *induced sorting*: sort the leftmost-S (LMS) suffixes, then induce the order of
//! every other suffix from them in two linear scans. It replaces the prefix-
//! doubling `O(n log² n)` build behind the same interface — the result is
//! **byte-identical**, because the indexed text ends in a unique smallest
//! sentinel, which makes every suffix distinct and so the suffix array unique.
//!
//! The implementation is alphabet-generic (it recurses on a reduced string whose
//! alphabet is the number of distinct LMS substrings); the byte entry point maps
//! the `ACGTN`+sentinel text into the integer alphabet it needs.

/// Marks an empty slot during induced sorting (no valid suffix index equals it).
const EMPTY: usize = usize::MAX;

/// Build the suffix array of `data` in `O(n)`.
///
/// `data` must end in a unique sentinel that is the smallest byte present (the
/// FM-index appends `0`). The returned array is identical to the direct sort.
pub fn suffix_array(data: &[u8]) -> Vec<usize> {
    let s: Vec<usize> = data.iter().map(|&b| b as usize).collect();
    sais(&s, 256)
}

/// Suffix array of `s` (values in `0..alphabet`, ending in a unique smallest 0).
fn sais(s: &[usize], alphabet: usize) -> Vec<usize> {
    let n = s.len();
    let mut sa = vec![EMPTY; n];
    if n == 0 {
        return sa;
    }
    if n == 1 {
        sa[0] = 0;
        return sa;
    }

    // S/L classification: `is_s[i]` is true when suffix `i` is S-type (smaller than
    // the suffix to its right). The sentinel is S-type by definition.
    let mut is_s = vec![false; n];
    is_s[n - 1] = true;
    for i in (0..n - 1).rev() {
        is_s[i] = s[i] < s[i + 1] || (s[i] == s[i + 1] && is_s[i + 1]);
    }

    let mut sizes = vec![0usize; alphabet];
    for &c in s {
        sizes[c] += 1;
    }

    // Pass 1: place LMS suffixes at their bucket tails in text order, then induce —
    // this sorts the LMS suffixes by their LMS-substring (the "guess").
    place_lms_text_order(&mut sa, s, &is_s, &sizes);
    induce(&mut sa, s, &is_s, &sizes);

    // Name the now-sorted LMS substrings; equal substrings share a name.
    let lms_sorted: Vec<usize> = sa
        .iter()
        .copied()
        .filter(|&p| p != EMPTY && is_lms(&is_s, p))
        .collect();
    let (reduced, num_names, lms_in_text) = name_lms(s, &is_s, &lms_sorted);

    // Sort the LMS suffixes for real: if every name is unique the reduced string's
    // suffix array is just its inverse, else recurse.
    let lms_order: Vec<usize> = if num_names == lms_in_text.len() {
        let mut inverse = vec![0usize; reduced.len()];
        for (i, &name) in reduced.iter().enumerate() {
            inverse[name] = i;
        }
        inverse.iter().map(|&i| lms_in_text[i]).collect()
    } else {
        let sub_sa = sais(&reduced, num_names);
        sub_sa.iter().map(|&i| lms_in_text[i]).collect()
    };

    // Final pass: place the truly-sorted LMS suffixes, then induce everything.
    sa.iter_mut().for_each(|x| *x = EMPTY);
    place_lms_sorted(&mut sa, s, &sizes, &lms_order);
    induce(&mut sa, s, &is_s, &sizes);
    sa
}

/// Return whether position `i` is a leftmost-S (LMS) position.
fn is_lms(is_s: &[bool], i: usize) -> bool {
    i > 0 && is_s[i] && !is_s[i - 1]
}

/// Bucket head offsets: the start index of each character's bucket.
fn bucket_heads(sizes: &[usize]) -> Vec<usize> {
    let mut heads = vec![0usize; sizes.len()];
    let mut sum = 0;
    for (h, &size) in heads.iter_mut().zip(sizes) {
        *h = sum;
        sum += size;
    }
    heads
}

/// Bucket tail offsets: one past the last index of each character's bucket.
fn bucket_tails(sizes: &[usize]) -> Vec<usize> {
    let mut tails = vec![0usize; sizes.len()];
    let mut sum = 0;
    for (t, &size) in tails.iter_mut().zip(sizes) {
        sum += size;
        *t = sum;
    }
    tails
}

/// Place every LMS suffix at its bucket tail in left-to-right text order.
fn place_lms_text_order(sa: &mut [usize], s: &[usize], is_s: &[bool], sizes: &[usize]) {
    let mut tails = bucket_tails(sizes);
    for (i, &c) in s.iter().enumerate() {
        if is_lms(is_s, i) {
            tails[c] -= 1;
            sa[tails[c]] = i;
        }
    }
}

/// Place the already-sorted LMS suffixes at their bucket tails.
///
/// Processed in reverse sorted order so that, as tails fill from the right,
/// suffixes within a bucket end up in increasing order left-to-right.
fn place_lms_sorted(sa: &mut [usize], s: &[usize], sizes: &[usize], lms_order: &[usize]) {
    let mut tails = bucket_tails(sizes);
    for &i in lms_order.iter().rev() {
        let c = s[i];
        tails[c] -= 1;
        sa[tails[c]] = i;
    }
}

/// Induce the order of L- then S-type suffixes from the placed suffixes.
fn induce(sa: &mut [usize], s: &[usize], is_s: &[bool], sizes: &[usize]) {
    let n = s.len();
    // L-type: scan left to right, append each L predecessor at its bucket head.
    let mut heads = bucket_heads(sizes);
    for i in 0..n {
        let j = sa[i];
        if j != EMPTY && j > 0 && !is_s[j - 1] {
            let c = s[j - 1];
            sa[heads[c]] = j - 1;
            heads[c] += 1;
        }
    }
    // S-type: scan right to left, prepend each S predecessor at its bucket tail.
    let mut tails = bucket_tails(sizes);
    for i in (0..n).rev() {
        let j = sa[i];
        if j != EMPTY && j > 0 && is_s[j - 1] {
            let c = s[j - 1];
            tails[c] -= 1;
            sa[tails[c]] = j - 1;
        }
    }
}

/// Name the sorted LMS substrings and build the reduced string.
///
/// Returns `(reduced, num_names, lms_in_text)`: the reduced string (LMS names in
/// text order), the number of distinct names, and the LMS positions in text order.
fn name_lms(s: &[usize], is_s: &[bool], lms_sorted: &[usize]) -> (Vec<usize>, usize, Vec<usize>) {
    let n = s.len();
    let mut names = vec![EMPTY; n];
    let mut current = 0usize;
    let mut prev: Option<usize> = None;
    for &pos in lms_sorted {
        if let Some(p) = prev {
            if !lms_substring_eq(s, is_s, p, pos) {
                current += 1;
            }
        }
        names[pos] = current;
        prev = Some(pos);
    }
    let num_names = if lms_sorted.is_empty() {
        0
    } else {
        current + 1
    };
    let lms_in_text: Vec<usize> = (0..n).filter(|&i| is_lms(is_s, i)).collect();
    let reduced: Vec<usize> = lms_in_text.iter().map(|&i| names[i]).collect();
    (reduced, num_names, lms_in_text)
}

/// Return whether the LMS substrings starting at `a` and `b` are identical.
///
/// Compares character **and** S/L type at each offset (over-distinguishing is
/// always safe — it can only refine names, never merge distinct substrings), and
/// stops when both reach the next LMS boundary. The length-1 sentinel substring
/// equals only itself.
fn lms_substring_eq(s: &[usize], is_s: &[bool], a: usize, b: usize) -> bool {
    let n = s.len();
    if a == n - 1 || b == n - 1 {
        return a == b;
    }
    let mut i = 0usize;
    loop {
        let a_lms = i > 0 && is_lms(is_s, a + i);
        let b_lms = i > 0 && is_lms(is_s, b + i);
        if a_lms && b_lms {
            return true;
        }
        if a_lms != b_lms {
            return false;
        }
        if s[a + i] != s[b + i] || is_s[a + i] != is_s[b + i] {
            return false;
        }
        i += 1;
    }
}
