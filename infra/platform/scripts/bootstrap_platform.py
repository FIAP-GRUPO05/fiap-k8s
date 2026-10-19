"""Bootstrap namespaces and the New Relic Kubernetes/Java integration."""
import json
import os
import subprocess
import tempfile
import time
import boto3

def run(*args, document=None):
    subprocess.run(args, input=json.dumps(document) if document is not None else None, text=True, check=True)

def apply(document):
    run("kubectl", "apply", "--server-side", "--field-manager=fiap-platform", "-f", "-", document=document)

for environment in ("develop", "homol", "prod"):
    apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": environment,
        "labels": {"fiap/environment": environment}}})
run("kubectl", "get", "nodes")
run("helm", "upgrade", "--install", "aws-load-balancer-controller", "aws-load-balancer-controller",
    "--repo", "https://aws.github.io/eks-charts", "--version", "3.6.0", "--namespace", "kube-system",
    "--set", "clusterName=fiap-shared", "--set", f"region={os.environ['CLUSTER_REGION']}",
    "--set", f"vpcId={os.environ['CLUSTER_VPC_ID']}",
    "--set", "serviceAccount.name=aws-load-balancer-controller", "--set", "serviceAccount.create=true",
    "--set", "enableShield=false", "--set", "enableWaf=false", "--set", "enableWafv2=false",
    "--wait", "--timeout", "5m")
if os.environ.get("BOOTSTRAP_ONLY", "false").lower() == "true":
    print("Namespaces and ingress controller ready")
    raise SystemExit(0)

credentials = json.loads(boto3.client("secretsmanager").get_secret_value(SecretId="fiap/shared/newrelic")["SecretString"])
values = {
    "global": {"cluster": "fiap-shared", "licenseKey": credentials["license_key"]},
    "newrelic-infrastructure": {"enabled": True},
    "nri-metadata-injection": {"enabled": True},
    "kube-state-metrics": {"enabled": True},
    "nri-kube-events": {"enabled": True},
    "newrelic-logging": {"enabled": True},
    "k8s-agents-operator": {"enabled": True},
}
# Credentials stay in a private temporary file instead of process arguments.
with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as value_file:
    json.dump(values, value_file)
    value_file.flush()
    run("helm", "upgrade", "--install", "newrelic-bundle", "nri-bundle",
        "--repo", "https://helm-charts.newrelic.com", "--version", os.environ["NEW_RELIC_CHART_VERSION"],
        "--namespace", "newrelic", "--create-namespace", "--values", value_file.name,
        "--wait", "--timeout", "10m")

for environment in ("develop", "homol", "prod"):
    apply({"apiVersion": "newrelic.com/v1alpha2", "kind": "Instrumentation",
        "metadata": {"name": f"fiap-java-{environment}", "namespace": "newrelic"},
        "spec": {
            "agent": {"language": "java", "image": os.environ["NEW_RELIC_JAVA_IMAGE"], "env": [
                {"name": "NEW_RELIC_APP_NAME", "value": f"fiap-api-{environment}"},
                {"name": "NEW_RELIC_DISTRIBUTED_TRACING_ENABLED", "value": "true"},
                {"name": "NEW_RELIC_APPLICATION_LOGGING_FORWARDING_ENABLED", "value": "false"}]},
            "podLabelSelector": {"matchExpressions": [{"key": "app", "operator": "In", "values": ["api"]}]},
            "namespaceLabelSelector": {"matchLabels": {"kubernetes.io/metadata.name": environment}},
        }})
run("kubectl", "get", "pods", "-n", "newrelic")
probe = boto3.client("lambda")
for attempt in range(12):
    response = probe.invoke(FunctionName="fiap-observability-probe", Payload=b'{"require_apm":false}')
    result = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError("New Relic verification failed; inspect the observability probe logs")
    if result.get("healthy"):
        print("Real New Relic cluster telemetry verified")
        break
    time.sleep(15)
else:
    raise RuntimeError("New Relic did not receive cluster telemetry")
print("New Relic metrics, events, logs and Java instrumentation installed")

