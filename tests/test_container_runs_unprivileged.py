"""The network-facing release image does not run its service as root."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_runtime_user_is_fixed_and_the_cache_belongs_to_it() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    users = re.findall(r"^USER\s+(\S+)$", dockerfile, re.MULTILINE)
    assert users == ["10001:10001"]
    assert "groupadd --gid 10001 alleleforge" in dockerfile
    assert "useradd --uid 10001 --gid 10001" in dockerfile
    assert "chown 10001:10001 /cache" in dockerfile
    assert dockerfile.index("chown 10001:10001 /cache") < dockerfile.index("USER 10001:10001")
    assert dockerfile.index("USER 10001:10001") < dockerfile.index('CMD ["uvicorn"')


def test_the_deployment_guide_explains_bind_mount_permissions() -> None:
    guide = " ".join((ROOT / "docs" / "deployment.md").read_text(encoding="utf-8").split())
    assert "UID/GID `10001:10001`" in guide
    assert "readable by 10001" in guide
    assert "writable by 10001" in guide
