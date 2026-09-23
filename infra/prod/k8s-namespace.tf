resource "kubectl_manifest" "namespace" {

  depends_on = [aws_eks_access_policy_association.eks_policy_console]

  yaml_body = <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: prod
  YAML

}