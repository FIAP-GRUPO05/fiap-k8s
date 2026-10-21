"""Authorization, teardown and reporting regressions. No real AWS/GitHub calls."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aws_destroy as cloud
import destroy_ops as ops
from destroy_report import render


def request():
    snapshot = {"release": "release/v0.2.0", "refs": {name: "a" * 40 for name in ("develop", "release/v0.2.0", "prod", "main")}}
    return {"schema": 1, "request_id": "2f38efaf-b919-45d3-b1a7-51ef038265e7", "requested_by": "codewesleylima",
            "account": "456687462806", "region": "sa-east-1", "confirmation": "DESTRUIR-456687462806",
            "delete_project_data": True, "implementation_sha": "b" * 40, "billing_start": "2026-10-01",
            "repositories": {name: copy.deepcopy(snapshot) for name in ops.REPOS}}


def review(name, state="APPROVED", sha="c" * 40):
    return {"user": {"login": name}, "state": state, "commit_id": sha}


class ApprovalTests(unittest.TestCase):
    def test_both_other_members_are_required(self):
        self.assertEqual(ops.approvals({"head": {"sha": "c" * 40}}, request(), [review("timbeck97"), review("matpitas")]), ["matpitas", "timbeck97"])

    def test_requester_and_one_member_are_insufficient(self):
        with self.assertRaises(ValueError):
            ops.approvals({"head": {"sha": "c" * 40}}, request(), [review("codewesleylima"), review("timbeck97")])

    def test_stale_approval_is_rejected(self):
        with self.assertRaises(ValueError):
            ops.approvals({"head": {"sha": "c" * 40}}, request(), [review("timbeck97", sha="d" * 40), review("matpitas")])

    def test_changes_requested_revokes_previous_approval(self):
        with self.assertRaises(ValueError):
            ops.approvals({"head": {"sha": "c" * 40}}, request(), [review("timbeck97"), review("matpitas"), review("timbeck97", "CHANGES_REQUESTED")])

    def test_comments_do_not_revoke_approval(self):
        self.assertEqual(len(ops.approvals({"head": {"sha": "c" * 40}}, request(), [review("timbeck97"), review("matpitas"), review("timbeck97", "COMMENTED")])), 2)

    def test_dismissed_approval_is_rejected(self):
        with self.assertRaises(ValueError):
            ops.approvals({"head": {"sha": "c" * 40}}, request(), [review("timbeck97"), review("matpitas"), review("matpitas", "DISMISSED")])

    def test_valid_snapshot(self):
        ops.validate_request(request())

    def test_wrong_account_is_rejected(self):
        document = request()
        document["account"] = "000000000000"
        with self.assertRaises(ValueError):
            ops.validate_request(document)

    def test_data_deletion_must_be_acknowledged(self):
        document = request()
        document["delete_project_data"] = False
        with self.assertRaises(ValueError):
            ops.validate_request(document)

    def test_unexpected_branch_in_snapshot_is_rejected(self):
        document = request()
        document["repositories"]["fiap-k8s"]["refs"]["ALL"] = "d" * 40
        with self.assertRaises(ValueError):
            ops.validate_request(document)


class AwsSafetyTests(unittest.TestCase):
    def test_same_name_in_another_service_is_not_covered(self):
        report = {"resources": [{"kind": "ecr", "id": "fiap-application"}], "free_resources": []}
        self.assertTrue(cloud.covered_identifier("ecr", {"fiap-application"}, report))
        self.assertFalse(cloud.covered_identifier("codebuild", {"fiap-application"}, report))
        self.assertFalse(cloud.covered_identifier("sns", {"fiap-application"}, report))

    def test_vpc_children_are_only_ec2_resources(self):
        report = {"resources": [{"kind": "vpc", "id": "vpc-project", "children": ["sg-one"]}], "free_resources": []}
        self.assertTrue(cloud.covered_identifier("ec2", {"sg-one"}, report))
        self.assertFalse(cloud.covered_identifier("rds", {"sg-one"}, report))

    def test_default_client_cannot_delete(self):
        with patch("subprocess.run") as process, self.assertRaises(PermissionError):
            cloud.Aws().change("s3api", "delete-bucket", "--bucket", cloud.BUCKET)
        process.assert_not_called()

    def test_feature_event_cannot_delete(self):
        with patch.dict(os.environ, {"GITHUB_REF_NAME": ops.SOURCE, "GITHUB_EVENT_NAME": "push", "FIAP_APPROVED_DESTROY_REQUEST": "request"}), patch("subprocess.run") as process:
            with self.assertRaises(PermissionError):
                cloud.Aws(destructive=True).change("s3api", "delete-bucket", "--bucket", cloud.BUCKET)
            process.assert_not_called()

    def test_missing_approval_context_cannot_delete(self):
        with patch.dict(os.environ, {"GITHUB_REF_NAME": "ALL", "GITHUB_EVENT_NAME": "push", "FIAP_APPROVED_DESTROY_REQUEST": ""}), patch("subprocess.run") as process:
            with self.assertRaises(PermissionError):
                cloud.Aws(destructive=True).change("s3api", "delete-bucket", "--bucket", cloud.BUCKET)
            process.assert_not_called()

    def test_unknown_account_stops_inventory(self):
        fake = cloud.Aws()
        with patch.object(fake, "run", return_value={"Account": "000000000000"}), self.assertRaises(PermissionError):
            cloud.inventory(fake)

    def test_new_vpc_child_changes_the_approved_inventory(self):
        before = {"resources": [{"kind": "vpc", "id": "vpc-project", "children": ["sg-one"]}]}
        after = {"resources": [{"kind": "vpc", "id": "vpc-project", "children": ["sg-one", "sg-two"]}]}
        self.assertEqual(cloud.resource_keys(after) - cloud.resource_keys(before), {("vpc-child", "sg-two")})

    def test_s3_partial_delete_stops_before_bucket_deletion(self):
        class Fake:
            calls = []
            def run(self, *args, **kwargs):
                return {"Versions": [{"Key": "state", "VersionId": "v1"}]}
            def change(self, *args, **kwargs):
                self.calls.append(args)
                return {"Errors": [{"Code": "AccessDenied"}]}
        fake = Fake()
        with self.assertRaises(RuntimeError):
            cloud.purge_bucket(fake, cloud.BUCKET)
        self.assertFalse(any(call[1] == "delete-bucket" for call in fake.calls))

    def test_unavailable_cost_is_not_zero(self):
        fake = cloud.Aws()
        with patch.object(fake, "run", side_effect=RuntimeError("User not enabled for cost explorer access")):
            result = cloud.cost_report("2026-10-01", fake)
        self.assertFalse(result["available"])
        self.assertNotIn("total", result)

    def test_credits_do_not_hide_consumption(self):
        fake = cloud.Aws()
        usage = {"ResultsByTime": [{"TimePeriod": {"Start": "2026-10-19"}, "Estimated": True,
                  "Groups": [{"Keys": ["Amazon RDS", "Usage"], "Metrics": {"UnblendedCost": {"Amount": "12.3456789012", "Unit": "USD"}}},
                             {"Keys": ["Amazon RDS", "Credit"], "Metrics": {"UnblendedCost": {"Amount": "-12.3456789012", "Unit": "USD"}}}]}]}
        with patch.object(fake, "run", return_value=usage):
            result = cloud.cost_report("2026-10-01", fake)
        self.assertEqual(result["consumption"], "12.3456789012")
        self.assertEqual(result["credits"], "-12.3456789012")
        self.assertEqual(result["total"], "0E-10")


class SynchronizationTests(unittest.TestCase):
    def test_concurrent_update_aborts_without_writing(self):
        with patch.object(ops, "REPOS", ("fiap-k8s",)), patch.object(ops, "ref", return_value="d" * 40), patch.object(ops, "api") as api:
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                ops.synchronize(request(), "e" * 40, [], Path(directory))
            api.assert_not_called()

    def test_sync_prepares_normal_merge_commits_without_force_push(self):
        refs = dict(request()["repositories"]["fiap-k8s"]["refs"])
        calls = []
        def api(method, path, body=None):
            calls.append((method, path, body))
            if method == "POST" and path.endswith("/git/refs"):
                refs[body["ref"].removeprefix("refs/heads/")] = body["sha"]
            elif method == "POST" and path.endswith("/merges"):
                refs[body["base"]] = "d" * 40
            elif method == "PATCH":
                import urllib.parse
                branch = urllib.parse.unquote(path.split("/git/refs/heads/", 1)[1])
                self.assertIs(body["force"], False)
                refs[branch] = body["sha"]
        log = []
        with patch.object(ops, "REPOS", ("fiap-k8s",)), patch.object(ops, "ref", side_effect=lambda repo, branch: refs[branch]), patch.object(ops, "api", side_effect=api):
            with tempfile.TemporaryDirectory() as directory:
                ops.synchronize(request(), "e" * 40, log, Path(directory))
        self.assertEqual([row["branch"] for row in log], ["develop", "release/v0.2.0", "prod", "main"])
        self.assertEqual(sum(method == "PATCH" for method, _, _ in calls), 4)


class ReportTests(unittest.TestCase):
    def test_missing_execution_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            render(Path(directory))
            text = (Path(directory) / "report.md").read_text(encoding="utf-8")
            self.assertIn("custo", text.lower())
            self.assertNotIn("✅", text)

    def test_audit_error_prevents_green_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "execution.json").write_text(json.dumps({"before": {"resources": [{"kind": "rds", "id": "project"}]},
                "after": {"resources": [], "errors": ["AccessDenied"]}, "costs": {"available": False}}))
            render(path)
            self.assertNotIn("✅", (path / "report.md").read_text(encoding="utf-8"))

    def test_removed_and_remaining_resources_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "execution.json").write_text(json.dumps({"before": {"resources": [{"kind": "rds", "id": "removed"}, {"kind": "ecr", "id": "remaining"}]},
                "after": {"resources": [{"kind": "ecr", "id": "remaining"}], "errors": []}, "costs": {"available": False}}))
            render(path)
            text = (path / "report.md").read_text(encoding="utf-8")
            self.assertIn("| ✅ | `rds: removed`", text)
            self.assertIn("| ❌ | `ecr: remaining`", text)


if __name__ == "__main__":
    unittest.main()
