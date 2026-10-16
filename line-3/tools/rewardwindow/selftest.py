#!/usr/bin/env python3
"""Offline checks for exhaustive consecutive-unit reward windows."""

import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

import rewardwindow as rw


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = rw.rs.read_json(rw.rr.ROOT / "zto-mainnet.json")

    def test_paradox_and_verification(self):
        result = rw.demo()
        report = result["scan"]
        self.assertEqual(report["start_budget_units"], "25")
        self.assertEqual(report["end_budget_units"], "28")
        self.assertEqual(report["reversals"][0]["at_budget_units"], "26")
        self.assertEqual([r["id"] for r in report["reversals"][0]["contributors_losing"]], ["d", "e"])
        self.assertEqual(result["verification"]["result"], "verified every atomic-unit transition in window")

    def test_limits(self):
        request = rw.rs.read_json(rw.rr.ROOT / "example.json")
        for steps in (0, -1, 129, True, "2", 2.0, None):
            with self.subTest(steps=steps), self.assertRaises(rw.rs.Invalid):
                rw.scan(request, self.metadata, steps)
        request["budget"] = rw.rs.display_units(rw.rs.UINT256_MAX, 18)
        with self.assertRaisesRegex(rw.rs.Invalid, "uint256"):
            rw.scan(request, self.metadata, 1)

    def test_tampering_rejected(self):
        request = rw.rs.read_json(rw.rr.ROOT / "example.json")
        report = rw.scan(request, self.metadata, 2)
        for mutate in (
            lambda item: item["reversals"].append({}),
            lambda item: item.update(extra=True),
            lambda item: item.update(end_budget_units="0"),
        ):
            changed = copy.deepcopy(report)
            mutate(changed)
            with self.assertRaises(rw.rs.Invalid):
                rw.verify(request, self.metadata, changed)
        changed_request = copy.deepcopy(request)
        changed_request["contributors"][0]["weight"] = "2"
        with self.assertRaises(rw.rs.Invalid):
            rw.verify(changed_request, self.metadata, report)

    def test_seeded_consecutive_conservation(self):
        rng = random.Random(25)
        for _ in range(40):
            count = rng.randrange(2, 15)
            start = rng.randrange(1, 60)
            request = {"budget": rw.rs.display_units(start, 18),
                       "contributors": [{"id": "role%02d" % i, "weight": str(rng.randrange(1, 300))}
                                        for i in range(count)]}
            report = rw.scan(request, self.metadata, 8)
            self.assertEqual(report["end_budget_units"], str(start + 8))
            self.assertEqual(rw.verify(request, self.metadata, report)["scan_sha256"], rw.rr.digest(report))
            for offset in range(9):
                candidate = dict(request, budget=rw.rs.display_units(start + offset, 18))
                allocation = rw.rs.allocate(candidate, self.metadata)
                self.assertEqual(sum(int(row["units"]) for row in allocation["allocations"]), start + offset)

    def test_cli_roundtrip(self):
        scratch = Path.cwd() / "test" / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp)
            request = {"budget": rw.rs.display_units(25, 18), "contributors": [
                {"id": name, "weight": str(weight)} for name, weight in
                zip("abcdef", (1500, 1500, 900, 500, 500, 200))]}
            (root / "request.json").write_text(json.dumps(request))
            script = str(Path(rw.__file__))
            command = [sys.executable, "-B", script, "scan", "--request", str(root / "request.json"),
                       "--steps", "3", "--output", str(root / "window.json")]
            run = lambda args: subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(run(command).returncode, 0)
            self.assertEqual(run(command).returncode, 2)
            check = [sys.executable, "-B", script, "verify", "--request", str(root / "request.json"),
                     "--report", str(root / "window.json")]
            self.assertEqual(run(check).returncode, 0)
            (root / "window.json").write_text('{"steps_checked":3,"steps_checked":2}')
            self.assertEqual(run(check).returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
