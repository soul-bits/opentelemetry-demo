"""Scenario activation state machine, idempotence, and mutual exclusion.

Owns the activate / verify / teardown / status / solve state transitions
for case1, case2, and case3, coordinating atomic writes to
``src/flagd/demo.flagd.json`` and ``src/prometheus/alert-rules.yml`` and
issuing the Prometheus ``/-/reload`` call.

This module currently contains only the CLI/controller contract: custom
exceptions the CLI translates to exit codes, and stub functions that
raise ``NotImplementedError`` until the full state machine lands in
task 3.1. Downstream tasks (3.1, 5.2, 6.7, 7.4) fill in the bodies.
"""

from __future__ import annotations


class LockRejectionError(RuntimeError):
    """Lock acquisition failed, or mutual exclusion rejected the call.

    Raised when another scenario is already active with a different
    identifier (e.g., ``activate case2`` while ``case1`` is active), or
    when the POSIX advisory lock on ``./.scenario-state.json`` cannot be
    acquired. The CLI translates this to exit code ``2``.
    """


class ActivationRollbackError(RuntimeError):
    """Activation failed mid-sequence; partial state has been rolled back.

    Raised after the controller has restored the pre-activation flagd
    JSON and alert-rules snapshots. The message names the failed step
    (per Req 2.7). The CLI translates this to exit code ``3``.
    """


def activate(scenario: str) -> None:
    """Activate the named scenario. Populated by task 3.1."""
    raise NotImplementedError(
        f"activate({scenario!r}) is not implemented yet (pending task 3.1)"
    )


def verify(scenario: str) -> None:
    """Verify the named scenario's alert is firing. Populated by task 3.1."""
    raise NotImplementedError(
        f"verify({scenario!r}) is not implemented yet (pending task 3.1)"
    )


def teardown(scenario: str) -> None:
    """Tear down the named scenario (or ``all``). Populated by task 3.1."""
    raise NotImplementedError(
        f"teardown({scenario!r}) is not implemented yet (pending task 3.1)"
    )


def status() -> None:
    """Print the currently active scenario, if any. Populated by task 3.1."""
    raise NotImplementedError(
        "status() is not implemented yet (pending task 3.1)"
    )


def solve(scenario: str, timed_out: bool = False) -> None:
    """Record solve/timeout for the named scenario. Populated by task 3.1."""
    raise NotImplementedError(
        f"solve({scenario!r}, timed_out={timed_out!r}) is not implemented yet "
        "(pending task 3.1)"
    )
