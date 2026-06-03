# Scope & responsible use

!!! warning "Research tool — not medical advice"
    AlleleForge produces hypotheses and rankings, not medical advice or clinical decisions. Every
    generated report repeats this.

- **Research use only.** AlleleForge is computational. It produces ranked, explicitly uncertain
  *predictions* for research and method development. It contains no wet-lab protocols and no
  synthesis instructions.
- **Off-target predictions require experimental validation.** Computational nomination narrows the
  search; it does not replace GUIDE-seq / CHANGE-seq / amplicon confirmation.
- **No telemetry, no phone-home.** All computation runs locally or on user-controlled
  infrastructure. User sequences are never transmitted externally.
- **Honest uncertainty over false confidence.** Where models are out of distribution, AlleleForge
  flags it rather than hiding it.
- **Dual-use awareness.** This is a design and safety-analysis tool for legitimate therapeutic and
  basic research.

## Licensing

AlleleForge is released under the MIT License — all code, schemas, benchmark, and any first-party
model weights. Each wrapped third-party tool or model retains its own upstream license, recorded in
its card; the registry refuses to bundle any component whose license is incompatible with
redistribution and fetches it at runtime with the user's consent instead.
