resource "aws_iam_role" "github_database" {
  name = "fiap-gh-deploy-fiap-database"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = aws_iam_openid_connect_provider.github.arn },
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike = { "token.actions.githubusercontent.com:sub" = [
          for ref in ["develop", "release/v*", "prod"] : "repo:${local.github_organization}@${local.github_owner_id}/fiap-database@${local.repositories["fiap-database"]}:ref:refs/heads/${ref}"
        ] }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_database" {
  name = "fiap-private-database-verification"
  role = aws_iam_role.github_database.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = ["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
      Resource = ["arn:aws:codebuild:sa-east-1:456687462806:project/fiap-database-bootstrap", "arn:aws:codebuild:sa-east-1:456687462806:build/fiap-database-bootstrap:*"]
    }]
  })
}
