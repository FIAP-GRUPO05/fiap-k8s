"""Authoritative checks for deleted security group rules still present in tags."""
import subprocess
import unittest
from unittest.mock import patch

import aws_destroy as cloud


class DeletedRuleAuditTests(unittest.TestCase):
    rule_id = "sgr-00000000000000001"
    arn = f"arn:aws:ec2:sa-east-1:{cloud.ACCOUNT}:security-group-rule/{rule_id}"

    def inventory(self, response=None, error=None):
        calls = []

        class Fake:
            def identity(self):
                return {"Account": cloud.ACCOUNT}

            def run(self, service, operation, *arguments, **kwargs):
                calls.append((service, operation, arguments, kwargs))
                if (service, operation) == ("ec2", "describe-regions"):
                    return [cloud.REGION]
                if (service, operation) == ("resourcegroupstaggingapi", "get-resources"):
                    return [DeletedRuleAuditTests.arn]
                if (service, operation) == ("ec2", "describe-security-group-rules"):
                    if error:
                        raise RuntimeError(error)
                    return response
                return []

        return cloud.inventory(Fake()), calls

    def test_missing_rule_is_verified_before_stale_tag_is_accepted(self):
        for response in (None, []):
            with self.subTest(response=response):
                report, calls = self.inventory(response)
                self.assertEqual(report["errors"], [])
                self.assertEqual(report["resources"], [])
                self.assertTrue(any(item["kind"] == "verified-absent-security-group-rule"
                                    and item["id"] == self.rule_id and item["state"] == "Absent"
                                    for item in report["free_resources"]))
                self.assertTrue(any(service == "ec2" and operation == "describe-security-group-rules"
                                    and arguments == ("--security-group-rule-ids", self.rule_id)
                                    and options.get("missing") is True
                                    for service, operation, arguments, options in calls))

    def test_live_rule_outside_the_inventory_remains_blocked(self):
        report, _ = self.inventory([{"SecurityGroupRuleId": self.rule_id, "GroupId": "sg-unverified"}])
        self.assertIn("Tagged resource not covered by the teardown engine: " + self.arn, report["errors"])
        self.assertFalse(any(item["kind"] == "verified-absent-security-group-rule" for item in report["free_resources"]))

    def test_permission_error_never_proves_absence(self):
        report, _ = self.inventory(error="AccessDenied")
        self.assertTrue(any("AccessDenied" in error for error in report["errors"]))
        self.assertFalse(any(item["kind"] == "verified-absent-security-group-rule" for item in report["free_resources"]))

    def test_rule_not_found_is_the_specific_allowed_missing_response(self):
        response = subprocess.CompletedProcess([], 255, "", "An error occurred (InvalidSecurityGroupRuleId.NotFound): missing")
        with patch("subprocess.run", return_value=response):
            self.assertIsNone(cloud.Aws().run("ec2", "describe-security-group-rules",
                                             "--security-group-rule-ids", self.rule_id, missing=True))

    def test_other_rule_errors_are_not_converted_to_absence(self):
        for code in ("AccessDenied", "InvalidSecurityGroupRuleId.Malformed"):
            with self.subTest(code=code), patch("subprocess.run", return_value=subprocess.CompletedProcess([], 255, "", code)):
                with self.assertRaises(RuntimeError):
                    cloud.Aws().run("ec2", "describe-security-group-rules", "--security-group-rule-ids", self.rule_id, missing=True)


if __name__ == "__main__":
    unittest.main()
