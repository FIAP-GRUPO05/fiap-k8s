import unittest
import aws_destroy as cloud


class UnaliasedPendingKeyTests(unittest.TestCase):
    arn = f"arn:aws:kms:{cloud.REGION}:{cloud.ACCOUNT}:key/old-project-key"

    def inventory(self, state="PendingDeletion", denied=False):
        class Fake:
            def identity(self): return {"Account": cloud.ACCOUNT}
            def run(self, service, operation, *args, **kwargs):
                if (service, operation) == ("ec2", "describe-regions"): return [cloud.REGION]
                if (service, operation) == ("resourcegroupstaggingapi", "get-resources"): return [UnaliasedPendingKeyTests.arn]
                if (service, operation) == ("kms", "describe-key"):
                    if denied: raise RuntimeError("AccessDenied")
                    return {"KeyId": "old-project-key", "KeyState": state}
                return []
        return cloud.inventory(Fake())

    def test_pending_old_key_remains_explicit_after_alias_moves_to_new_cluster_key(self):
        report = self.inventory()
        self.assertEqual(report["errors"], [])
        self.assertTrue(any(item["id"] == "old-project-key" and item["state"] == "PendingDeletion" for item in report["free_resources"]))

    def test_unknown_active_key_is_not_declared_free(self):
        report = self.inventory(state="Enabled")
        self.assertTrue(report["errors"])
        self.assertEqual(report["free_resources"], [])

    def test_permission_failure_does_not_prove_pending_deletion(self):
        report = self.inventory(denied=True)
        self.assertTrue(report["errors"])
        self.assertEqual(report["free_resources"], [])
