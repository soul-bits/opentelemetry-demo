"""Atomic state persistence for ``./.scenario-state.json``.

Tracks ``{active_scenario, activated_at, solve_marker, solved_at,
controller_pid}`` across CLI invocations under a ``filelock``-backed
POSIX advisory lock so mutual exclusion and idempotence survive process
restarts.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, asdict
from typing import Optional
from filelock import FileLock


STATE_FILE = "./.scenario-state.json"
LOCK_FILE = "./.scenario-state.json.lock"


@dataclass
class ScenarioState:
    """Scenario state record."""
    active_scenario: Optional[str] = None
    activated_at: Optional[float] = None
    solve_marker: Optional[bool] = None
    solved_at: Optional[float] = None
    controller_pid: Optional[int] = None


def _acquire_lock():
    """Return an acquired FileLock context manager."""
    return FileLock(LOCK_FILE, timeout=10)


def read_state() -> ScenarioState:
    """Read and parse scenario state from disk under lock.

    Returns ScenarioState with active_scenario=None on file-not-found or
    JSON decode errors (fail-open to Baseline).
    """
    with _acquire_lock():
        try:
            if not os.path.exists(STATE_FILE):
                return ScenarioState()
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            return ScenarioState(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Corrupt or mistyped state file — fail-open to Baseline.
            return ScenarioState()


def write_state(state: ScenarioState) -> None:
    """Atomically write scenario state to disk under lock.

    Uses tempfile.NamedTemporaryFile + os.replace to ensure atomic writes.
    """
    with _acquire_lock():
        data = asdict(state)
        # Remove None values to keep the JSON compact.
        data = {k: v for k, v in data.items() if v is not None}

        # Atomic write: tempfile + replace.
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=os.path.dirname(STATE_FILE) or ".",
            delete=False,
            suffix=".json"
        ) as tmp:
            tmp_path = tmp.name
            json.dump(data, tmp, indent=2)

        try:
            os.replace(tmp_path, STATE_FILE)
        except Exception:
            # Clean up temp file on failure.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def clear_state() -> None:
    """Clear scenario state (idempotent teardown)."""
    with _acquire_lock():
        try:
            os.unlink(STATE_FILE)
        except FileNotFoundError:
            pass
