"""HTTP helpers for the Prometheus server at ``localhost:9090``.

Exposes ``reload``, ``query_instant``, ``list_rules``, and a
``validate_rules_file`` wrapper around ``promtool check rules``. Used by
the scenario controller's activation sequence and by the verify polls.
Populated by task 2.3.
"""
