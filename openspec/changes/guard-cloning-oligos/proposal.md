# Guard cloning oligos as a wet-lab deliverable

## Why

The oligo set is a real reagent a scientist orders, anneals, and clones — a wrong one wastes
reagents and a week of bench time, and the spec already calls this surface safety-critical.
A prior change (`validate-oligo-alphabet`, archived) enforced the `ACGTN` alphabet and the
round-trip invariant, but four gaps let a cloning-lethal or mis-specified oligo ship as a
clean, round-trip-valid deliverable:

1. **No screening for the enzyme's own recognition site.** `VectorScheme` carries an
   `enzyme` field (`BsmBI`/`BbsI`/`BsaI`, `report/oligos.py:70-89`) but nothing ever reads
   it to screen a sequence — a repo-wide search for the recognition motifs finds nothing in
   `src/`. If the spacer or the pegRNA 3' extension (RTT+PBS+motif) contains that Type IIS
   enzyme's site (BsmBI `CGTCTC`, BbsI `GAAGAC`, BsaI `GGTCTC`, or its reverse complement),
   the enzyme cuts *inside* the insert during Golden-Gate assembly and the clone silently
   fails. The round-trip invariant can't catch this — it only checks strand complementarity,
   not that the insert survives digestion. This is the classic Golden-Gate failure every
   CRISPR cloning protocol warns about.
2. **The U6 5'-G is double-added.** `sgrna_oligos` / `pegrna_oligos` prepend `G`
   unconditionally when `prepend_g` is set (`oligos.py:259-260,288-290`), with no
   `startswith("G")` guard; `reconstruct()` strips exactly one G (`oligos.py:161`), so a
   spacer already starting with G recovers cleanly and the extra base passes invisibly. About
   1 in 4 spacers reach the oligo layer already G-initiated (the design layer only annotates,
   `design/prime.py:86`), so they ship as a 21-nt guide with an unintended 5' G — a terminal
   mismatch that shifts length and can depress activity. Standard protocols add the G only if
   the spacer does not already begin with one.
3. **The PDF leave-behind omits the oligos, and no render states prep.** `report/pdf.py:33-73`
   renders everything *except* the cloning oligos, though it is marketed as the printable
   leave-behind and the reporting spec requires "cloning oligos" per candidate in every
   report; the HTML render includes them (`html.py:165-170`). No render states whether the
   annealed oligos need 5' phosphorylation (T4 PNK) or a dephosphorylated vector — required
   for the ligation to close. So the one artifact a scientist prints can't be ordered from,
   and the electronic one can set up a ligation that cannot close.
4. **The pegRNA extension overhang is uncited and self-contradictory.** The docstring says
   the extension uses `GTGC/CGCG` ends (`oligos.py:112-114`), but the constants build
   `GTGC/AAAA` (`oligos.py:126-127`); the distal overhang is a bare, uncited constant while
   every `VectorScheme` carries a protocol citation, and `reconstruct` only checks internal
   consistency. If the true acceptor's downstream overhang is not `AAAA`, the extension does
   not ligate in-frame downstream of the scaffold — a non-functional pegRNA presented as
   verified. (A homopolymeric `AAAA` overhang is also a low-fidelity junction.)

## What Changes

- **Screen every emitted insert (both strands)** against its scheme's Type IIS recognition
  site and either refuse to emit the oligo set with a clear error or attach a prominent
  `internal-<enzyme>-site` flag naming the position — so a cloning-lethal insert never ships
  clean.
- **Add the 5' G only if the spacer does not already begin with G**, and record whether a G
  was added, so emitted guide length and 5' base match the intended protospacer.
- **Include the cloning oligos in the PDF render** (per the reporting spec) and **state the
  phosphorylation/annealing prerequisite** in every oligo render.
- **Make the pegRNA 3'-extension overhangs a named, citation-bearing part of the scheme**,
  matched to the acceptor's documented overhangs, with the docstring and constants in
  agreement.

## Impact

- Specs: `oligo-output` (ADDED enzyme-site screening; ADDED phosphorylation note; MODIFIED
  conditional 5'-G duplex construction; MODIFIED cited extension overhangs), `reporting`
  (ADDED oligos-in-every-render).
- Code: `report/oligos.py`, `report/pdf.py`, `report/html.py`, `report/builder.py`.
- Tests: a spacer/extension containing the scheme's enzyme site is refused or flagged with a
  position; a spacer starting with G is not double-G'd and records that no G was added; the
  PDF render contains each candidate's oligos and a phosphorylation note; the extension
  overhang constants match a cited acceptor and the docstring.
