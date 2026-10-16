#!/usr/bin/env python3
"""Find every largest-remainder reversal in a bounded ZTO budget window."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys


SPEC = importlib.util.spec_from_file_location(
    "rewardreceipt", Path(__file__).resolve().parents[1] / "rewardreceipt" / "rewardreceipt.py")
rr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rr)
rs = rr.rs
MAX_STEPS = 128


def scan(request, metadata, steps):
    """Enumerate each consecutive atomic-unit budget; never interpolate gaps."""
    rs.require(type(steps) is int and 1 <= steps <= MAX_STEPS,
               "steps must be an integer from 1 to 128")
    first = rs.allocate(request, metadata)
    start = int(first["budget_units"])
    rs.require(start + steps <= rs.UINT256_MAX, "window exceeds uint256 budget")
    previous = first
    reversals = []
    decreases = {row["id"]: 0 for row in first["allocations"]}
    for offset in range(1, steps + 1):
        budget = start + offset
        next_request = dict(request, budget=rs.display_units(budget, metadata["decimals"]))
        current = rs.allocate(next_request, metadata)
        losses = []
        deltas = []
        for before, after in zip(previous["allocations"], current["allocations"]):
            delta = int(after["units"]) - int(before["units"])
            deltas.append(delta)
            if delta < 0:
                losses.append({"id": before["id"], "before_units": before["units"],
                               "after_units": after["units"]})
                decreases[before["id"]] += 1
        assert sum(deltas) == 1
        if losses:
            reversals.append({"at_budget_units": str(budget), "contributors_losing": losses})
        previous = current
    result = {
        "schema": "rewardwindow-v1",
        "token": first["token"],
        "request_sha256": rr.digest(request),
        "metadata_sha256": rr.digest(metadata),
        "start_report_sha256": rr.digest(first),
        "end_report_sha256": rr.digest(previous),
        "start_budget_units": str(start),
        "end_budget_units": str(start + steps),
        "steps_checked": steps,
        "transitions_with_reversal": len(reversals),
        "contributors_with_reversals": [
            {"id": identifier, "decrease_count": count}
            for identifier, count in decreases.items() if count
        ],
        "reversals": reversals,
        "scope": "every consecutive atomic-unit budget in this window; arithmetic only, no payment or entitlement",
    }
    encoded = (json.dumps(result, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    rs.require(len(encoded) <= rs.MAX_BYTES, "scan report exceeds 256-KiB limit; shorten the window")
    return result


def verify(request, metadata, report):
    rs.require(isinstance(report, dict), "scan report must be an object")
    expected = scan(request, metadata, report.get("steps_checked"))
    rs.require(rr.canonical_bytes(report) == rr.canonical_bytes(expected),
               "scan report differs from a complete recomputation")
    return {"schema": "rewardwindow-verification-v1",
            "result": "verified every atomic-unit transition in window",
            "scan_sha256": rr.digest(report),
            "transitions_with_reversal": expected["transitions_with_reversal"],
            "start_budget_units": expected["start_budget_units"],
            "end_budget_units": expected["end_budget_units"],
            "scope": expected["scope"]}


def demo():
    metadata = rs.read_json(rr.ROOT / "zto-mainnet.json")
    contributors = [{"id": name, "weight": str(weight)} for name, weight in
                    zip("abcdef", (1500, 1500, 900, 500, 500, 200))]
    request = {"budget": rs.display_units(25, metadata["decimals"]),
               "contributors": contributors}
    report = scan(request, metadata, 3)
    return {"scan": report, "verification": verify(request, metadata, report)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="offline 25-to-28 atomic ZTO unit window")
    for command in ("scan", "verify"):
        check = sub.add_parser(command)
        check.add_argument("--request", required=True)
        check.add_argument("--metadata", default=str(rr.ROOT / "zto-mainnet.json"))
        check.add_argument("--output", help="new workspace JSON file; never overwrite")
        if command == "scan":
            check.add_argument("--steps", type=int, required=True)
        else:
            check.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = demo()
        else:
            request = rs.read_json(args.request)
            metadata = rs.read_json(args.metadata)
            if args.command == "scan":
                result = scan(request, metadata, args.steps)
            else:
                result = verify(request, metadata, rs.read_json(args.report))
        rs.write_json(result, getattr(args, "output", None))
    except (rs.Invalid, OSError, ValueError, OverflowError) as exc:
        message = str(exc) if isinstance(exc, rs.Invalid) else type(exc).__name__
        print("rewardwindow: " + message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
