resource "helm_release" "newrelic_bundle" {
  name             = "newrelic-bundle"
  repository       = "https://helm-charts.newrelic.com"
  chart            = "nri-bundle"
  version          = "5.0.0"
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
  ]

  depends_on = [aws_eks_node_group.main]
}
