"""Scenario activation state machine, idempotence, and mutual exclusion.

Owns the activate / verify / teardown / status / solve state transitions
for case1, case2, and case3, coordinating atomic writes to
``src/flagd/demo.flagd.json`` and ``src/prometheus/alert-rules.yml`` and
issuing the Prometheus ``/-/reload`` call.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Optional

from scenarios import state_file, flagd_client, prometheus_client
from scenarios.state_file import ScenarioState


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


# Alert rule names per scenario
ALERT_NAMES = {
    "case1": "AnomalousZeroValueOrders",
    "case2": "PaymentServiceUnreachable",
    "case3": "ProductReviewsMemoryHigh",
}

# Expected time-to-fire (in seconds) per scenario
TIME_TO_FIRE = {
    "case1": 300,  # 5 minutes
    "case2": 60,   # 1 minute
    "case3": 900,  # 15 minutes
}

PROMETHEUS_RULES_PATH = "src/prometheus/alert-rules.yml"
TEMP_DIR = os.path.expanduser("~/.scenarios-tmp")


def _ensure_temp_dir() -> None:
    """Ensure temporary directory exists."""
    os.makedirs(TEMP_DIR, exist_ok=True)


def _get_flagd_backup_path() -> str:
    """Get path for flagd backup during activation."""
    _ensure_temp_dir()
    return os.path.join(TEMP_DIR, "flagd-backup.json")


def _get_rules_backup_path() -> str:
    """Get path for alert rules backup during activation."""
    _ensure_temp_dir()
    return os.path.join(TEMP_DIR, "alert-rules-backup.yml")


def activate(scenario: str) -> None:
    """Activate the named scenario (flag + alert rule + Prometheus reload)."""
    if scenario not in ALERT_NAMES:
        raise ValueError(f"Unknown scenario: {scenario}")

    # Read current state
    current_state = state_file.read_state()

    # Mutual exclusion: if different scenario is active, reject
    if current_state.active_scenario and current_state.active_scenario != scenario:
        raise LockRejectionError(
            f"Scenario {current_state.active_scenario!r} is already active; "
            f"cannot activate {scenario!r}"
        )

    # Idempotence: if same scenario already active, no-op
    if current_state.active_scenario == scenario:
        print(f"Scenario {scenario!r} already active (idempotent)", file=sys.stderr)
        return

    # Begin activation sequence (with rollback on failure)
    flagd_backup = _get_flagd_backup_path()
    rules_backup = _get_rules_backup_path()

    try:
        # Step 1: Read flagd config
        try:
            flags = flagd_client.read_flags()
        except Exception as e:
            raise ActivationRollbackError(f"Failed to read flagd config: {e}")

        # Step 2: Snapshot flagd for rollback
        flagd_client.write_flags(flags, flagd_backup)

        # Step 3: Mutate the appropriate flag
        if scenario == "case1":
            if "quoteSilentCorruption" not in flags.get("flags", {}):
                raise ActivationRollbackError(
                    "quoteSilentCorruption flag not found in flagd config"
                )
            flags["flags"]["quoteSilentCorruption"]["defaultVariant"] = "on"
        elif scenario == "case2":
            if "paymentUnreachable" not in flags.get("flags", {}):
                raise ActivationRollbackError(
                    "paymentUnreachable flag not found in flagd config"
                )
            flags["flags"]["paymentUnreachable"]["defaultVariant"] = "on"
        elif scenario == "case3":
            if "productReviewsMemoryLeak" not in flags.get("flags", {}):
                raise ActivationRollbackError(
                    "productReviewsMemoryLeak flag not found in flagd config"
                )
            flags["flags"]["productReviewsMemoryLeak"]["defaultVariant"] = "on"

        # Step 4: Write flagd atomically
        try:
            flagd_client.write_flags(flags, flagd_backup)
        except Exception as e:
            raise ActivationRollbackError(f"Failed to write flagd config: {e}")

        # Step 5: Ensure alert rule is present
        try:
            _ensure_alert_rule_present(scenario, rules_backup)
        except Exception as e:
            raise ActivationRollbackError(f"Failed to ensure alert rule: {e}")

        # Step 6: Reload Prometheus
        try:
            prometheus_client.reload()
        except Exception as e:
            raise ActivationRollbackError(f"Failed to reload Prometheus: {e}")

        # Step 7: Poll for alert rule presence
        try:
            _poll_for_alert_rule(scenario, timeout=5)
        except Exception as e:
            raise ActivationRollbackError(f"Failed to verify alert rule loaded: {e}")

        # Step 8: Update state file
        new_state = ScenarioState(
            active_scenario=scenario,
            activated_at=time.time(),
        )
        state_file.write_state(new_state)

        # Step 9: Print activation summary
        alert_name = ALERT_NAMES[scenario]
        time_to_fire = TIME_TO_FIRE[scenario]
        print(
            f"Activated scenario {scenario!r}: alert {alert_name!r} "
            f"should fire within {time_to_fire}s",
            file=sys.stderr,
        )

    except ActivationRollbackError:
        # Rollback on failure
        try:
            if os.path.exists(flagd_backup):
                flagd_client.restore_from_backup(flagd_backup)
            if os.path.exists(rules_backup):
                with open(rules_backup, "r") as f:
                    original_rules = f.read()
                with open(PROMETHEUS_RULES_PATH, "w") as f:
                    f.write(original_rules)
        except Exception as rollback_error:
            print(
                f"Warning: rollback also failed: {rollback_error}",
                file=sys.stderr,
            )
        raise


def verify(scenario: str) -> None:
    """Verify the named scenario's alert is firing."""
    if scenario not in ALERT_NAMES:
        raise ValueError(f"Unknown scenario: {scenario}")

    alert_name = ALERT_NAMES[scenario]
    time_to_fire = TIME_TO_FIRE[scenario]
    grace_period = 60  # Wait 60s before first poll (Req 2.5)

    # Wait grace period
    print(f"Waiting {grace_period}s before polling for alert...", file=sys.stderr)
    time.sleep(grace_period)

    # Poll for alert
    deadline = time.time() + time_to_fire
    poll_interval = 5

    while time.time() < deadline:
        try:
            result = prometheus_client.query_instant(
                f'ALERTS{{alertname="{alert_name}", alertstate="firing"}}'
            )
            data = result.get("data", {}).get("result", [])
            if data:
                print(f"✓ Alert {alert_name!r} is firing", file=sys.stderr)
                return
        except Exception:
            pass

        time.sleep(poll_interval)

    raise RuntimeError(
        f"Alert {alert_name!r} did not fire within {time_to_fire}s"
    )


def teardown(scenario: str) -> None:
    """Tear down the named scenario (or ``all``)."""
    # Read current state
    current_state = state_file.read_state()

    # Idempotence: teardown when nothing is active is a no-op
    if not current_state.active_scenario:
        print("No active scenario to tear down", file=sys.stderr)
        return

    # If tearing down a specific scenario, verify it matches
    if scenario != "all" and current_state.active_scenario != scenario:
        raise ValueError(
            f"Scenario {scenario!r} is not active "
            f"(active: {current_state.active_scenario!r})"
        )

    active = current_state.active_scenario

    try:
        # Step 1: Restore flagd (flip flag back to off)
        try:
            flags = flagd_client.read_flags()

            if active == "case1":
                flags["flags"]["quoteSilentCorruption"]["defaultVariant"] = "off"
            elif active == "case2":
                flags["flags"]["paymentUnreachable"]["defaultVariant"] = "off"
            elif active == "case3":
                flags["flags"]["productReviewsMemoryLeak"]["defaultVariant"] = "off"

            backup = _get_flagd_backup_path()
            flagd_client.write_flags(flags, backup)
        except Exception as e:
            raise RuntimeError(f"Failed to update flagd during teardown: {e}")

        # Step 2: Restart product-reviews if Case 3
        if active == "case3":
            try:
                subprocess.run(
                    [
                        "docker",
                        "compose",
                        "-f",
                        "docker-compose.minimal.yml",
                        "restart",
                        "product-reviews",
                    ],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to restart product-reviews: {e}")

        # Step 3: Reload Prometheus
        try:
            prometheus_client.reload()
        except Exception as e:
            raise RuntimeError(f"Failed to reload Prometheus during teardown: {e}")

        # Step 4: Clear state
        state_file.clear_state()

        print(f"Tore down scenario {active!r}", file=sys.stderr)

    except Exception as e:
        print(f"Teardown failed: {e}", file=sys.stderr)
        raise


def status() -> None:
    """Print the currently active scenario, if any."""
    current_state = state_file.read_state()

    if current_state.active_scenario:
        elapsed = time.time() - (current_state.activated_at or 0)
        print(
            f"Active scenario: {current_state.active_scenario!r} "
            f"(activated {elapsed:.0f}s ago)"
        )
    else:
        print("No active scenario")


def solve(scenario: str, timed_out: bool = False) -> None:
    """Record that trainee reached (or timed out on) root cause."""
    current_state = state_file.read_state()

    if not current_state.active_scenario:
        print("Warning: no active scenario to mark solved", file=sys.stderr)
        return

    if current_state.active_scenario != scenario:
        raise ValueError(
            f"Scenario {scenario!r} is not active "
            f"(active: {current_state.active_scenario!r})"
        )

    now = time.time()
    elapsed = now - (current_state.activated_at or 0)

    # Case 1: warn if solved too quickly
    if scenario == "case1" and not timed_out and elapsed < 900:  # 15 min
        print(
            f"Warning: Case 1 solved in {elapsed:.0f}s (expected 30+ min)",
            file=sys.stderr,
        )

    # Case 3: error if marked solved (should always time out)
    if scenario == "case3" and not timed_out:
        print(
            f"Error: Case 3 should NOT be marked solved (it's impossible). "
            f"Use --timed-out flag.",
            file=sys.stderr,
        )
        return

    # Update state with solve marker
    updated_state = ScenarioState(
        active_scenario=current_state.active_scenario,
        activated_at=current_state.activated_at,
        solve_marker=not timed_out,  # True if solved, False if timed out
        solved_at=now,
    )
    state_file.write_state(updated_state)

    status_str = "solved" if not timed_out else "timed out"
    print(
        f"Marked scenario {scenario!r} as {status_str} "
        f"(elapsed: {elapsed:.0f}s)",
        file=sys.stderr,
    )


def _ensure_alert_rule_present(scenario: str, backup_path: str) -> None:
    """Ensure alert rule exists in prometheus rules file."""
    alert_name = ALERT_NAMES[scenario]

    # Read current rules file
    with open(PROMETHEUS_RULES_PATH, "r") as f:
        rules_content = f.read()

    # Backup original
    with open(backup_path, "w") as f:
        f.write(rules_content)

    # Check if alert rule is present
    if f"alert: {alert_name}" in rules_content:
        return  # Already present

    # If not present, this is an error (rule should exist from task 5/6/7)
    raise RuntimeError(
        f"Alert rule {alert_name!r} not found in {PROMETHEUS_RULES_PATH}. "
        f"Has task 5/6/7 been completed?"
    )


def _poll_for_alert_rule(scenario: str, timeout: int = 5) -> None:
    """Poll Prometheus /api/v1/rules until alert rule is loaded."""
    alert_name = ALERT_NAMES[scenario]
    deadline = time.time() + timeout
    poll_interval = 0.5

    while time.time() < deadline:
        try:
            rules = prometheus_client.list_rules()
            # Search for the alert rule in the loaded rules
            for group in rules:
                for rule in group.get("rules", []):
                    if rule.get("name") == alert_name:
                        return  # Found it
        except Exception:
            pass

        time.sleep(poll_interval)

    raise RuntimeError(
        f"Alert rule {alert_name!r} did not load within {timeout}s"
    )
