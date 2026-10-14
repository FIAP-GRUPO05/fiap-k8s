resource "kubectl_manifest" "namespace" {

  depends_on = [time_sleep.wait_eks_access]

  yaml_body = <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: prod
  YAML

}