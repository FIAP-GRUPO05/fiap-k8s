import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

with patch.dict("sys.modules", {"boto3": MagicMock()}):
    spec = importlib.util.spec_from_file_location("telemetry_probe", Path(__file__).resolve().parents[2] / "infra/platform/scripts/verify_observability.py")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)


class NotificationTelemetryTests(unittest.TestCase):
    def test_notifications_require_correlated_success_and_no_failure(self):
        def result(query):
            return 0 if "level = 'ERROR'" in query else 1
        with patch.object(probe, "count", side_effect=result) as count:
            health = probe.lambda_handler({"environment": "prod", "require_notifications": True, "correlation_id": "regression-123"}, None)
        self.assertTrue(health["healthy"])
        self.assertTrue(any("regression-123" in call.args[0] for call in count.call_args_list))
        with patch.object(probe, "count", return_value=1):
            self.assertFalse(probe.lambda_handler({"require_notifications": True, "correlation_id": "regression-123"}, None)["healthy"])

    def test_missing_success_is_not_healthy(self):
        with patch.object(probe, "count", side_effect=[1, 0, 0]):
            self.assertFalse(probe.lambda_handler({"require_notifications": True, "correlation_id": "regression-123"}, None)["healthy"])

    def test_correlation_cannot_inject_an_nrql_filter(self):
        with patch.object(probe, "count", return_value=1), self.assertRaises(ValueError):
            probe.lambda_handler({"require_notifications": True, "correlation_id": "x' OR true"}, None)
