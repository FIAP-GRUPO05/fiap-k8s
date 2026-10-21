locals {
  destroy_read_statements = [
    {
      Effect = "Allow"
      Action = [
        "ec2:DescribeVpcs", "ec2:DescribeInstances", "ec2:DescribeVolumes", "ec2:DescribeSnapshots",
        "ec2:DescribeNatGateways", "ec2:DescribeAddresses", "ec2:DescribeVpcEndpoints", "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeSecurityGroups", "ec2:DescribeSecurityGroupRules", "ec2:DescribeRouteTables", "ec2:DescribeSubnets", "ec2:DescribeInternetGateways",
        "eks:ListClusters", "eks:DescribeCluster", "eks:ListNodegroups", "eks:DescribeNodegroup", "eks:ListFargateProfiles", "eks:DescribeUpdate",
        "rds:DescribeDBInstances", "rds:DescribeDBSnapshots", "rds:DescribeDBInstanceAutomatedBackups", "rds:DescribeDBSubnetGroups",
        "elasticloadbalancing:DescribeLoadBalancers", "elasticloadbalancing:DescribeTargetGroups", "elasticloadbalancing:DescribeTags",
        "lambda:ListFunctions", "secretsmanager:ListSecrets", "kms:ListAliases", "kms:DescribeKey",
        "ecr:DescribeRepositories", "s3:ListAllMyBuckets", "logs:DescribeLogGroups",
        "codebuild:ListProjects", "codebuild:ListBuildsForProject", "codebuild:BatchGetBuilds",
        "events:ListRules", "events:ListTargetsByRule", "iam:ListRoles", "iam:ListOpenIDConnectProviders", "autoscaling:DescribeAutoScalingGroups",
        "ec2:DescribeRegions", "tag:GetResources"
      ]
      Resource = "*"
    },
    {
      Effect   = "Allow"
      Action   = ["apigateway:GET"]
      Resource = "arn:aws:apigateway:sa-east-1::/*"
    },
    {
      Effect   = "Allow"
      Action   = ["ce:GetCostAndUsage"]
      Resource = "*"
    }
  ]
  destroy_mutation_statements = [
    {
      Effect   = "Allow"
      Action   = ["autoscaling:DeleteAutoScalingGroup"]
      Resource = "arn:aws:autoscaling:sa-east-1:456687462806:autoScalingGroup:*:autoScalingGroupName/eks-fiap-shared-*"
    },
    {
      Effect = "Allow"
      Action = [
        "ec2:TerminateInstances", "ec2:DeleteVolume", "ec2:DeleteSnapshot", "ec2:DeleteVpcEndpoints",
        "ec2:DeleteNatGateway", "ec2:ReleaseAddress", "ec2:RevokeSecurityGroupIngress", "ec2:RevokeSecurityGroupEgress",
        "ec2:DeleteSecurityGroup", "ec2:DisassociateRouteTable", "ec2:DeleteRouteTable", "ec2:DeleteSubnet",
        "ec2:DetachInternetGateway", "ec2:DeleteInternetGateway", "ec2:DeleteVpc"
      ]
      Resource = concat([for kind in ["instance", "volume", "snapshot", "vpc-endpoint", "natgateway", "elastic-ip", "security-group", "security-group-rule", "route-table", "subnet", "internet-gateway", "vpc"] : "arn:aws:ec2:sa-east-1:456687462806:${kind}/*"], ["arn:aws:ec2:sa-east-1::snapshot/*"])
    },
    {
      Effect   = "Allow"
      Action   = ["eks:DeleteCluster", "eks:UpdateClusterConfig", "eks:DeleteNodegroup"]
      Resource = ["arn:aws:eks:sa-east-1:456687462806:cluster/fiap-shared", "arn:aws:eks:sa-east-1:456687462806:nodegroup/fiap-shared/*/*"]
    },
    {
      Effect   = "Allow"
      Action   = ["rds:ModifyDBInstance", "rds:DeleteDBInstance", "rds:DeleteDBSnapshot", "rds:DeleteDBInstanceAutomatedBackup", "rds:DeleteDBSubnetGroup"]
      Resource = ["arn:aws:rds:sa-east-1:456687462806:db:fiap-shared-postgres", "arn:aws:rds:sa-east-1:456687462806:snapshot:fiap-*", "arn:aws:rds:sa-east-1:456687462806:auto-backup:*", "arn:aws:rds:sa-east-1:456687462806:subgrp:fiap-shared-postgres"]
    },
    {
      Effect   = "Allow"
      Action   = ["elasticloadbalancing:DeleteLoadBalancer", "elasticloadbalancing:DeleteTargetGroup"]
      Resource = ["arn:aws:elasticloadbalancing:sa-east-1:456687462806:loadbalancer/app/fiap-shared-api/*", "arn:aws:elasticloadbalancing:sa-east-1:456687462806:targetgroup/k8s-*/*"]
    },
    {
      Effect   = "Allow"
      Action   = ["lambda:DeleteFunction"]
      Resource = [for function in ["fiap-auth-develop", "fiap-auth-homol", "fiap-auth-prod", "fiap-uptime-probe", "fiap-observability-probe"] : "arn:aws:lambda:sa-east-1:456687462806:function:${function}"]
    },
    {
      Effect   = "Allow"
      Action   = ["apigateway:DELETE"]
      Resource = ["arn:aws:apigateway:sa-east-1::/apis/*", "arn:aws:apigateway:sa-east-1::/vpclinks/*"]
    },
    {
      Effect   = "Allow"
      Action   = ["secretsmanager:DeleteSecret"]
      Resource = "arn:aws:secretsmanager:sa-east-1:456687462806:secret:fiap/*"
    },
    {
      Effect    = "Allow"
      Action    = ["kms:ScheduleKeyDeletion"]
      Resource  = "arn:aws:kms:sa-east-1:456687462806:key/*"
      Condition = { StringEquals = { "aws:ResourceTag/Project" = "fiap-tech-challenge-fase-3" } }
    },
    {
      Effect   = "Allow"
      Action   = ["ecr:DeleteRepository"]
      Resource = "arn:aws:ecr:sa-east-1:456687462806:repository/fiap-application"
    },
    {
      Effect   = "Allow"
      Action   = ["logs:DeleteLogGroup"]
      Resource = [for prefix in ["/aws/lambda/fiap-", "/aws/apigateway/fiap-", "/aws/codebuild/fiap-", "/aws/eks/fiap-shared/", "/aws/rds/instance/fiap-shared-postgres/"] : "arn:aws:logs:sa-east-1:456687462806:log-group:${prefix}*"]
    },
    {
      Effect   = "Allow"
      Action   = ["codebuild:DeleteProject", "codebuild:StopBuild"]
      Resource = ["arn:aws:codebuild:sa-east-1:456687462806:project/fiap-*", "arn:aws:codebuild:sa-east-1:456687462806:build/fiap-*:*"]
    },
    {
      Effect   = "Allow"
      Action   = ["events:DisableRule", "events:RemoveTargets", "events:DeleteRule"]
      Resource = "arn:aws:events:sa-east-1:456687462806:rule/fiap-uptime-every-five-minutes"
    },
    {
      Effect   = "Allow"
      Action   = ["s3:ListBucket", "s3:ListBucketVersions", "s3:ListBucketMultipartUploads", "s3:DeleteBucket"]
      Resource = "arn:aws:s3:::fiap-tfstate-456687462806"
    },
    {
      Effect   = "Allow"
      Action   = ["s3:DeleteObject", "s3:DeleteObjectVersion", "s3:AbortMultipartUpload"]
      Resource = "arn:aws:s3:::fiap-tfstate-456687462806/*"
    },
    {
      Effect   = "Allow"
      Action   = ["s3:PutObject"]
      Resource = "arn:aws:s3:::fiap-tfstate-456687462806/fiap/operations/state.json"
    }
  ]
}

resource "aws_iam_role" "github_destroy_plan" {
  name = "fiap-gh-plan-destroy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = aws_iam_openid_connect_provider.github.arn }, Action = "sts:AssumeRoleWithWebIdentity"
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        "token.actions.githubusercontent.com:sub" = [
          "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:pull_request",
          "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:environment:aws-destroy",
          "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:ref:refs/heads/main"
        ]
      } }
    }]
  })
}

resource "aws_iam_role_policy" "github_destroy_plan" {
  name   = "fiap-destroy-inventory"
  role   = aws_iam_role.github_destroy_plan.id
  policy = jsonencode({ Version = "2012-10-17", Statement = local.destroy_read_statements })
}

resource "aws_iam_role" "github_destroy" {
  name                 = "fiap-gh-destroy-infra"
  max_session_duration = 14400
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = aws_iam_openid_connect_provider.github.arn }, Action = "sts:AssumeRoleWithWebIdentity"
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        "token.actions.githubusercontent.com:sub" = "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:environment:aws-destroy"
      } }
    }]
  })
}

resource "aws_iam_role_policy" "github_destroy_read" {
  name   = "fiap-destroy-inventory"
  role   = aws_iam_role.github_destroy.id
  policy = jsonencode({ Version = "2012-10-17", Statement = local.destroy_read_statements })
}

resource "aws_iam_role_policy" "github_destroy_write" {
  name   = "fiap-destroy-project-resources"
  role   = aws_iam_role.github_destroy.id
  policy = jsonencode({ Version = "2012-10-17", Statement = local.destroy_mutation_statements })
}

# Existing deployment identities receive only the right to read the live freeze.
resource "aws_iam_role_policy" "github_infra_guard" {
  for_each = toset([
    "fiap-gh-deploy-fiap-application", "fiap-gh-deploy-fiap-database", "fiap-gh-deploy-fiap-k8s",
    "fiap-gh-deploy-fiap-lambda-develop", "fiap-gh-deploy-fiap-lambda-homol", "fiap-gh-deploy-fiap-lambda-prod",
    "fiap-gh-bootstrap-fiap-lambda", "fiap-gh-terraform-fiap-k8s", "fiap-gh-terraform-fiap-database", "fiap-gh-terraform-fiap-lambda"
  ])
  name = "fiap-live-infrastructure-guard"
  role = each.value
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["s3:GetObject"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806/fiap/operations/state.json"
  }] })
}
