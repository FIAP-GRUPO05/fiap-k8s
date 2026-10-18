"""Deploy ECR images using Kubernetes Secret references and real health checks."""
import base64
import json
import os
import re
import subprocess
import boto3

env = os.environ["DEPLOY_NAMESPACE"]
image = os.environ["IMAGE_URI"]
if env not in {"develop", "homol", "prod"}:
    raise ValueError("Invalid namespace")
if not re.fullmatch(r"456687462806\.dkr\.ecr\.sa-east-1\.amazonaws\.com/fiap-application(?::[A-Za-z0-9_.-]+|@sha256:[a-f0-9]{64})", image) or image.endswith(":latest"):
    raise ValueError("Use an immutable application ECR image")

def kubectl(*args, document=None, capture=False):
    return subprocess.run(["kubectl", "-n", env, *args], text=True, check=True,
        input=json.dumps(document) if document is not None else None, capture_output=capture)

def apply(document):
    kubectl("apply", "--server-side", "--field-manager=fiap-cicd", "-f", "-", document=document)

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
    "env": [{"name": "MAIL_TIPE", "value": "NONE"}, {"name": "NEW_RELIC_APP_NAME", "value": f"fiap-api-{env}"}],
    "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
    "resources": {"requests": {"cpu": "250m", "memory": "512Mi"}, "limits": {"cpu": "1", "memory": "768Mi"}},
    "volumeMounts": [{"name": "java-tmp", "mountPath": "/tmp"}],
}
for probe, path in (("startupProbe", "liveness"), ("readinessProbe", "readiness"), ("livenessProbe", "liveness")):
    container[probe] = {"httpGet": {"path": f"/actuator/health/{path}", "port": "http"}, "periodSeconds": 10}
container["startupProbe"]["failureThreshold"] = 36
apply({"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "api-deployment"}, "spec": {
    "selector": {"matchLabels": {"app": "api"}}, "template": {
        "metadata": {"labels": {"app": "api", "environment": env}}, "spec": {
            "automountServiceAccountToken": False,
            "securityContext": {"runAsNonRoot": True, "runAsUser": 1001, "runAsGroup": 1001,
                "fsGroup": 1001, "seccompProfile": {"type": "RuntimeDefault"}},
            "containers": [container], "volumes": [{"name": "java-tmp", "emptyDir": {"sizeLimit": "128Mi"}}],
        }}}})
apply({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "api-service"}, "spec": {
    "type": "LoadBalancer" if env == "prod" else "ClusterIP", "selector": {"app": "api"},
    "ports": [{"name": "http", "port": 80, "targetPort": "http"}]}})
apply({"apiVersion": "autoscaling/v2", "kind": "HorizontalPodAutoscaler", "metadata": {"name": "api-hpa"}, "spec": {
    "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": "api-deployment"},
    "minReplicas": 2 if env == "prod" else 1, "maxReplicas": 4 if env == "prod" else 2,
    "metrics": [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}}}]}})
kubectl("rollout", "status", "deployment/api-deployment", "--timeout=8m")
result = kubectl("exec", "deployment/api-deployment", "-c", "api-container", "--", "curl",
    "--fail", "--silent", "--show-error", "http://127.0.0.1:8080/actuator/health", capture=True)
if json.loads(result.stdout).get("status") != "UP":
    raise RuntimeError("Application/database health check failed")
print(f"Deployment and database health verified: {env}")

