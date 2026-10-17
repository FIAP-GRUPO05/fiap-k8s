output "github_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}

output "github_preflight_role_arns" {
  value = { for repository, role in aws_iam_role.github_preflight : repository => role.arn }
}

