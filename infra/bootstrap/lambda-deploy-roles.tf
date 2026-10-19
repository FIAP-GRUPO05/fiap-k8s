variable "bootstrap_lambda_feature_ref" {
  type        = string
  default     = null
  description = "Exact temporary feature ref for the initial JWT key import; leave null afterwards."
  validation {
    condition     = var.bootstrap_lambda_feature_ref == null ? true : can(regex("^feature/[a-z0-9._/-]+$", var.bootstrap_lambda_feature_ref))
    error_message = "Use one exact feature branch or null."
  }
}

locals { lambda_refs = { develop = "develop", homol = "release/v*", prod = "prod" } }

resource "aws_iam_role" "github_lambda" {
  for_each = local.lambda_refs
  name     = "fiap-gh-deploy-fiap-lambda-${each.key}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = aws_iam_openid_connect_provider.github.arn },
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = "repo:${local.github_organization}@${local.github_owner_id}/fiap-lambda@${local.repositories["fiap-lambda"]}:ref:refs/heads/${each.value}" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_lambda" {
  for_each = local.lambda_refs
  name     = "fiap-lambda-code-deploy-${each.key}"
  role     = aws_iam_role.github_lambda[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["lambda:UpdateFunctionCode", "lambda:GetFunction", "lambda:GetFunctionConfiguration", "lambda:PublishVersion", "lambda:GetAlias", "lambda:UpdateAlias", "lambda:InvokeFunction"]
      Resource = [
        "arn:aws:lambda:sa-east-1:456687462806:function:fiap-auth-${each.key}",
        "arn:aws:lambda:sa-east-1:456687462806:function:fiap-auth-${each.key}:*"
      ]
    }]
  })
}

resource "aws_iam_role" "github_lambda_keys" {
  name = "fiap-gh-bootstrap-fiap-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = aws_iam_openid_connect_provider.github.arn },
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike = { "token.actions.githubusercontent.com:sub" = concat([
          for ref in ["develop", "release/v*", "prod"] : "repo:${local.github_organization}@${local.github_owner_id}/fiap-lambda@${local.repositories["fiap-lambda"]}:ref:refs/heads/${ref}"
        ], var.bootstrap_lambda_feature_ref == null ? [] : ["repo:${local.github_organization}@${local.github_owner_id}/fiap-lambda@${local.repositories["fiap-lambda"]}:ref:refs/heads/${var.bootstrap_lambda_feature_ref}"]) }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_lambda_keys" {
  name = "fiap-jwt-key-bootstrap"
  role = aws_iam_role.github_lambda_keys.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = ["secretsmanager:DescribeSecret", "secretsmanager:PutSecretValue"],
      Resource = [for environment in keys(local.lambda_refs) : "arn:aws:secretsmanager:sa-east-1:456687462806:secret:fiap/${environment}/jwt-signing-*"]
    }]
  })
}
