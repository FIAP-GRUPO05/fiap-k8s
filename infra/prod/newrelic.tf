resource "helm_release" "newrelic_bundle" {
  name             = "newrelic-bundle"
  repository       = "https://helm-charts.newrelic.com"
  chart            = "nri-bundle"
  version          = "8.0.30"
  namespace        = "newrelic"
  create_namespace = true

  set_sensitive = [
    { name = "global.licenseKey", value = var.newrelic_license_key },
  ]

  set = [
    { name = "global.cluster", value = aws_eks_cluster.main.name },
    { name = "newrelic-infrastructure.enabled", value = "true" },
    { name = "nri-metadata-injection.enabled", value = "true" },
    { name = "kube-state-metrics.enabled", value = "true" },
    { name = "nri-kube-events.enabled", value = "true" },
    { name = "newrelic-logging.enabled", value = "true" },
    # Injeta o agente APM nos pods selecionados pelos recursos Instrumentation
    { name = "k8s-agents-operator.enabled", value = "true" },
  ]

  depends_on = [aws_eks_node_group.main]
}

# Injeta o agente Java do New Relic nos pods da API (label app=api), sem
# alterar a imagem: o operador adiciona um initContainer com o agente e o
# JAVA_TOOL_OPTIONS=-javaagent:... no pod.
resource "kubectl_manifest" "newrelic_instrumentation_java" {
  depends_on = [helm_release.newrelic_bundle]
  yaml_body  = <<YAML
apiVersion: newrelic.com/v1alpha2
kind: Instrumentation
metadata:
  name: newrelic-instrumentation-java
  namespace: newrelic
spec:
  agent:
    language: java
    image: newrelic/newrelic-java-init:latest
    env:
      - name: NEW_RELIC_APP_NAME
        value: "fiap-api"
      - name: NEW_RELIC_DISTRIBUTED_TRACING_ENABLED
        value: "true"
  podLabelSelector:
    matchExpressions:
      - key: "app"
        operator: "In"
        values: ["api"]
YAML
}
