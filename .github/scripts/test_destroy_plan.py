"""Regressions for immutable reviewed plans. No real AWS or GitHub calls."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aws_destroy as cloud
import destroy_ops as ops


class ReviewedPlanTests(unittest.TestCase):
    def plan(self, current, *, available=True):
        original = {"head_sha": "a" * 40, "request": {"billing_start": "2026-10-01"},
                    "inventory": {"resources": [{"kind": "vpc", "id": "vpc-project", "children": ["sg-existing"]}],
                                  "free_resources": [], "errors": []},
                    "costs": {"available": True, "consumption": "1.00"}}
        pr = {"head": {"sha": original["head_sha"]}}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "pull_request_review"}), \
                 patch.object(ops, "validate_pr", return_value=(pr, original["request"])), \
                 patch.object(ops, "snapshot_valid"), patch.object(ops, "installation_ready"), \
                 patch.object(ops, "api", return_value={"artifacts": [{"expired": False}] if available else []}), \
                 patch.object(ops, "approved_plan", return_value=copy.deepcopy(original)) as recovered, \
                 patch.object(cloud, "inventory", return_value=current) as inventory, \
                 patch.object(cloud, "cost_report") as costs:
                try:
                    ops.plan(28, target)
                finally:
                    # A review must not replace the original billing capture.
                    costs.assert_not_called()
                    if not available:
                        inventory.assert_not_called()
                        recovered.assert_not_called()
                return json.loads((target / "plan.json").read_text(encoding="utf-8")), original

    def test_review_reuses_original_plan_when_inventory_is_unchanged(self):
        current = {"resources": [{"kind": "vpc", "id": "vpc-project", "children": ["sg-existing"]}], "errors": []}
        written, original = self.plan(current)
        self.assertEqual(written, original)

    def test_review_rejects_a_new_resource_after_the_original_plan(self):
        current = {"resources": [{"kind": "vpc", "id": "vpc-project", "children": ["sg-existing"]},
                                 {"kind": "secret", "id": "new-secret"}], "errors": []}
        with self.assertRaisesRegex(ValueError, "Inventory expanded"):
            self.plan(current)

    def test_review_rejects_a_new_child_in_an_existing_vpc(self):
        current = {"resources": [{"kind": "vpc", "id": "vpc-project", "children": ["sg-existing", "sg-new"]}],
                   "errors": []}
        with self.assertRaisesRegex(ValueError, "Inventory expanded"):
            self.plan(current)

    def test_review_requires_an_original_plan_artifact(self):
        with self.assertRaisesRegex(ValueError, "original plan must exist"):
            self.plan({"resources": [], "errors": []}, available=False)


if __name__ == "__main__":
    unittest.main()
