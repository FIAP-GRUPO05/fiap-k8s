"""Check fixed public project endpoints and ingest aggregate uptime events."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request

import boto3

_credentials = None


def check(item):
    environment, base = item
    if environment not in {"develop", "homol", "prod"} or not re.fullmatch(
            r"https://[a-z0-9]+\.execute-api\.sa-east-1\.amazonaws\.com", base):
        raise ValueError("Only fixed project API Gateway endpoints are accepted")
    started = time.monotonic()
    status, healthy, failure = 0, 0, ""
    try:
        for path in ("/actuator/health", "/.well-known/jwks.json"):
            request = urllib.request.Request(base + path, headers={"User-Agent": "FIAP-Uptime/1.0"})
            with urllib.request.urlopen(request, timeout=12) as response:
                status = response.status
                data = json.load(response)
            if path.endswith("health") and data.get("status") != "UP":
                raise ValueError("Application health is not UP")
            if path.endswith("jwks.json") and not data.get("keys"):
                raise ValueError("JWKS is empty")
        healthy = 1
    except urllib.error.HTTPError as error:
        status, failure = error.code, "HTTPError"
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
        failure = type(error).__name__
    return {"eventType": "FiapUptimeCheck", "environment": environment,
            "appName": f"fiap-api-{environment}", "healthy": healthy,
            "responseTimeMs": round((time.monotonic() - started) * 1000, 2),
            "httpStatus": status, "failureClass": failure}


def lambda_handler(event, context):
    global _credentials
    if _credentials is None:
        _credentials = json.loads(boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["NEW_RELIC_SECRET_ARN"])["SecretString"])
    endpoints = json.loads(os.environ["API_ENDPOINTS"])
    if set(endpoints) != {"develop", "homol", "prod"}:
        raise ValueError("Three environment endpoints are required")
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(check, endpoints.items()))
    host = "insights-collector.eu01.nr-data.net" if _credentials.get("region") == "EU" else "insights-collector.newrelic.com"
    account = int(_credentials["account_id"])
    request = urllib.request.Request(f"https://{host}/v1/accounts/{account}/events",
        data=gzip.compress(json.dumps(results).encode()), method="POST",
        headers={"Api-Key": _credentials["license_key"], "Content-Type": "application/json", "Content-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            accepted = json.load(response).get("success") is True
        if not accepted:
            raise ValueError("Event ingestion was rejected")
    except (urllib.error.URLError, ValueError, TimeoutError):
        raise RuntimeError("New Relic uptime ingestion failed") from None
    summary = {result["environment"]: {"healthy": result["healthy"], "httpStatus": result["httpStatus"]}
               for result in results}
    print(json.dumps({"uptime": summary}))
    return {"ingested": len(results), "environments": summary}
