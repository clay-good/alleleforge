"""CRISPR-Bench splits — frozen, content-hashed train/val/test partitions.

A split is **immutable once published**. Each split file pins:

* the membership of the ``train`` / ``val`` / ``test`` folds (example ids), with
  deliberate **cross-context** test folds that hold out whole cell types or
  chromatin contexts to measure generalization rather than memorization;
* the content hash of the dataset it was cut from, so the loader can detect that
  the underlying data has drifted out from under the split;
* a hash of the split's own membership, so the file cannot be silently edited.

:func:`load_split` recomputes and verifies **both** hashes on read and raises
:class:`SplitIntegrityError` on any mismatch. Changing the data — or the split —
requires minting a new split *version*; you never edit a published one.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from alleleforge.benchmark._canon import content_hash
from alleleforge.benchmark.datasets import BenchmarkDataset, load_dataset
from alleleforge.benchmark.tasks import Example

#: Directory of bundled frozen split files.
SPLITS_DIR = Path(__file__).parent


class SplitIntegrityError(RuntimeError):
    """Raised when a split's stored hash disagrees with its recomputed hash."""


class Split(BaseModel):
    """A frozen train/val/test partition over a benchmark dataset.

    Attributes:
        split_version: The split's immutable version tag (e.g. ``"v1"``).
        task: The task this split is intended for.
        dataset: The dataset name the example ids index into.
        dataset_sha256: The expected :meth:`BenchmarkDataset.content_hash`.
        rationale: How the test fold was held out (the generalization story).
        train: Training-fold example ids.
        val: Validation-fold example ids.
        test: Test-fold example ids.
        split_sha256: Hash over the membership + binding fields (self-integrity).
    """

    model_config = ConfigDict(frozen=True)

    split_version: str
    task: str
    dataset: str
    dataset_sha256: str
    rationale: str
    train: tuple[str, ...]
    val: tuple[str, ...]
    test: tuple[str, ...]
    split_sha256: str

    def membership_hash(self) -> str:
        """Return the recomputed self-integrity hash over the binding + folds."""
        return content_hash(
            {
                "split_version": self.split_version,
                "task": self.task,
                "dataset": self.dataset,
                "dataset_sha256": self.dataset_sha256,
                "train": list(self.train),
                "val": list(self.val),
                "test": list(self.test),
            }
        )

    def verify(self, dataset: BenchmarkDataset) -> None:
        """Verify the split against ``dataset``; raise on any mismatch.

        Raises:
            SplitIntegrityError: If the split file was edited (membership hash
                mismatch) or the dataset content drifted (dataset hash mismatch).
        """
        if self.membership_hash() != self.split_sha256:
            raise SplitIntegrityError(
                f"split {self.task}/{self.split_version} membership hash mismatch — "
                "the split file was modified; mint a new version instead of editing it"
            )
        actual = dataset.content_hash()
        if actual != self.dataset_sha256:
            raise SplitIntegrityError(
                f"split {self.task}/{self.split_version} expects dataset hash "
                f"{self.dataset_sha256[:12]}… but {dataset.name} now hashes to "
                f"{actual[:12]}… — the data changed; a frozen split cannot follow it"
            )

    def examples(self, dataset: BenchmarkDataset, fold: str) -> tuple[Example, ...]:
        """Return the ``fold`` examples from ``dataset`` in stored order.

        Args:
            dataset: The dataset to draw rows from (already hash-verified).
            fold: One of ``"train"``, ``"val"``, ``"test"``.

        Returns:
            The examples for the fold.

        Raises:
            ValueError: If ``fold`` is not a recognized fold name.
            KeyError: If a referenced id is absent from ``dataset``.
        """
        if fold not in ("train", "val", "test"):
            raise ValueError(f"unknown fold {fold!r}; use train/val/test")
        ids: tuple[str, ...] = getattr(self, fold)
        index = dataset.by_id()
        return tuple(index[i] for i in ids)


def load_split(
    task: str,
    *,
    version: str = "v1",
    splits_dir: Path = SPLITS_DIR,
    dataset: BenchmarkDataset | None = None,
) -> tuple[Split, BenchmarkDataset]:
    """Load and integrity-check the frozen split for ``task``.

    Args:
        task: The task name (matches ``splits/<task>.<version>.json``).
        version: The split version to load.
        splits_dir: Override for the splits directory (tests).
        dataset: A pre-loaded dataset to verify against; loaded from the bundled
            fixtures if omitted.

    Returns:
        ``(split, dataset)`` with both integrity checks passed.

    Raises:
        FileNotFoundError: If the split file is missing.
        SplitIntegrityError: If either hash check fails.
    """
    path = splits_dir / f"{task}.{version}.json"
    if not path.is_file():
        available = sorted(p.name for p in splits_dir.glob("*.json"))
        raise FileNotFoundError(f"no split {task!r}@{version!r}; available: {available}")
    split = Split.model_validate_json(path.read_text())
    ds = dataset if dataset is not None else load_dataset(split.dataset)
    split.verify(ds)
    return split, ds
