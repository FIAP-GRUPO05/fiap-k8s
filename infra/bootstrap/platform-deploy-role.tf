variable "bootstrap_feature_ref" {
  type        = string
  default     = null
  description = "Temporary exact feature ref for the initial bootstrap; leave null after verification."
  validation {
    condition     = var.bootstrap_feature_ref == null ? true : can(regex("^feature/[a-z0-9._/-]+$", var.bootstrap_feature_ref))
    error_message = "Use one exact feature branch or null."
  }
}

resource "aws_iam_role" "github_platform" {
  name = "fiap-gh-deploy-fiap-k8s"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = concat([
            "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:ref:refs/heads/develop",
            "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:ref:refs/heads/release/v*",
            "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:ref:refs/heads/prod"
          ], var.bootstrap_feature_ref == null ? [] : ["repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:ref:refs/heads/${var.bootstrap_feature_ref}"])
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_platform" {
  name = "fiap-platform-bootstrap"
  role = aws_iam_role.github_platform.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:PutSecretValue"], Resource = "arn:aws:secretsmanager:sa-east-1:456687462806:secret:fiap/shared/newrelic-*" },
      { Effect = "Allow", Action = ["codebuild:StartBuild", "codebuild:BatchGetBuilds"], Resource = [
        "arn:aws:codebuild:sa-east-1:456687462806:project/fiap-platform-bootstrap",
        "arn:aws:codebuild:sa-east-1:456687462806:build/fiap-platform-bootstrap:*"
      ] }
    ]
  })
}
