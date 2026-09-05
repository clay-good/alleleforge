"""JSON Schema export: validity, concreteness, and freshness of the committed files."""

from __future__ import annotations

import json
import tempfile
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


def test_committed_schemas_match_the_code() -> None:
    """The published schemas in ``docs/schemas/`` must be a current export.

    These files are the machine-readable contract AlleleForge publishes, and they
    are consumed by people who never read the Python. Nothing regenerated them
    automatically and nothing checked them, so they drifted silently: at the time
    this guard was written, ten were stale, and `Variant` — the core input type —
    had been missing its `source_assembly` field for many releases. A consumer
    validating against the published schema would have rejected a document the
    library emits.

    Regenerate with ``python scripts/export_schemas.py``.
    """
    committed = Path(__file__).resolve().parents[1] / "docs" / "schemas"
    with tempfile.TemporaryDirectory() as tmp:
        fresh_dir = Path(tmp)
        export(fresh_dir)
        fresh = {p.name: json.loads(p.read_text()) for p in fresh_dir.glob("*.schema.json")}

    on_disk = {p.name: json.loads(p.read_text()) for p in committed.glob("*.schema.json")}
    assert set(on_disk) == set(fresh), (
        "docs/schemas/ has files the exporter does not emit (or is missing some); "
        "run python scripts/export_schemas.py"
    )
    stale = sorted(name for name, schema in fresh.items() if on_disk[name] != schema)
    assert not stale, (
        f"{len(stale)} committed schema(s) are out of date with the models: "
        f"{', '.join(stale)}. Run python scripts/export_schemas.py"
    )
