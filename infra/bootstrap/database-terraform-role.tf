resource "aws_iam_role" "github_database_terraform" {
  name = "fiap-gh-terraform-fiap-database"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:${local.github_organization}@${local.github_owner_id}/fiap-database@${local.repositories["fiap-database"]}:ref:refs/heads/prod"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_database_terraform" {
  name = "fiap-database-terraform"
  role = aws_iam_role.github_database_terraform.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow", Action = ["s3:ListBucket"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806"
        Condition = { StringLike = { "s3:prefix" = ["fiap/database-shared.tfstate", "fiap/database-shared.tfstate.tflock", "fiap/platform-shared.tfstate"] } }
      },
      {
        Effect = "Allow", Action = ["s3:GetObject"], Resource = [
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/database-shared.tfstate",
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/database-shared.tfstate.tflock",
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/platform-shared.tfstate"
        ]
      },
      {
        Effect = "Allow", Action = ["s3:PutObject"], Resource = [
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/database-shared.tfstate",
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/database-shared.tfstate.tflock",
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/bootstrap/bootstrap_databases.py"
        ]
      },
      {
        Effect = "Allow", Action = ["s3:DeleteObject"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806/fiap/database-shared.tfstate.tflock"
      },
      {
        Effect = "Allow", Action = ["rds:Describe*", "rds:ListTagsForResource"], Resource = "*"
      },
      {
        Effect = "Allow", Action = ["rds:CreateDBInstance", "rds:ModifyDBInstance", "rds:DeleteDBInstance", "rds:AddTagsToResource", "rds:RemoveTagsFromResource"], Resource = "arn:aws:rds:sa-east-1:456687462806:db:fiap-*"
      },
      {
        Effect = "Allow", Action = ["rds:CreateDBSubnetGroup", "rds:ModifyDBSubnetGroup", "rds:DeleteDBSubnetGroup", "rds:AddTagsToResource", "rds:RemoveTagsFromResource"], Resource = "arn:aws:rds:sa-east-1:456687462806:subgrp:fiap-*"
      },
      {
        Effect = "Allow", Action = ["ec2:Describe*"], Resource = "*"
      },
      {
        Effect = "Allow", Action = ["ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup", "ec2:CreateTags", "ec2:DeleteTags", "ec2:CreateSecurityGroupRule", "ec2:DeleteSecurityGroupRule", "ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress", "ec2:AuthorizeSecurityGroupEgress", "ec2:RevokeSecurityGroupEgress"], Resource = [
          "arn:aws:ec2:sa-east-1:456687462806:security-group/*", "arn:aws:ec2:sa-east-1:456687462806:security-group-rule/*", "arn:aws:ec2:sa-east-1:456687462806:vpc/*"
        ]
      },
      {
        Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:DescribeLogGroups", "logs:ListTagsForResource", "logs:TagResource", "logs:UntagResource", "logs:PutRetentionPolicy"], Resource = [
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/codebuild/fiap-database-bootstrap",
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/codebuild/fiap-database-bootstrap:*"
        ]
      },
      {
        Effect = "Allow", Action = ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateAssumeRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:TagRole", "iam:UntagRole", "iam:PassRole", "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy"], Resource = "arn:aws:iam::456687462806:role/fiap-database-bootstrap"
      },
      {
        Effect = "Allow", Action = ["codebuild:CreateProject", "codebuild:UpdateProject", "codebuild:DeleteProject", "codebuild:BatchGetProjects", "codebuild:ListTagsForResource"], Resource = "arn:aws:codebuild:sa-east-1:456687462806:project/fiap-database-bootstrap"
      }
    ]
  })
}
