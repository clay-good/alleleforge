"""Test that JSON Schema export produces valid schemas for every model."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_schemas import export


def test_export_writes_schema_per_model(tmp_path: Path) -> None:
    paths = export(tmp_path)
    assert len(paths) >= 20
    names = {p.name for p in paths}
    assert "Variant.schema.json" in names
    assert "PegRNA.schema.json" in names
    assert "PredictionFloat.schema.json" in names


def test_exported_schemas_are_valid_json(tmp_path: Path) -> None:
    for path in export(tmp_path):
        data = json.loads(path.read_text())
        assert "properties" in data or "type" in data or "$ref" in data


def test_prediction_schema_is_concrete(tmp_path: Path) -> None:
    export(tmp_path)
    schema = json.loads((tmp_path / "PredictionFloat.schema.json").read_text())
    assert "interval" in schema["properties"]
