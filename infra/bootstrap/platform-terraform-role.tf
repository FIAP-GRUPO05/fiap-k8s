locals {
  platform_role_names        = ["fiap-shared-eks-cluster", "fiap-shared-eks-nodes", "fiap-aws-load-balancer-controller", "fiap-eks-deploy-runner", "fiap-platform-bootstrap", "fiap-observability-probe", "fiap-uptime-probe", "fiap-application-develop", "fiap-application-homol", "fiap-application-prod"]
  platform_network_resources = [for kind in ["vpc", "subnet", "internet-gateway", "route-table", "elastic-ip", "natgateway", "vpc-endpoint", "security-group", "security-group-rule", "network-interface"] : "arn:aws:ec2:sa-east-1:456687462806:${kind}/*"]
}

resource "aws_iam_role" "github_platform_terraform" {
  name = "fiap-gh-terraform-fiap-k8s"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Federated = aws_iam_openid_connect_provider.github.arn }, Action = "sts:AssumeRoleWithWebIdentity"
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        "token.actions.githubusercontent.com:sub" = "repo:${local.github_organization}@${local.github_owner_id}/fiap-k8s@${local.repositories["fiap-k8s"]}:ref:refs/heads/prod"
      } }
    }]
  })
}

resource "aws_iam_role_policy" "github_platform_terraform" {
  name = "fiap-platform-terraform"
  role = aws_iam_role.github_platform_terraform.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow", Action = ["s3:ListBucket"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806"
        Condition = { StringLike = { "s3:prefix" = ["fiap/platform-shared.tfstate", "fiap/platform-shared.tfstate.tflock", "fiap/platform/scripts/*"] } }
      },
      {
        Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = [
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/platform-shared.tfstate",
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/platform-shared.tfstate.tflock",
          "arn:aws:s3:::fiap-tfstate-456687462806/fiap/platform/scripts/*"
        ]
      },
      { Effect = "Allow", Action = ["s3:GetObjectTagging", "s3:PutObjectTagging"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806/fiap/platform/scripts/*" },
      { Effect = "Allow", Action = ["s3:DeleteObject"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806/fiap/platform-shared.tfstate.tflock" },
      { Effect = "Allow", Action = ["ec2:Describe*", "logs:DescribeLogGroups", "eks:DescribeAddonVersions", "eks:DescribeClusterVersions"], Resource = "*" },
      {
        Effect = "Allow", Action = [
          "ec2:CreateVpc", "ec2:DeleteVpc", "ec2:ModifyVpcAttribute", "ec2:CreateSubnet", "ec2:DeleteSubnet", "ec2:ModifySubnetAttribute",
          "ec2:CreateInternetGateway", "ec2:DeleteInternetGateway", "ec2:AttachInternetGateway", "ec2:DetachInternetGateway",
          "ec2:CreateRouteTable", "ec2:DeleteRouteTable", "ec2:AssociateRouteTable", "ec2:DisassociateRouteTable", "ec2:ReplaceRouteTableAssociation",
          "ec2:CreateRoute", "ec2:DeleteRoute", "ec2:ReplaceRoute", "ec2:AllocateAddress", "ec2:ReleaseAddress",
          "ec2:CreateNatGateway", "ec2:DeleteNatGateway", "ec2:CreateVpcEndpoint", "ec2:DeleteVpcEndpoints", "ec2:ModifyVpcEndpoint",
          "ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup", "ec2:AuthorizeSecurityGroupIngress", "ec2:AuthorizeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress", "ec2:RevokeSecurityGroupEgress", "ec2:ModifySecurityGroupRules", "ec2:CreateTags", "ec2:DeleteTags"
        ], Resource = local.platform_network_resources
      },
      {
        Effect = "Allow", Action = [
          "eks:CreateCluster", "eks:DescribeCluster", "eks:UpdateClusterConfig", "eks:UpdateClusterVersion", "eks:DeleteCluster", "eks:DescribeUpdate",
          "eks:CreateNodegroup", "eks:DescribeNodegroup", "eks:UpdateNodegroupConfig", "eks:UpdateNodegroupVersion", "eks:DeleteNodegroup",
          "eks:CreateAddon", "eks:DescribeAddon", "eks:UpdateAddon", "eks:DeleteAddon", "eks:TagResource", "eks:UntagResource", "eks:ListTagsForResource",
          "eks:CreateAccessEntry", "eks:DescribeAccessEntry", "eks:UpdateAccessEntry", "eks:DeleteAccessEntry", "eks:AssociateAccessPolicy", "eks:DisassociateAccessPolicy", "eks:ListAssociatedAccessPolicies",
          "eks:CreatePodIdentityAssociation", "eks:DescribePodIdentityAssociation", "eks:UpdatePodIdentityAssociation", "eks:DeletePodIdentityAssociation"
          ], Resource = [
          "arn:aws:eks:sa-east-1:456687462806:cluster/fiap-shared",
          "arn:aws:eks:sa-east-1:456687462806:nodegroup/fiap-shared/*",
          "arn:aws:eks:sa-east-1:456687462806:addon/fiap-shared/*",
          "arn:aws:eks:sa-east-1:456687462806:access-entry/fiap-shared/*",
          "arn:aws:eks:sa-east-1:456687462806:podidentityassociation/fiap-shared/*"
        ]
      },
      {
        Effect   = "Allow", Action = ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:UpdateAssumeRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:TagRole", "iam:UntagRole", "iam:PassRole", "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy"],
        Resource = [for name in local.platform_role_names : "arn:aws:iam::456687462806:role/${name}"]
      },
      {
        Effect    = "Allow", Action = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"], Resource = [for name in local.platform_role_names : "arn:aws:iam::456687462806:role/${name}"]
        Condition = { ArnEquals = { "iam:PolicyARN" = ["arn:aws:iam::aws:policy/AmazonEKSClusterPolicy", "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy", "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPullOnly", "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy", "arn:aws:iam::456687462806:policy/fiap-aws-load-balancer-controller"] } }
      },
      {
        Effect = "Allow", Action = ["iam:CreatePolicy", "iam:DeletePolicy", "iam:GetPolicy", "iam:GetPolicyVersion", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion", "iam:ListPolicyVersions", "iam:TagPolicy", "iam:UntagPolicy"], Resource = "arn:aws:iam::456687462806:policy/fiap-aws-load-balancer-controller"
      },
      {
        Effect    = "Allow", Action = ["iam:CreateServiceLinkedRole"], Resource = "arn:aws:iam::456687462806:role/aws-service-role/*"
        Condition = { StringEquals = { "iam:AWSServiceName" = ["eks.amazonaws.com", "eks-nodegroup.amazonaws.com"] } }
      },
      {
        Effect    = "Allow", Action = ["kms:CreateKey"], Resource = "*"
        Condition = { StringEquals = { "aws:RequestTag/Project" = "fiap-tech-challenge-fase-3" } }
      },
      {
        Effect    = "Allow", Action = ["kms:DescribeKey", "kms:GetKeyPolicy", "kms:GetKeyRotationStatus", "kms:ListResourceTags", "kms:EnableKeyRotation", "kms:DisableKeyRotation", "kms:PutKeyPolicy", "kms:UpdateKeyDescription", "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion", "kms:TagResource", "kms:UntagResource", "kms:CreateGrant", "kms:ListGrants", "kms:RevokeGrant"], Resource = "arn:aws:kms:sa-east-1:456687462806:key/*"
        Condition = { StringEquals = { "aws:ResourceTag/Project" = "fiap-tech-challenge-fase-3" } }
      },
      {
        Effect = "Allow", Action = ["kms:CreateAlias", "kms:UpdateAlias", "kms:DeleteAlias"], Resource = ["arn:aws:kms:sa-east-1:456687462806:alias/fiap-*", "arn:aws:kms:sa-east-1:456687462806:key/*"]
      },
      { Effect = "Allow", Action = ["kms:ListAliases"], Resource = "*" },
      { Effect = "Allow", Action = ["lambda:ListVersionsByFunction"], Resource = ["arn:aws:lambda:sa-east-1:456687462806:function:fiap-observability-probe", "arn:aws:lambda:sa-east-1:456687462806:function:fiap-uptime-probe"] },
      {
        Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:ListTagsForResource", "logs:TagResource", "logs:UntagResource", "logs:PutRetentionPolicy"], Resource = [
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/eks/fiap-shared/*",
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/codebuild/fiap-*",
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/lambda/fiap-observability-probe*",
          "arn:aws:logs:sa-east-1:456687462806:log-group:/aws/lambda/fiap-uptime-probe*"
        ]
      },
      {
        Effect = "Allow", Action = ["codebuild:CreateProject", "codebuild:UpdateProject", "codebuild:DeleteProject", "codebuild:BatchGetProjects"], Resource = ["arn:aws:codebuild:sa-east-1:456687462806:project/fiap-eks-deploy", "arn:aws:codebuild:sa-east-1:456687462806:project/fiap-platform-bootstrap"]
      },
      {
        Effect = "Allow", Action = ["secretsmanager:CreateSecret", "secretsmanager:DeleteSecret", "secretsmanager:DescribeSecret", "secretsmanager:GetResourcePolicy", "secretsmanager:UpdateSecret", "secretsmanager:TagResource", "secretsmanager:UntagResource", "secretsmanager:RestoreSecret"], Resource = "arn:aws:secretsmanager:sa-east-1:456687462806:secret:fiap/shared/newrelic-*"
      },
      {
        Effect = "Allow", Action = ["lambda:CreateFunction", "lambda:DeleteFunction", "lambda:GetFunction", "lambda:GetFunctionConfiguration", "lambda:GetFunctionCodeSigningConfig", "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration", "lambda:ListTags", "lambda:TagResource", "lambda:UntagResource", "lambda:AddPermission", "lambda:RemovePermission", "lambda:GetPolicy"], Resource = ["arn:aws:lambda:sa-east-1:456687462806:function:fiap-observability-probe", "arn:aws:lambda:sa-east-1:456687462806:function:fiap-uptime-probe"]
      },
      {
        Effect = "Allow", Action = ["events:PutRule", "events:DescribeRule", "events:DeleteRule", "events:EnableRule", "events:DisableRule", "events:ListTagsForResource", "events:TagResource", "events:UntagResource", "events:PutTargets", "events:ListTargetsByRule", "events:RemoveTargets"], Resource = "arn:aws:events:sa-east-1:456687462806:rule/fiap-uptime-every-five-minutes"
      }
    ]
  })
}
