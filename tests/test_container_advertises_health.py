"""Container runtimes can observe the service's existing liveness contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_image_has_one_bounded_healthcheck_against_the_public_endpoint() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    checks = re.findall(r"^HEALTHCHECK\s+(.+?)\n\s+CMD\s+(\[.+\])$", dockerfile, re.MULTILINE)
    assert len(checks) == 1
    options, command = checks[0]
    assert "--interval=30s" in options
    assert "--timeout=3s" in options
    assert "--start-period=10s" in options
    assert "--retries=3" in options
    assert command.startswith('["python", "-c", ')
    assert "http://127.0.0.1:8000/api/health" in command
    assert "body['status'] == 'ok'" in command


def test_the_probe_runs_under_the_same_unprivileged_identity_as_the_server() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("USER 10001:10001") < dockerfile.index("HEALTHCHECK")
    assert dockerfile.index("HEALTHCHECK") < dockerfile.index('CMD ["uvicorn"')


def test_the_deployment_guide_names_the_inherited_health_state() -> None:
    guide = " ".join((ROOT / "docs" / "deployment.md").read_text(encoding="utf-8").split())
    assert "Docker and Compose report the container as `healthy`" in guide
    assert "GET /api/health" in guide
