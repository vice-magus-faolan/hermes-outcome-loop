# SPDX-License-Identifier: GPL-3.0-or-later
"""Bootstrap-document regression checks, not outcome-plugin acceptance tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    """Keep source handoff, authority constraints and bootstrap status explicit."""

    def test_source_handoff_retains_core_invariants(self):
        text = (ROOT / "docs/project-handoff.md").read_text(encoding="utf-8")
        for phrase in ("Hermes Kanban remains the sole execution authority",
                       "No direct Kanban database writes",
                       "No hidden second truth"):
            self.assertIn(phrase, text)

    def test_reviewed_constraints_cover_known_design_gaps(self):
        text = (ROOT / "docs/mvp-constraints.md").read_text(encoding="utf-8")
        for phrase in ("not a sandbox", "commented", "native comment IDs",
                       "retry key/ID", "due time unknown", "read back"):
            self.assertIn(phrase.casefold(), text.casefold())

    def test_roadmap_retains_feasibility_and_pilot_gates(self):
        text = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
        self.assertIn("Phase 0", text)
        self.assertIn("Approval-gated", text)
        self.assertIn("canonical verifier", text)

    def test_license_is_explicitly_or_later(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("GPL-3.0-or-later", readme)
        self.assertIn("GNU GENERAL PUBLIC LICENSE",
                      (ROOT / "LICENSE").read_text(encoding="utf-8"))
