#!/usr/bin/env python
"""Derive the version-independent Rule Set 3 booster from the `rs3` package.

The trained Rule Set 3 model ships inside the Apache-2.0 `rs3` package as a
pickled scikit-learn-wrapped LightGBM regressor (`RuleSet3.pkl`). That pickle is
version-fragile: it only unpickles under the legacy `lightgbm<=3.3.5` /
`scikit-learn<=1.0.2` that `rs3` pins, neither of which has a wheel on modern
Python. This script converts it **once** into LightGBM's version-independent
**text booster** format (`RuleSet3.txt`), which loads under any LightGBM and is
what AlleleForge resolves through the model zoo (consent + checksum gated).

The conversion is exact: the text booster reproduces the pickle's predictions to
the bit (verified in tests/scoring/test_cas9_efficiency.py, opt-in lane).

This is a maintainer tool, run once in a legacy environment, not part of the
package runtime. After running it, upload `RuleSet3.txt` as the release asset the
`rule-set-3` model card pins (`source_url`), and confirm the printed SHA-256
matches the card's `checkpoint_sha256`.

Setup (legacy env; `rs3`'s pins do not install on Python >= 3.11):

    python3.10 -m venv rs3env && source rs3env/bin/activate
    pip install --no-deps rs3 sglearn
    pip install "numpy<2" pandas "lightgbm<=3.3.5" biopython joblib seqfold packaging
    # macOS: brew install libomp   (LightGBM's OpenMP runtime)

Usage:
    python scripts/export_rs3_booster.py --out RuleSet3.txt
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("RuleSet3.txt"), help="Destination text booster path."
    )
    args = parser.parse_args()

    try:
        from rs3.seq import load_seq_model
    except ImportError:
        print(
            "error: `rs3` is not importable. Run this in the legacy env described in "
            "the module docstring.",
            file=sys.stderr,
        )
        return 1

    model = load_seq_model()
    # The legacy sklearn-wrapper pickle leaves `_n_classes` unset; modern LightGBM
    # reads it during predict/save. A regressor has a single output.
    if getattr(model, "_n_classes", None) is None:
        model._n_classes = 1
    model.booster_.save_model(str(args.out))

    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    print(f"sha256: {digest}")
    print("Set this as the `rule-set-3` card's checkpoint_sha256 and host the file at source_url.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
