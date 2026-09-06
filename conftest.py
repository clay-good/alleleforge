"""Repository-root pytest configuration.

Makes the repository root importable so tests can import ``scripts.*``, and enforces
the opt-in markers centrally.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterable

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#: Markers whose tests reach outside the repository — real model weights, a live
#: external service — paired with the environment variable that opts in. "CI stays
#: weight-free" is a non-negotiable design principle (`openspec/project.md`), and it
#: was upheld only by each such test opening with its own hand-written `pytest.skip`
#: when the extra or the artifact was absent. Six correct guards and no mechanism: a
#: new one that forgot would download real weights in CI, and the marker's own
#: description already claims the marker does this ("opt-in, skipped in CI"). This
#: makes the claim true in one place. `native` is deliberately absent — it has its own
#: CI job selecting it with `-m native`, which this would turn into a no-op.
_OPT_IN_MARKERS: dict[str, str] = {
    "real_weights": "ALLELEFORGE_REAL_WEIGHTS",
    "live_integration": "ALLELEFORGE_LIVE_INTEGRATION",
}


def pytest_collection_modifyitems(config: pytest.Config, items: Iterable[pytest.Item]) -> None:
    """Skip opt-in tests unless their environment variable is set."""
    for marker, env_var in _OPT_IN_MARKERS.items():
        if os.environ.get(env_var):
            continue
        skip = pytest.mark.skip(
            reason=f"opt-in: set {env_var}=1 to run {marker!r} tests (they reach "
            "outside the repository)"
        )
        for item in items:
            if marker in item.keywords:
                item.add_marker(skip)
