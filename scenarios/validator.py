"""Service-map observability validator.

Reads ``service_map.yml`` and, for each active service, runs concurrent
metrics / logs / traces probes against Prometheus, OpenSearch, and
Jaeger, emitting a structured JSON diff. Enforces a 60-second wall-clock
budget and exits non-zero on any missing signal. Populated by task 4.1.
"""
