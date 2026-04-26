"""CLI entry point for the SRE debug challenge scenarios.

Usage::

    python -m scenarios.scenarios activate {case1|case2|case3}
    python -m scenarios.scenarios verify   {case1|case2|case3}
    python -m scenarios.scenarios teardown {case1|case2|case3|all}
    python -m scenarios.scenarios status
    python -m scenarios.scenarios solve    {case1|case2|case3} [--timed-out]

Exit codes (design § Error Handling / Scenario controller failure modes):

* ``0``   — success (including idempotent no-ops)
* ``1``   — unexpected error (e.g. unimplemented stub, unhandled exception)
* ``2``   — lock acquisition / mutual-exclusion rejection
    (note: argparse also uses ``2`` for usage errors; both map to the same
    "command refused without side effects" semantic, so the overlap is
    benign)
* ``3``   — mid-activation rollback triggered by a failed step
* ``130`` — SIGINT (Ctrl-C; Unix convention 128 + SIGINT=2)
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from scenarios import controller
from scenarios.controller import ActivationRollbackError, LockRejectionError


SCENARIO_CHOICES = ("case1", "case2", "case3")
TEARDOWN_CHOICES = ("case1", "case2", "case3", "all")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scenarios.scenarios",
        description=(
            "Activate, verify, or tear down SRE debug challenge "
            "fault-injection scenarios."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    activate_p = subparsers.add_parser(
        "activate",
        help="Activate a scenario (flag flip + alert rule + Prometheus reload).",
    )
    activate_p.add_argument("scenario", choices=SCENARIO_CHOICES)

    verify_p = subparsers.add_parser(
        "verify",
        help="Verify a scenario's alert is firing and MLT signals are present.",
    )
    verify_p.add_argument("scenario", choices=SCENARIO_CHOICES)

    teardown_p = subparsers.add_parser(
        "teardown",
        help=(
            "Tear down a scenario (restore flag; Case 3 also restarts "
            "product-reviews)."
        ),
    )
    teardown_p.add_argument("scenario", choices=TEARDOWN_CHOICES)

    subparsers.add_parser(
        "status",
        help="Print the currently active scenario, if any.",
    )

    solve_p = subparsers.add_parser(
        "solve",
        help="Record that the trainee reached (or timed out on) the root cause.",
    )
    solve_p.add_argument("scenario", choices=SCENARIO_CHOICES)
    solve_p.add_argument(
        "--timed-out",
        action="store_true",
        help="Mark the attempt as timed out instead of solved.",
    )

    return parser


def _dispatch(args: argparse.Namespace) -> None:
    if args.command == "activate":
        controller.activate(args.scenario)
        return
    if args.command == "verify":
        controller.verify(args.scenario)
        return
    if args.command == "teardown":
        controller.teardown(args.scenario)
        return
    if args.command == "status":
        controller.status()
        return
    if args.command == "solve":
        controller.solve(args.scenario, timed_out=args.timed_out)
        return
    # argparse's ``required=True`` subparsers prevent this branch; guard anyway.
    raise AssertionError(f"unknown command: {args.command!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _dispatch(args)
    except KeyboardInterrupt:
        # Standard Unix convention: 128 + SIGINT(2) = 130.
        return 130
    except LockRejectionError as exc:
        print(f"scenarios: lock/mutual-exclusion rejection: {exc}", file=sys.stderr)
        return 2
    except ActivationRollbackError as exc:
        print(f"scenarios: activation rolled back: {exc}", file=sys.stderr)
        return 3
    except NotImplementedError as exc:
        # Stub path: expected in the current milestone. Keep the output clean.
        print(f"scenarios: not implemented: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
