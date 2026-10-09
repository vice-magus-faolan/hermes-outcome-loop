# SPDX-License-Identifier: GPL-3.0-or-later
"""Prevent canonical verification from silently losing production acceptance coverage."""
import json
from pathlib import Path
import unittest

from scripts.verify import require_production_gates, test_ids

ROOT = Path(__file__).resolve().parents[1]


class VerificationTests(unittest.TestCase):
    def test_production_map_matches_discovery_and_fails_when_a_gate_disappears(self):
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        discovered = test_ids(suite)
        require_production_gates(discovered)
        mapping = json.loads((ROOT / "tests/fixtures/outcome/production-map.json").read_text())
        for required in mapping.values():
            for identifier in required:
                with self.subTest(identifier=identifier), self.assertRaisesRegex(RuntimeError, "missing production acceptance tests"):
                    require_production_gates(discovered - {identifier})


if __name__ == "__main__":
    unittest.main()
