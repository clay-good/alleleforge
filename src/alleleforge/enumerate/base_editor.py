"""Base-editor registry and activity-window enumeration.

A base editor edits its target base (A for ABE, C for CBE) on the protospacer
("non-target") strand within a narrow activity window — by default protospacer
positions **4-8**, counting from the PAM-distal end. The hard part the spec calls
out is the *window outcome*: which editable base(s) get edited, and what
**bystanders** ride along.

The :class:`BaseEditor` registry is declarative — deaminase, edit chemistry,
default window, PAM, motif preference — so adding an editor is a data change.
:func:`enumerate_base_edits` finds, for the transition a variant requires, every
sgRNA placing the target base in-window for an eligible editor, annotated with the
intended target position(s), bystander position(s), and in-window composition.

Only transition SNVs are base-editable: ABE installs A->G / T->C, CBE installs
C->T / G->A on the plus strand (editing the appropriate strand).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from alleleforge.genome.reference import ReferenceGenome
from alleleforge.types.edit import Chemistry, EditIntent
from alleleforge.types.guide import DEFAULT_SPACER_LENGTH, PAM, BaseEditWindow, Spacer
from alleleforge.types.sequence import DNASequence, GenomicInterval, Strand
from alleleforge.types.variant import VariantClass
from alleleforge.variant.resolver import ResolvedVariant

_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}

#: The default base-editing activity window (1-based, PAM-distal = position 1).
DEFAULT_WINDOW = (4, 8)

#: The primary base-editor PAM.
_NGG = PAM(pattern="NGG")


class BaseEditor(BaseModel):
    """A declarative base-editor descriptor.

    Attributes:
        name: Editor name (e.g. ``"ABE8e"``).
        deaminase: The deaminase domain (e.g. ``"TadA-8e"``, ``"APOBEC1"``).
        chemistry: ``BASE_ABE`` (A->G) or ``BASE_CBE`` (C->T).
        target_base: The editable base on the protospacer strand (``"A"``/``"C"``).
        result_base: What the target base becomes (``"G"``/``"T"``).
        window: The default ``(start, end)`` activity window (1-based).
        pam: The editor's PAM.
        motif_preference: The preferred 5' neighbor of the target base (e.g.
            ``"T"`` for APOBEC1's TC motif), or ``None`` for a broad editor.
        citation: Literature citation.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    deaminase: str
    chemistry: Chemistry
    target_base: str
    result_base: str
    window: tuple[int, int] = DEFAULT_WINDOW
    pam: PAM = _NGG
    motif_preference: str | None = None
    citation: str | None = None

    def installs(self, from_base: str, to_base: str) -> Strand | None:
        """Return the strand that installs plus-strand ``from_base -> to_base``.

        ``PLUS`` when the editor edits the plus protospacer directly, ``MINUS``
        when it edits the complementary base on the minus strand, else ``None``.
        """
        if from_base == self.target_base and to_base == self.result_base:
            return Strand.PLUS
        if (
            _COMPLEMENT.get(from_base) == self.target_base
            and _COMPLEMENT.get(to_base) == self.result_base
        ):
            return Strand.MINUS
        return None


#: The default base-editor registry. Adding an editor is appending a descriptor.
BASE_EDITORS: tuple[BaseEditor, ...] = (
    BaseEditor(
        name="ABE8e",
        deaminase="TadA-8e",
        chemistry=Chemistry.BASE_ABE,
        target_base="A",
        result_base="G",
        window=(4, 8),
        motif_preference=None,
        citation="Richter et al., Nat Biotechnol 2020 (ABE8e)",
    ),
    BaseEditor(
        name="CBE4max",
        deaminase="APOBEC1",
        chemistry=Chemistry.BASE_CBE,
        target_base="C",
        result_base="T",
        window=(4, 8),
        motif_preference="T",  # APOBEC1 prefers a 5' T (TC motif)
        citation="Koblan et al., Nat Biotechnol 2018 (BE4max)",
    ),
    BaseEditor(
        name="evoCDA1",
        deaminase="evoCDA1",
        chemistry=Chemistry.BASE_CBE,
        target_base="C",
        result_base="T",
        window=(2, 10),  # evoCDA1 has a broad window and weak motif preference
        motif_preference=None,
        citation="Thuronyi et al., Nat Biotechnol 2019 (evoCDA1)",
    ),
)


def _required_transition(resolved: ResolvedVariant, intent: EditIntent) -> tuple[str, str]:
    """Return the plus-strand ``(from_base, to_base)`` the intent requires."""
    var = resolved.variant
    if intent in (EditIntent.CORRECT, EditIntent.REVERT):
        return var.alt, var.ref  # the genome carries the variant; restore the reference
    return var.ref, var.alt  # install the alternate allele


def _editable_positions(spacer: str, window: tuple[int, int], target_base: str) -> tuple[int, ...]:
    """Return 1-based protospacer positions in-window holding ``target_base``."""
    start, end = window
    return tuple(
        pos
        for pos in range(start, end + 1)
        if pos <= len(spacer) and spacer[pos - 1] == target_base
    )


def _windows_for_editor(
    template: str,
    *,
    offset: int,
    chrom: str,
    editor: BaseEditor,
    strand: Strand,
    target_pos: int,
    spacer_length: int,
    window: tuple[int, int],
) -> list[BaseEditWindow]:
    """Enumerate sgRNAs placing ``target_pos``'s base in-window for ``editor``."""
    pam_len = len(editor.pam.pattern)
    out: list[BaseEditWindow] = []
    for k in range(len(template) - pam_len + 1):
        pam_window = template[k : k + pam_len]
        if strand is Strand.PLUS:
            if k < spacer_length or "N" in pam_window or not editor.pam.matches(pam_window):
                continue
            spacer = template[k - spacer_length : k]
            gproto = offset + k - spacer_length  # genomic protospacer start
            ppos = target_pos - gproto + 1  # 1-based, PAM-distal = position 1
            placement = GenomicInterval(
                chrom=chrom, start=gproto, end=gproto + spacer_length, strand=Strand.PLUS
            )
            concrete_pam = pam_window
        else:
            rc_pam = str(DNASequence(pam_window).reverse_complement())
            proto_end = k + pam_len + spacer_length
            if proto_end > len(template) or "N" in rc_pam or not editor.pam.matches(rc_pam):
                continue
            spacer = str(DNASequence(template[k + pam_len : proto_end]).reverse_complement())
            gproto = offset + k + pam_len  # genomic protospacer start (plus coords)
            # minus protospacer position of a plus coordinate: mirror the span.
            ppos = (gproto + spacer_length) - target_pos
            placement = GenomicInterval(
                chrom=chrom, start=gproto, end=gproto + spacer_length, strand=Strand.MINUS
            )
            concrete_pam = rc_pam
        if "N" in spacer or not window[0] <= ppos <= window[1]:
            continue
        if spacer[ppos - 1] != editor.target_base:
            continue  # the target base must be editable on the protospacer strand
        editable = _editable_positions(spacer, window, editor.target_base)
        out.append(
            BaseEditWindow(
                spacer=Spacer(sequence=DNASequence(spacer)),
                editor=editor.name,
                window=window,
                target_positions=(ppos,),
                bystander_positions=tuple(p for p in editable if p != ppos),
                placement=placement,
                pam=editor.pam,
                pam_sequence=DNASequence(concrete_pam),
            )
        )
    return out


def enumerate_base_edits(
    resolved: ResolvedVariant,
    *,
    reference: ReferenceGenome,
    intent: EditIntent = EditIntent.CORRECT,
    editors: tuple[BaseEditor, ...] = BASE_EDITORS,
    spacer_length: int = DEFAULT_SPACER_LENGTH,
    window: tuple[int, int] | None = None,
) -> list[BaseEditWindow]:
    """Enumerate base-editor sgRNAs that place the variant's base in-window.

    Args:
        resolved: The resolved variant (must be a transition SNV to be editable).
        reference: The reference genome.
        intent: What the edit must accomplish (sets the required transition).
        editors: The editors to consider (default: ABE8e, CBE4max, evoCDA1).
        spacer_length: Protospacer length (default 20).
        window: Override the activity window for every editor (default: each
            editor's own window).

    Returns:
        One :class:`BaseEditWindow` per eligible (editor, sgRNA), sorted by editor
        name then protospacer start. Empty for non-SNV or non-transition variants.
    """
    var = resolved.variant
    if var.variant_class is not VariantClass.SNV:
        return []
    from_base, to_base = _required_transition(resolved, intent)
    margin = spacer_length + max((len(e.pam.pattern) for e in editors), default=0)
    region = GenomicInterval(
        chrom=var.chrom,
        start=max(0, var.pos - margin),
        end=var.pos + margin,
        strand=Strand.PLUS,
    )
    fetched = reference.fetch_result(region)
    plus_template = str(fetched.sequence)
    rel = var.pos - region.start
    # The edited strand carries `from_base` at the target position.
    plus_template = plus_template[:rel] + from_base + plus_template[rel + 1 :]

    results: list[BaseEditWindow] = []
    for editor in editors:
        strand = editor.installs(from_base, to_base)
        if strand is None:
            continue
        results.extend(
            _windows_for_editor(
                plus_template,
                offset=region.start,
                chrom=var.chrom,
                editor=editor,
                strand=strand,
                target_pos=var.pos,
                spacer_length=spacer_length,
                window=window or editor.window,
            )
        )
    results.sort(key=lambda w: (w.editor, w.placement.start if w.placement else 0))
    return results
