"""Atomic state persistence for ``./.scenario-state.json``.

Tracks ``{active_scenario, activated_at, solve_marker, solved_at,
controller_pid}`` across CLI invocations under a ``filelock``-backed
POSIX advisory lock so mutual exclusion and idempotence survive process
restarts. Populated by task 2.1.
"""
