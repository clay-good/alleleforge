# Tasks

## 1. Type IIS recognition-site screening

- [ ] Add the recognition motif for each supported enzyme (BsmBI `CGTCTC`, BbsI `GAAGAC`,
  BsaI `GGTCTC`) to `VectorScheme`, and screen every emitted insert — sgRNA spacer, pegRNA
  spacer, and the RTT+PBS+motif extension — on both strands at oligo construction.
- [ ] On a hit, refuse to emit the oligo set with a clear error, or attach a prominent
  `internal-<enzyme>-site` flag naming the position.
- [ ] Test: a spacer and an extension each containing the scheme's site are refused/flagged;
  a clean insert is unaffected.

## 2. Conditional 5'-G

- [ ] In `sgrna_oligos` / `pegrna_oligos`, add the 5' G only when the spacer does not already
  begin with G; record whether a G was added.
- [ ] Ensure `reconstruct()` accounts for the conditional G rather than always stripping one.
- [ ] Test: a spacer starting with G is not double-G'd and reports no G added; a
  non-G-initial spacer gets exactly one G.

## 3. Oligos in the PDF + phosphorylation note

- [ ] Add each candidate's cloning oligos (top/bottom sequences and scheme) to the PDF
  render, matching the reporting spec and the HTML render.
- [ ] State the phosphorylation/annealing prerequisite for the chosen scheme in every oligo
  render (HTML and PDF).
- [ ] Test: the PDF render contains a candidate's oligos and its phosphorylation note.

## 4. Cited extension overhangs

- [ ] Move the pegRNA 3'-extension overhangs into the named, citation-bearing pegRNA scheme,
  matched to the acceptor's documented BsaI overhangs.
- [ ] Reconcile the docstring and the constants so they agree.
- [ ] Test: the extension overhang constants match the cited scheme and the docstring.
