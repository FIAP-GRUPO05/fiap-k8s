"""Deploy ECR images using Kubernetes Secret references and real health checks."""
import base64
import json
import os
import re
import subprocess
import time
import boto3

env = os.environ["DEPLOY_NAMESPACE"]
image = os.environ["IMAGE_URI"]
prefix = f"/{env}"
issuer = os.environ.get("JWT_ISSUER", "")
if env not in {"develop", "homol", "prod"}:
    raise ValueError("Invalid namespace")
if not re.fullmatch(r"456687462806\.dkr\.ecr\.sa-east-1\.amazonaws\.com/fiap-application(?::[A-Za-z0-9_.-]+|@sha256:[a-f0-9]{64})", image) or image.endswith(":latest"):
    raise ValueError("Use an immutable application ECR image")
if env == "prod" and not issuer:
    raise ValueError("Production requires the API Gateway JWT issuer")

def kubectl(*args, document=None, capture=False):
    return subprocess.run(["kubectl", "-n", env, *args], text=True, check=True,
        input=json.dumps(document) if document is not None else None, capture_output=capture)

def apply(document):
    kubectl("apply", "--server-side", "--field-manager=fiap-cicd", "-f", "-", document=document)

apply({"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "fiap-application"},
       "automountServiceAccountToken": False})
client = boto3.client("secretsmanager")
db = json.loads(client.get_secret_value(SecretId=f"fiap/{env}/postgres")["SecretString"])
app = json.loads(client.get_secret_value(SecretId=f"fiap/{env}/application")["SecretString"])
values = {
    "SPRING_DATASOURCE_URL": f"jdbc:postgresql://{db['host']}:5432/{db['dbname']}?sslmode=require",
    "SPRING_DATASOURCE_USERNAME": db["username"],
    "SPRING_DATASOURCE_PASSWORD": db["password"],
    "JWT_SECRET": app["jwt_secret"],
}
apply({"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "api-secret"}, "type": "Opaque",
    "data": {key: base64.b64encode(value.encode()).decode() for key, value in values.items()}})
container = {
    "name": "api-container", "image": image, "imagePullPolicy": "IfNotPresent",
    "ports": [{"name": "http", "containerPort": 8080}],
    "envFrom": [{"secretRef": {"name": "api-secret"}}],
    "env": [{"name": "MAIL_TIPE", "value": "LAMBDA"}, {"name": "AWS_REGION", "value": "sa-east-1"},
        {"name": "NOTIFICATIONS_LAMBDA_FUNCTION", "value": f"fiap-email-{env}:live"}, {"name": "NEW_RELIC_APP_NAME", "value": f"fiap-api-{env}"},
        {"name": "SPRING_PROFILES_ACTIVE", "value": "json-logs"},
        {"name": "NEW_RELIC_LOG", "value": "STDOUT"},
        {"name": "SERVER_SERVLET_CONTEXT_PATH", "value": prefix}],
    "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
    "resources": {"requests": {"cpu": "250m", "memory": "512Mi"}, "limits": {"cpu": "1", "memory": "768Mi"}},
    "volumeMounts": [{"name": "java-tmp", "mountPath": "/tmp"}],
}
if issuer:
    container["env"].extend([{"name": "JWT_ISSUER", "value": issuer},
        {"name": "JWT_AUDIENCE", "value": "fiap-api"}, {"name": "APP_PUBLIC_URL", "value": issuer}])
for probe, path in (("startupProbe", "liveness"), ("readinessProbe", "readiness"), ("livenessProbe", "liveness")):
    container[probe] = {"httpGet": {"path": f"{prefix}/actuator/health/{path}", "port": "http"}, "periodSeconds": 10}
container["startupProbe"]["failureThreshold"] = 36
apply({"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "api-deployment"}, "spec": {
    "selector": {"matchLabels": {"app": "api"}}, "template": {
        "metadata": {"labels": {"app": "api", "environment": env}}, "spec": {
            "serviceAccountName": "fiap-application", "automountServiceAccountToken": False,
            "securityContext": {"runAsNonRoot": True, "runAsUser": 1001, "runAsGroup": 1001,
                "fsGroup": 1001, "seccompProfile": {"type": "RuntimeDefault"}},
            "containers": [container], "volumes": [{"name": "java-tmp", "emptyDir": {"sizeLimit": "128Mi"}}],
        }}}})
apply({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "api-service"}, "spec": {
    "type": "ClusterIP", "selector": {"app": "api"},
    "ports": [{"name": "http", "port": 80, "targetPort": "http"}]}})
apply({"apiVersion": "networking.k8s.io/v1", "kind": "Ingress", "metadata": {
    "name": "api-ingress", "annotations": {
        "alb.ingress.kubernetes.io/group.name": "fiap-shared",
        "alb.ingress.kubernetes.io/load-balancer-name": "fiap-shared-api",
        "alb.ingress.kubernetes.io/scheme": "internal",
        "alb.ingress.kubernetes.io/target-type": "ip",
        "alb.ingress.kubernetes.io/inbound-cidrs": os.environ.get("VPC_CIDR", "10.42.0.0/16"),
        "alb.ingress.kubernetes.io/healthcheck-path": f"{prefix}/actuator/health",
        "alb.ingress.kubernetes.io/listen-ports": '[{"HTTP":80}]',
    }}, "spec": {"ingressClassName": "alb", "rules": [{"http": {"paths": [{
        "path": prefix, "pathType": "Prefix", "backend": {"service": {"name": "api-service", "port": {"number": 80}}}
    }]}}]}})
apply({"apiVersion": "autoscaling/v2", "kind": "HorizontalPodAutoscaler", "metadata": {"name": "api-hpa"}, "spec": {
    "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": "api-deployment"},
    "minReplicas": 2 if env == "prod" else 1, "maxReplicas": 4 if env == "prod" else 2,
    "metrics": [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}}}]}})
kubectl("rollout", "status", "deployment/api-deployment", "--timeout=8m")
result = kubectl("exec", "deployment/api-deployment", "-c", "api-container", "--", "curl",
    "--fail", "--silent", "--show-error", f"http://127.0.0.1:8080{prefix}/actuator/health", capture=True)
if json.loads(result.stdout).get("status") != "UP":
    raise RuntimeError("Application/database health check failed")
kubectl("exec", "deployment/api-deployment", "-c", "api-container", "--", "curl", "--fail", "--silent",
    "--show-error", "--output", "/dev/null", f"http://127.0.0.1:8080{prefix}/v3/api-docs")
pods = json.loads(kubectl("get", "pods", "-l", "app=api", "-o", "json", capture=True).stdout)["items"]
active = [pod for pod in pods if not pod["metadata"].get("deletionTimestamp")]
if not active or not all(any("newrelic-java-init@sha256:" in init.get("image", "")
    for init in pod["spec"].get("initContainers", [])) for pod in active):
    raise RuntimeError("The deployed application pods must contain the pinned New Relic Java agent")
probe = boto3.client("lambda")
for attempt in range(12):
    response = probe.invoke(FunctionName="fiap-observability-probe", Payload=json.dumps({
        "environment": env, "require_apm": True}).encode())
    status = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError("New Relic verification failed; inspect the observability probe CloudWatch logs")
    if status.get("healthy"):
        print(f"Real New Relic cluster and APM telemetry verified: {env}")
        break
    print("Waiting for New Relic telemetry ingestion", flush=True)
    time.sleep(15)
else:
    raise RuntimeError("New Relic did not receive cluster and application telemetry within the deployment window")
print(f"Deployment and database health verified: {env}")

