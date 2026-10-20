# PRs can query aggregate telemetry, never read New Relic/API/database credentials.
resource "aws_iam_role_policy" "preflight_observability" {
  for_each = local.repositories
  name     = "fiap-aggregate-telemetry-verification"
  role     = aws_iam_role.github_preflight[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = ["lambda:InvokeFunction"],
      Resource = "arn:aws:lambda:sa-east-1:456687462806:function:fiap-observability-probe"
    }]
  })
}

resource "aws_iam_role_policy" "application_observability" {
  name   = "fiap-application-telemetry-verification"
  role   = aws_iam_role.github_application_ecr.id
  policy = aws_iam_role_policy.preflight_observability["fiap-application"].policy
}
