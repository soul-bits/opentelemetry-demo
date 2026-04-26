"""HTTP helpers for the Prometheus server at ``localhost:9090``.

Exposes ``reload``, ``query_instant``, ``list_rules``, and a
``validate_rules_file`` wrapper around ``promtool check rules``. Used by
the scenario controller's activation sequence and by the verify polls.
"""

from __future__ import annotations

import subprocess
from typing import Any
import httpx


PROMETHEUS_BASE_URL = "http://localhost:9090"


def reload() -> None:
    """Trigger a Prometheus configuration reload via POST /-/reload.

    Raises httpx.HTTPError on non-200 response.
    """
    with httpx.Client() as client:
        response = client.post(f"{PROMETHEUS_BASE_URL}/-/reload")
        response.raise_for_status()


def query_instant(promql: str) -> dict[str, Any]:
    """Execute a Prometheus instant query.

    Args:
        promql: PromQL expression

    Returns:
        The parsed JSON response from /api/v1/query
    """
    with httpx.Client() as client:
        response = client.get(
            f"{PROMETHEUS_BASE_URL}/api/v1/query",
            params={"query": promql}
        )
        response.raise_for_status()
        return response.json()


def list_rules() -> list[dict[str, Any]]:
    """List currently loaded alert rules.

    Returns:
        List of rule group dicts from /api/v1/rules
    """
    with httpx.Client() as client:
        response = client.get(f"{PROMETHEUS_BASE_URL}/api/v1/rules")
        response.raise_for_status()
        data = response.json()
        # Response has {"status": "success", "data": {"groups": [...]}}
        return data.get("data", {}).get("groups", [])


def validate_rules_file(path: str) -> None:
    """Validate a Prometheus rules file using promtool.

    Args:
        path: Path to the rules file

    Raises:
        subprocess.CalledProcessError if promtool validation fails
    """
    subprocess.run(
        ["promtool", "check", "rules", path],
        check=True,
        capture_output=True
    )
