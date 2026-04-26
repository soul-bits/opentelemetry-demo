"""HTTP helpers for the OpenSearch ``otel-logs-*`` index.

Exposes ``count`` and ``search`` wrappers against ``localhost:9200`` used
by the service-map validator's logs probe and by Case 1 / Case 3
property tests.
"""

from __future__ import annotations

from typing import Any
import httpx


OPENSEARCH_BASE_URL = "http://localhost:9200"
LOG_INDEX_PATTERN = "otel-logs-*"


def count(
    index: str,
    query: dict[str, Any],
    lookback_minutes: int = 5
) -> int:
    """Count documents matching a query in the given index.

    Args:
        index: Index pattern (e.g., "otel-logs-*")
        query: OpenSearch DSL query object
        lookback_minutes: Lookback window in minutes (adds range filter on @timestamp)

    Returns:
        Document count
    """
    # Build range filter for @timestamp.
    range_query = {
        "range": {
            "@timestamp": {
                "gte": f"now-{lookback_minutes}m"
            }
        }
    }

    # Combine with user query using must.
    combined_query = {
        "bool": {
            "must": [query, range_query]
        }
    }

    with httpx.Client() as client:
        response = client.post(
            f"{OPENSEARCH_BASE_URL}/{index}/_count",
            json={"query": combined_query}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("count", 0)


def search(
    index: str,
    query: dict[str, Any],
    size: int = 10,
    lookback_minutes: int = 5
) -> list[dict[str, Any]]:
    """Search for documents matching a query in the given index.

    Args:
        index: Index pattern (e.g., "otel-logs-*")
        query: OpenSearch DSL query object
        size: Maximum number of results to return
        lookback_minutes: Lookback window in minutes

    Returns:
        List of hit documents (from _source field)
    """
    # Build range filter for @timestamp.
    range_query = {
        "range": {
            "@timestamp": {
                "gte": f"now-{lookback_minutes}m"
            }
        }
    }

    # Combine with user query using must.
    combined_query = {
        "bool": {
            "must": [query, range_query]
        }
    }

    with httpx.Client() as client:
        response = client.post(
            f"{OPENSEARCH_BASE_URL}/{index}/_search",
            json={
                "query": combined_query,
                "size": size,
                "sort": [{"@timestamp": {"order": "desc"}}]
            }
        )
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", {}).get("hits", [])
        return [hit.get("_source", {}) for hit in hits]
