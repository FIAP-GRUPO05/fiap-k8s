"""Return aggregate telemetry health; never expose New Relic credentials."""
import json
import os
import urllib.error
import urllib.request

import boto3

_credentials = None


def count(query):
    global _credentials
    if _credentials is None:
        _credentials = json.loads(boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["NEW_RELIC_SECRET_ARN"])["SecretString"])
    account = int(_credentials["account_id"])
    endpoint = "https://api.eu.newrelic.com/graphql" if _credentials.get("region", "US") == "EU" else "https://api.newrelic.com/graphql"
    graph = "{ actor { account(id: %d) { nrql(query: %s) { results } } } }" % (account, json.dumps(query))
    request = urllib.request.Request(endpoint, data=json.dumps({"query": graph}).encode(),
        headers={"API-Key": _credentials["api_key"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError):
        raise RuntimeError("New Relic API request failed; verify credentials and service availability") from None
    if result.get("errors"):
        raise RuntimeError("New Relic rejected the telemetry query")
    account_data = result.get("data", {}).get("actor", {}).get("account")
    if not account_data:
        raise RuntimeError("New Relic account is unavailable to this API key")
    return int(account_data["nrql"]["results"][0]["samples"])


def lambda_handler(event, context):
    environment = event.get("environment", "develop")
    if environment not in {"develop", "homol", "prod"}:
        raise ValueError("Invalid environment")
    cluster = count("SELECT count(*) AS samples FROM K8sNodeSample WHERE clusterName = 'fiap-shared' SINCE 15 minutes ago")
    require_apm = event.get("require_apm") is True
    application = count(f"SELECT count(*) AS samples FROM Transaction WHERE appName = 'fiap-api-{environment}' SINCE 15 minutes ago") if require_apm else 0
    require_business = event.get("require_business") is True
    business = count(f"SELECT count(*) AS samples FROM ServiceOrderStatusChanged WHERE appName = 'fiap-api-{environment}' SINCE 15 minutes ago") if require_business else 0
    logs = count(f"SELECT count(*) AS samples FROM Log WHERE namespace_name = '{environment}' AND correlationId IS NOT NULL SINCE 15 minutes ago") if require_business else 0
    return {"healthy": cluster > 0 and (application > 0 or not require_apm) and (business > 0 and logs > 0 or not require_business),
            "environment": environment, "cluster_samples": cluster, "application_samples": application,
            "business_samples": business, "correlated_logs": logs}
