resource "aws_iam_role" "github_lambda_terraform" {
  name = "fiap-gh-terraform-fiap-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          "token.actions.githubusercontent.com:sub" = "repo:${local.github_organization}@${local.github_owner_id}/fiap-lambda@${local.repositories["fiap-lambda"]}:ref:refs/heads/prod"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_lambda_terraform" {
  name = "fiap-lambda-terraform"
  role = aws_iam_role.github_lambda_terraform.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow", Action = ["s3:ListBucket"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806"
        Condition = { StringLike = { "s3:prefix" = ["fiap/lambda-shared.tfstate", "fiap/lambda-shared.tfstate.tflock", "fiap/platform-shared.tfstate", "fiap/database-shared.tfstate"] } }
      },
      {
        Effect = "Allow", Action = ["s3:GetObject"], Resource = [for key in ["fiap/lambda-shared.tfstate", "fiap/lambda-shared.tfstate.tflock", "fiap/platform-shared.tfstate", "fiap/database-shared.tfstate"] : "arn:aws:s3:::fiap-tfstate-456687462806/${key}"]
      },
      {
        Effect = "Allow", Action = ["s3:PutObject"], Resource = [for key in ["fiap/lambda-shared.tfstate", "fiap/lambda-shared.tfstate.tflock"] : "arn:aws:s3:::fiap-tfstate-456687462806/${key}"]
      },
      {
        Effect = "Allow", Action = ["s3:DeleteObject"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806/fiap/lambda-shared.tfstate.tflock"
      },
      {
        Effect = "Allow", Action = ["secretsmanager:DescribeSecret", "secretsmanager:GetResourcePolicy"], Resource = "arn:aws:secretsmanager:sa-east-1:456687462806:secret:fiap/*/postgres-*"
      },
      {
        Effect = "Allow", Action = ["secretsmanager:CreateSecret", "secretsmanager:DeleteSecret", "secretsmanager:DescribeSecret", "secretsmanager:GetResourcePolicy", "secretsmanager:UpdateSecret", "secretsmanager:TagResource", "secretsmanager:UntagResource", "secretsmanager:RestoreSecret"], Resource = "arn:aws:secretsmanager:sa-east-1:456687462806:secret:fiap/*/jwt-signing-*"
      },
      {
        Effect = "Allow", Action = ["lambda:CreateFunction", "lambda:DeleteFunction", "lambda:GetFunction", "lambda:GetFunctionConfiguration", "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration", "lambda:PublishVersion", "lambda:ListVersionsByFunction", "lambda:ListTags", "lambda:TagResource", "lambda:UntagResource", "lambda:CreateAlias", "lambda:GetAlias", "lambda:UpdateAlias", "lambda:DeleteAlias", "lambda:AddPermission", "lambda:GetPolicy", "lambda:RemovePermission"], Resource = [
          "arn:aws:lambda:sa-east-1:456687462806:function:fiap-auth-*", "arn:aws:lambda:sa-east-1:456687462806:function:fiap-email-*"
        ]
      },
      {
        Effect = "Allow", Action = ["apigateway:GET", "apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE"], Resource = ["arn:aws:apigateway:sa-east-1::/apis", "arn:aws:apigateway:sa-east-1::/apis/*"]
      },
      {
        Effect = "Allow", Action = ["apigateway:GET", "apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE"], Resource = ["arn:aws:apigateway:sa-east-1::/vpclinks", "arn:aws:apigateway:sa-east-1::/vpclinks/*"]
      },
      {
        Effect = "Allow", Action = ["lambda:GetFunctionCodeSigningConfig"], Resource = ["arn:aws:lambda:sa-east-1:456687462806:function:fiap-auth-*", "arn:aws:lambda:sa-east-1:456687462806:function:fiap-email-*"]
      },
      {
        Effect = "Allow", Action = ["logs:DescribeLogGroups"], Resource = "*"
      },
      {
        Effect = "Allow", Action = ["elasticloadbalancing:DescribeLoadBalancers", "elasticloadbalancing:DescribeLoadBalancerAttributes", "elasticloadbalancing:DescribeListeners", "elasticloadbalancing:DescribeListenerAttributes", "elasticloadbalancing:DescribeTags", "ec2:Describe*"], Resource = "*"
      },
      {
        Effect = "Allow", Action = ["ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup", "ec2:CreateTags", "ec2:DeleteTags", "ec2:AuthorizeSecurityGroupEgress", "ec2:RevokeSecurityGroupEgress", "ec2:ModifySecurityGroupRules"], Resource = [
          "arn:aws:ec2:sa-east-1:456687462806:security-group/*", "arn:aws:ec2:sa-east-1:456687462806:security-group-rule/*", "arn:aws:ec2:sa-east-1:456687462806:vpc/*"
        ]
      },
      {
        Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:DescribeLogGroups", "logs:ListTagsForResource", "logs:TagResource", "logs:UntagResource", "logs:PutRetentionPolicy"], Resource = [
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/lambda/fiap-auth-*",
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/lambda/fiap-email-*",
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/apigateway/fiap-*"
        ]
      },
      {
        Effect = "Allow", Action = ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateAssumeRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:TagRole", "iam:UntagRole", "iam:PassRole", "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy"], Resource = ["arn:aws:iam::456687462806:role/fiap-auth-*", "arn:aws:iam::456687462806:role/fiap-email-*"]
      }
    ]
  })
}
