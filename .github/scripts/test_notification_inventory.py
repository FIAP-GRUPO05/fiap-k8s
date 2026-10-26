import unittest
import aws_destroy as cloud


class NotificationInventoryTests(unittest.TestCase):
    def inventory(self, deny=False):
        class Fake:
            def identity(self): return {"Account": cloud.ACCOUNT}
            def run(self, service, operation, *args, **kwargs):
                if (service, operation) == ("lambda", "list-functions"):
                    return [{"Name": "fiap-email-prod"}, {"Name": "other-email-function"}]
                if (service, operation) == ("sesv2", "list-email-identities"):
                    return ["team@example.test", "unrelated@example.test"]
                if (service, operation) == ("sesv2", "get-email-identity"):
                    if deny: raise RuntimeError("AccessDenied")
                    return {"Tags": [{"Key": "Project", "Value": cloud.PROJECT if args[-1] == "team@example.test" else "other"}]}
                if (service, operation) == ("ec2", "describe-regions"): return [cloud.REGION]
                if (service, operation) == ("resourcegroupstaggingapi", "get-resources"):
                    return [f"arn:aws:ses:{cloud.REGION}:{cloud.ACCOUNT}:identity/team@example.test"]
                return []
        return cloud.inventory(Fake())

    def test_notification_lambda_is_removable_and_identity_is_explicitly_retained(self):
        report = self.inventory()
        self.assertEqual(report["errors"], [])
        self.assertEqual([r["id"] for r in report["resources"] if r["kind"] == "lambda"], ["fiap-email-prod"])
        self.assertEqual([r["id"] for r in report["free_resources"] if r["kind"] == "ses-identity"], ["team@example.test"])

    def test_failed_identity_lookup_never_proves_retention_is_safe(self):
        report = self.inventory(deny=True)
        self.assertTrue(report["errors"])
        self.assertFalse(any(r["kind"] == "ses-identity" for r in report["free_resources"]))
