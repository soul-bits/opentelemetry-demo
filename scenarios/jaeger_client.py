"""HTTP helpers for the Jaeger query API at ``localhost:16686``.

Exposes ``find_traces`` and ``get_trace`` used by the service-map
validator's traces probe and by Case 1 RCA property tests that descend
trace subtrees looking for the ``calculate-quote`` exception event.
"""

from __future__ import annotations

from typing import Any, Optional
import httpx


JAEGER_BASE_URL = "http://localhost:16686"


def find_traces(
    service: str,
    operation: Optional[str] = None,
    lookback_minutes: int = 5,
    limit: int = 100,
    tags: Optional[dict[str, str]] = None
) -> list[dict[str, Any]]:
    """Find traces for a given service and optional operation/tags.

    Args:
        service: Service name
        operation: Optional operation name
        lookback_minutes: Lookback window in minutes
        limit: Maximum number of traces to return
        tags: Optional dict of tags to filter by (e.g., {"error": "true"})

    Returns:
        List of trace objects from the Jaeger API
    """
    params = {
        "service": service,
        "limit": limit,
        "lookback": f"{lookback_minutes}m"
    }

    if operation:
        params["operation"] = operation

    if tags:
        # Tags are passed as space-separated key:value pairs.
        tag_strings = [f"{k}:{v}" for k, v in tags.items()]
        params["tags"] = " ".join(tag_strings)

    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{JAEGER_BASE_URL}/api/traces",
            params=params
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])


def get_trace(trace_id: str) -> dict[str, Any]:
    """Fetch a single trace by ID.

    Args:
        trace_id: The trace ID

    Returns:
        The trace object
    """
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{JAEGER_BASE_URL}/api/traces/{trace_id}")
        response.raise_for_status()
        data = response.json()
        return data.get("data", {})
