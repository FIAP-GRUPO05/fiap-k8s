"""Read NerdGraph metadata and map existing FIAP resources to Terraform imports."""
import json
import urllib.error
import urllib.request


def unique(items, name):
    matches = [item for item in items if item["name"] == name]
    if len(matches) > 1:
        raise RuntimeError("Ambiguous New Relic resource; reconcile duplicate names before applying: " + name)
    return matches[0] if matches else None


def imports(account, query):
    result = {}
    for environment in ("develop", "homol", "prod"):
        name = f"FIAP API ({environment})"
        scope = f'module.environment["{environment}"]'
        search = f"type = 'DASHBOARD' AND accountId = '{account}' AND name = '{name}'"
        dashboards = query("{ actor { entitySearch(query: " + json.dumps(search) + ") { results { entities { guid name } } } } }")["actor"]["entitySearch"]["results"]["entities"]
        if dashboard := unique(dashboards, name):
            result[scope + ".newrelic_one_dashboard.fiap_api"] = dashboard["guid"]
        policy_data = query('{ actor { account(id: %d) { alerts { policiesSearch(searchCriteria: {name: %s}) { nextCursor policies { id name } } } } } }' % (account, json.dumps(name)))["actor"]["account"]["alerts"]["policiesSearch"]
        if policy_data.get("nextCursor"):
            raise RuntimeError("Ambiguous policy search; refuse incomplete inventory")
        policy = unique(policy_data["policies"], name)
        if not policy:
            continue
        policy_id = str(policy["id"])
        result[scope + ".newrelic_alert_policy.fiap_api"] = policy_id
        conditions, cursor, seen = [], None, set()
        while True:
            arguments = "searchCriteria: {policyId: " + json.dumps(policy_id) + "}"
            if cursor:
                arguments += ", cursor: " + json.dumps(cursor)
            page = query("{ actor { account(id: %d) { alerts { nrqlConditionsSearch(%s) { nextCursor nrqlConditions { id name type } } } } } }" % (account, arguments))["actor"]["account"]["alerts"]["nrqlConditionsSearch"]
            conditions.extend(page["nrqlConditions"])
            cursor = page.get("nextCursor")
            if not cursor:
                break
            if cursor in seen:
                raise RuntimeError("Repeated New Relic pagination cursor")
            seen.add(cursor)
        names = {"service_order_failures": f"Falhas no processamento de ordens de servi\u00e7o ({environment})",
                 "https_uptime": f"Disponibilidade HTTPS ({environment})",
                 "notification_failures": f"Falhas de notificacao ({environment})"}
        for resource, condition_name in names.items():
            if condition := unique(conditions, condition_name):
                if condition["type"].upper() != "STATIC":
                    raise RuntimeError("Unexpected condition type for " + condition_name)
                result[scope + ".newrelic_nrql_alert_condition." + resource] = policy_id + ":" + str(condition["id"]) + ":static"
    return result


def client(credentials):
    host = "api.eu.newrelic.com" if credentials.get("region", "US") == "EU" else "api.newrelic.com"
    def query(graph):
        request = urllib.request.Request("https://" + host + "/graphql", data=json.dumps({"query": graph}).encode(),
                    headers={"API-Key": credentials["api_key"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except (urllib.error.URLError, ValueError):
            raise RuntimeError("New Relic metadata query failed; verify access without logging credentials") from None
        if result.get("errors") or not result.get("data"):
            raise RuntimeError("New Relic rejected the metadata query")
        return result["data"]
    return query
