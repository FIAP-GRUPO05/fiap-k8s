import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("restore_infra", Path(__file__).resolve().parents[2] / "tools/restore_infra.py")
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class ReconstructionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.task = restore.Restore(Path.cwd().parent, "test-profile")

    def test_default_refuses_mutations_before_starting_process(self):
        with patch.object(restore.subprocess, "run") as run, self.assertRaises(PermissionError):
            self.task.run(["aws", "s3api", "create-bucket"], mutation=True)
        run.assert_not_called()

    def test_account_mismatch_is_rejected(self):
        with patch.object(self.task, "aws", return_value={"Account": "000000000000"}), self.assertRaises(PermissionError):
            self.task.identity()

    def test_replacement_and_deletion_are_rejected(self):
        for actions in (["delete"], ["create", "delete"], ["delete", "create"]):
            with self.subTest(actions=actions), self.assertRaises(PermissionError):
                self.task.no_deletions({"resource_changes": [{"address": "aws_db_instance.database", "change": {"actions": actions}}]})
        self.task.no_deletions({"resource_changes": [{"address": "aws_iam_role.application", "change": {"actions": ["update"]}}]})

    def test_unknown_role_reference_waits_for_next_import_pass(self):
        with patch.object(self.task, "aws") as aws:
            result = self.task.import_id({"type": "aws_iam_role_policy", "change": {"after": {"name": "fiap-policy", "role": None}}})
        self.assertIsNone(result)
        aws.assert_not_called()

    def test_only_scoped_roles_are_imported(self):
        with patch.object(self.task, "aws", return_value={"Role": {}}) as aws:
            self.assertIsNone(self.task.import_id({"type": "aws_iam_role", "change": {"after": {"name": "other-project"}}}))
            aws.assert_not_called()
            self.assertEqual(self.task.import_id({"type": "aws_iam_role", "change": {"after": {"name": "fiap-email-prod"}}}), "fiap-email-prod")

    def test_permission_denial_does_not_mean_resource_is_absent(self):
        result = subprocess.CompletedProcess([], 255, "private stdout", "AccessDenied")
        with patch.object(restore.subprocess, "run", return_value=result), self.assertRaises(RuntimeError) as error:
            self.task.run(["aws", "iam", "get-role"], missing=True)
        self.assertNotIn("private stdout", str(error.exception))

    def test_unverified_sender_stops_before_creating_billable_infrastructure(self):
        self.task.sender = "team@example.test"
        with patch.object(self.task, "identity"), patch.object(self.task, "aws", return_value={"VerifiedForSendingStatus": False}) as aws:
            with self.assertRaisesRegex(RuntimeError, "Confirm the SES"):
                self.task.prepare()
        self.assertEqual(aws.call_count, 1)
        self.assertEqual(aws.call_args.args[:2], ("sesv2", "get-email-identity"))

    def test_unexpected_gateway_is_not_synchronized(self):
        config = {env: {"api_url": "https://other.example.test", "issuer": "https://other.example.test"} for env in restore.ENVS}
        with patch.object(self.task, "output", return_value=config), self.assertRaises(ValueError):
            self.task.runtime()

    def test_runtime_preserves_environment_isolation_and_adds_authorized_recipient(self):
        self.task.recipient = "authorized@example.test"
        config = {env: {"api_url": f"https://{env}.execute-api.sa-east-1.amazonaws.com",
                       "issuer": f"https://{env}.execute-api.sa-east-1.amazonaws.com"} for env in restore.ENVS}
        with patch.object(self.task, "output", return_value=config):
            result = self.task.runtime()
        self.assertEqual(result["prod"]["notification_test_email"], self.task.recipient)

    def test_full_reconstruction_requires_explicit_execution(self):
        with patch.object(self.task, "identity"), self.assertRaises(ValueError):
            self.task.stage("all")
