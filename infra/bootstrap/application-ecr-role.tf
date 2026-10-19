resource "aws_iam_role" "github_application_ecr" {
  name = "fiap-gh-deploy-fiap-application"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:${local.github_organization}@${local.github_owner_id}/fiap-application@${local.repositories["fiap-application"]}:ref:refs/heads/develop",
            "repo:${local.github_organization}@${local.github_owner_id}/fiap-application@${local.repositories["fiap-application"]}:ref:refs/heads/release/v*",
            "repo:${local.github_organization}@${local.github_owner_id}/fiap-application@${local.repositories["fiap-application"]}:ref:refs/heads/prod"
          ]
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_application_ecr" {
  name = "fiap-application-ecr-push"
  role = aws_iam_role.github_application_ecr.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:CreateRepository",
          "ecr:DeleteRepository",
          "ecr:DescribeRepositories",
          "ecr:PutLifecyclePolicy",
          "ecr:GetLifecyclePolicy",
          "ecr:DeleteLifecyclePolicy",
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:PutImage",
          "ecr:BatchGetImage",
          "ecr:DescribeImages",
          "ecr:ListImages",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = "arn:aws:ecr:sa-east-1:456687462806:repository/fiap-application"
      },
      {
        Effect    = "Allow", Action = ["s3:ListBucket"],
        Resource  = "arn:aws:s3:::fiap-tfstate-456687462806",
        Condition = { StringLike = { "s3:prefix" = ["fiap/registry.tfstate", "fiap/registry.tfstate.tflock"] } }
      },
      {
        Effect   = "Allow", Action = ["s3:GetObject", "s3:PutObject"],
        Resource = ["arn:aws:s3:::fiap-tfstate-456687462806/fiap/registry.tfstate", "arn:aws:s3:::fiap-tfstate-456687462806/fiap/registry.tfstate.tflock"]
      },
      {
        Effect   = "Allow", Action = ["s3:DeleteObject"],
        Resource = "arn:aws:s3:::fiap-tfstate-456687462806/fiap/registry.tfstate.tflock"
      },
      {
        Effect = "Allow"
        Action = ["codebuild:StartBuild", "codebuild:BatchGetBuilds"]
        Resource = [
          "arn:aws:codebuild:sa-east-1:456687462806:project/fiap-eks-deploy",
          "arn:aws:codebuild:sa-east-1:456687462806:build/fiap-eks-deploy:*"
        ]
      },
      {
        Effect   = "Allow", Action = ["secretsmanager:GetSecretValue"],
        Resource = [for environment in ["develop", "homol", "prod"] : "arn:aws:secretsmanager:sa-east-1:456687462806:secret:fiap/${environment}/admin-*"]
      }
    ]
  })
}
