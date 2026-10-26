import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("newrelic_reconcile", Path(__file__).resolve().parents[2] / "tools/newrelic_reconcile.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NewRelicImportTests(unittest.TestCase):
    def query(self, graph):
        if "entitySearch" in graph:
            return {"actor": {"entitySearch": {"results": {"entities": [{"name": "FIAP API (prod)", "guid": "dashboard-guid"}]}}}}
        if "policiesSearch" in graph:
            return {"actor": {"account": {"alerts": {"policiesSearch": {"policies": [{"name": "FIAP API (prod)", "id": "100"}], "nextCursor": None}}}}}
        return {"actor": {"account": {"alerts": {"nrqlConditionsSearch": {"nrqlConditions": [{"name": "Disponibilidade HTTPS (prod)", "id": "200", "type": "STATIC"}, {"name": "Falhas no processamento de ordens de servi\u00e7o (prod)", "id": "201", "type": "STATIC"}], "nextCursor": None}}}}}

    def test_existing_resources_map_to_correct_import_identifiers(self):
        result = module.imports(123, self.query)
        self.assertEqual(result['module.environment["prod"].newrelic_one_dashboard.fiap_api'], "dashboard-guid")
        self.assertEqual(result['module.environment["prod"].newrelic_nrql_alert_condition.https_uptime'], "100:200:static")
        self.assertEqual(result['module.environment["prod"].newrelic_nrql_alert_condition.service_order_failures'], "100:201:static")
        self.assertNotIn('module.environment["prod"].newrelic_nrql_alert_condition.notification_failures', result)

    def test_ambiguous_names_are_never_adopted(self):
        with self.assertRaises(RuntimeError):
            module.unique([{"name": "FIAP"}, {"name": "FIAP"}], "FIAP")

    def test_repeated_pagination_does_not_silently_drop_conditions(self):
        def query(graph):
            result = self.query(graph)
            if "nrqlConditionsSearch" in graph:
                result["actor"]["account"]["alerts"]["nrqlConditionsSearch"]["nextCursor"] = "repeated"
            return result
        with self.assertRaisesRegex(RuntimeError, "Repeated"):
            module.imports(123, query)
