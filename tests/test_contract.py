import json
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

class UserError(Exception):
    pass

sdk = types.ModuleType("genlayer")
sdk.TreeMap = dict
sdk.u256 = int
sdk.gl = types.SimpleNamespace(
    Contract=object, vm=types.SimpleNamespace(UserError=UserError),
    message=types.SimpleNamespace(sender_address="lab"),
    public=types.SimpleNamespace(view=lambda fn: fn, write=lambda fn: fn),
    eq_principle=types.SimpleNamespace(strict_eq=lambda fn: fn()),
    nondet=types.SimpleNamespace(web=types.SimpleNamespace()),
)
with patch.dict(sys.modules, {"genlayer": sdk}):
    contract = runpy.run_path(str(Path(__file__).resolve().parents[1] / "contracts/contract.py"))


class GridTests(unittest.TestCase):
    def setUp(self):
        self.grid = contract["CarbonLatch"]("2024-01-01T00:30Z", 64, 70)
        self.grid.journal = {}

    def upstream(self, values):
        rows = []
        for index, value in enumerate(values):
            if value is not None:
                start = contract["minute"]("2024-01-01T00:30Z") + contract["timedelta"](minutes=30 * index)
                end = start + contract["timedelta"](minutes=30)
                rows.append({"from": contract["stamp"](start), "to": contract["stamp"](end),
                             "intensity": {"actual": value, "forecast": 45}})
        sdk.gl.nondet.web.get = lambda url: types.SimpleNamespace(
            status=200, body=json.dumps({"data": rows[::-1]}).encode(),
        )

    def test_hysteresis_and_replay(self):
        self.upstream([64, 68, 70, 67])
        self.assertEqual(self.grid.advance("2024-01-01T00:30Z", 4), "2024-01-01T02:30Z")
        self.assertEqual([json.loads(v)["mode"] for v in self.grid.journal.values()],
                         ["ALLOW", "ALLOW", "HOLD", "HOLD"])
        with self.assertRaisesRegex(UserError, "Stale cursor"):
            self.grid.advance("2024-01-01T00:30Z", 4)
        self.assertEqual(len(self.grid.journal), 4)

    def test_gap_and_boolean_leave_the_entire_batch_unwritten(self):
        for unavailable in (None, True):
            self.upstream([60, unavailable])
            with self.assertRaisesRegex(UserError, "Missing or invalid"):
                self.grid.advance("2024-01-01T00:30Z", 2)
            self.assertEqual(self.grid.journal, {})
            self.assertEqual(json.loads(self.grid.state())["cursor"], "2024-01-01T00:30Z")
