# Each namespace can invoke only its own notification alias.
resource "aws_iam_role" "application_notifications" {
  for_each = toset(["develop", "homol", "prod"])
  name     = "fiap-application-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Service = "pods.eks.amazonaws.com" },
      Action = ["sts:AssumeRole", "sts:TagSession"],
      Condition = { StringEquals = {
        "aws:RequestTag/eks-cluster-name"           = var.cluster_name,
        "aws:RequestTag/kubernetes-namespace"       = each.key,
        "aws:RequestTag/kubernetes-service-account" = "fiap-application"
      } }
    }]
  })
}

resource "aws_iam_role_policy" "application_notifications" {
  for_each = aws_iam_role.application_notifications
  name     = "fiap-notification-invoke"
  role     = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["lambda:InvokeFunction"],
    Resource = "arn:aws:lambda:sa-east-1:456687462806:function:fiap-email-${each.key}:live" }]
  })
}

resource "aws_eks_pod_identity_association" "application_notifications" {
  for_each        = aws_iam_role.application_notifications
  cluster_name    = aws_eks_cluster.main.name
  namespace       = each.key
  service_account = "fiap-application"
  role_arn        = each.value.arn
  depends_on      = [aws_eks_addon.pod_identity, aws_iam_role_policy.application_notifications]
}
