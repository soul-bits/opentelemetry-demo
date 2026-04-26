"""HTTP helpers for the Jaeger query API at ``localhost:16686``.

Exposes ``find_traces`` and ``get_trace`` used by the service-map
validator's traces probe and by Case 1 RCA property tests that descend
trace subtrees looking for the ``calculate-quote`` exception event.
Populated by task 2.5.
"""
