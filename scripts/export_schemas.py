#!/usr/bin/env python
"""Emit JSON Schema for every public AlleleForge model into ``docs/schemas/``.

Wired into the docs build so the published schemas never drift from the code.
Run directly: ``python scripts/export_schemas.py [output_dir]``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import alleleforge.types as t

#: Public models to emit schemas for. Generic models (Prediction) are
#: parametrized so the schema is concrete.
_MODELS: list[type[BaseModel]] = [
    t.DNASequence,
    t.GenomicInterval,
    t.Variant,
    t.ClinVarAccession,
    t.DbSnpId,
    t.PAM,
    t.Spacer,
    t.Guide,
    t.BaseEditWindow,
    t.NickingGuide,
    t.PegRNA,
    t.AlleleOutcome,
    t.EditOutcome,
    t.EditStrategy,
    t.OffTargetSite,
    t.OffTargetReport,
    t.DesignCandidate,
    t.RankedMenu,
    t.ToolVersion,
    t.DatasetVersion,
    t.ModelCheckpoint,
    t.Provenance,
]


def _schema_for(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()


def export(output_dir: Path) -> list[Path]:
    """Write one ``<Model>.schema.json`` per public model to ``output_dir``.

    Args:
        output_dir: Directory to write schema files into (created if absent).

    Returns:
        The list of written file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    # Prediction is generic; emit a float-parametrized concrete schema too.
    schemas: dict[str, dict[str, Any]] = {m.__name__: _schema_for(m) for m in _MODELS}
    schemas["PredictionFloat"] = t.Prediction[float].model_json_schema()
    for name, schema in schemas.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written


def main() -> int:
    """Export schemas to the path in ``argv[1]`` or ``docs/schemas/``."""
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/schemas")
    paths = export(target)
    print(f"wrote {len(paths)} schemas to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
