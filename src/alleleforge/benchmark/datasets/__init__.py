"""CRISPR-Bench datasets — license-aware, provenance-stamped, content-hashed.

Each task draws from a named dataset whose **provenance is declared up front**:
source, license, and citation, mirroring the Phase 3 data registry. The real
public datasets (Rule Set 3, FORECasT, BE-Hive, PRIDICT2, GUIDE-seq) are mostly
*not redistributable* in bulk, so what ships in the repository — and runs in CI —
is a **small synthetic fixture** that exercises the contract; the real corpus is
fetched at runtime through the same consent-gated registry.

A loaded :class:`BenchmarkDataset` exposes a :meth:`~BenchmarkDataset.content_hash`
over its examples. Frozen splits record that hash and re-verify it on read, so a
split is invalidated the instant its underlying data changes.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.benchmark._canon import content_hash
from alleleforge.benchmark.tasks import Example
from alleleforge.types.provenance import DatasetVersion

#: Directory of bundled synthetic dataset fixtures shipped for CI.
FIXTURES_DIR = Path(__file__).parent / "fixtures"


class BenchmarkDataset(BaseModel):
    """A named, provenance-stamped collection of benchmark :class:`Example` rows.

    Attributes:
        name: Dataset identifier, referenced by a :class:`~alleleforge.benchmark.tasks.Task`.
        version: Pinned dataset version.
        license: SPDX-style or descriptive license identifier.
        citation: Literature citation for the source corpus.
        source_url: Where the full corpus is fetched from.
        redistributable: Whether the *full* corpus may be vendored (the shipped
            fixture always may; this flag describes the upstream data).
        synthetic: ``True`` when these rows are a synthetic CI stand-in.
        examples: The scored rows.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    license: str
    citation: str
    source_url: str | None = None
    redistributable: bool = False
    synthetic: bool = False
    examples: tuple[Example, ...] = ()

    def content_hash(self) -> str:
        """Return a stable SHA-256 over the dataset's examples.

        The hash covers example ids, inputs, and labels (not the provenance
        metadata), so re-pinning a citation does not invalidate a frozen split
        but changing a label does.
        """
        payload = [
            {"example_id": e.example_id, "inputs": e.inputs, "label": e.label}
            for e in self.examples
        ]
        return content_hash(payload)

    def by_id(self) -> dict[str, Example]:
        """Return the examples keyed by :attr:`Example.example_id`."""
        return {e.example_id: e for e in self.examples}

    def dataset_version(self) -> DatasetVersion:
        """Return the provenance :class:`DatasetVersion` for this dataset."""
        return DatasetVersion(
            name=self.name,
            version=self.version,
            source_url=self.source_url,
            license=self.license,
            sha256=self.content_hash(),
            citation=self.citation,
            redistributable=self.redistributable,
        )


def load_dataset(name: str, *, fixtures_dir: Path = FIXTURES_DIR) -> BenchmarkDataset:
    """Load the bundled fixture for dataset ``name``.

    Args:
        name: The dataset name (matches a ``fixtures/<name>.json`` file).
        fixtures_dir: Override for the fixtures directory (tests).

    Returns:
        The parsed, validated :class:`BenchmarkDataset`.

    Raises:
        FileNotFoundError: If no fixture by that name exists.
    """
    path = fixtures_dir / f"{name}.json"
    if not path.is_file():
        available = sorted(p.stem for p in fixtures_dir.glob("*.json"))
        raise FileNotFoundError(f"no benchmark dataset {name!r}; available: {available}")
    data = json.loads(path.read_text())
    return BenchmarkDataset.model_validate(data)


def available_datasets(*, fixtures_dir: Path = FIXTURES_DIR) -> tuple[str, ...]:
    """Return the names of every bundled dataset fixture, sorted."""
    return tuple(sorted(p.stem for p in fixtures_dir.glob("*.json")))
