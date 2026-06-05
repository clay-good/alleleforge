"""Haplotype-walk materialization: apply a haplotype's variants to a window.

The haplotype-aware off-target pass walks each common haplotype spanning the
search region and **materializes its alternative sequence** — the reference
window with the haplotype's full variant set applied — which the scan then
searches. That materialization is the hot inner step (one per haplotype per
region), so it has a native Rust kernel (``haplotype.rs``); this module is the
pure-Python equivalent and the dispatcher, mirroring how the FM-index and k-mer
kernels degrade. ``apply_variants`` is what both paths agree on (a parity test
pins them byte-for-byte).

Variants are applied **right-to-left** (descending position) so each edit's
coordinates stay valid as edits to its right change the sequence length; a
variant whose asserted reference base does not match the window yields ``None``
(a phasing / coordinate clash the engine skips rather than mis-applying).
"""

from __future__ import annotations

from alleleforge import _native

#: One variant edit as a ``(0-based pos, ref allele, alt allele)`` triple.
VariantEdit = tuple[int, str, str]


def native_haplotype_available() -> bool:
    """Return ``True`` if the native crate exposes the haplotype kernel."""
    ext = getattr(_native, "_ext", None)
    return _native.NATIVE_AVAILABLE and ext is not None and hasattr(ext, "haplotype_apply_variants")


def python_apply_variants(seq: str, window_start: int, variants: list[VariantEdit]) -> str | None:
    """Apply every variant (right-to-left) to ``seq``; ``None`` on a ref clash.

    Args:
        seq: The reference window, 5'->3' on the plus strand.
        window_start: 0-based genomic start of ``seq[0]``.
        variants: ``(pos, ref, alt)`` edits to apply (0-based ``pos``).

    Returns:
        The materialized sequence, or ``None`` if any variant falls outside the
        window or its asserted ``ref`` does not match the window (case-insensitive).
    """
    out = seq
    for pos, ref, alt in sorted(variants, key=lambda v: v[0], reverse=True):
        rel = pos - window_start
        if rel < 0 or rel + len(ref) > len(out):
            return None
        if out[rel : rel + len(ref)].upper() != ref.upper():
            return None
        out = out[:rel] + alt + out[rel + len(ref) :]
    return out


def apply_variants(
    seq: str, window_start: int, variants: list[VariantEdit], *, prefer_native: bool = True
) -> str | None:
    """Materialize the alt sequence, via the native kernel when available.

    The native and pure-Python paths return byte-identical results (a parity test
    pins this); ``prefer_native`` selects the Rust kernel when the crate is built.
    """
    if prefer_native and native_haplotype_available():  # pragma: no cover - native not built in CI
        ext = _native._ext  # type: ignore[attr-defined]  # optional native kernel
        result: str | None = ext.haplotype_apply_variants(seq, window_start, variants)
        return result
    return python_apply_variants(seq, window_start, variants)
