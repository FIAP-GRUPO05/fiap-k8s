data "aws_iam_policy_document" "codebuild_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["codebuild.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codebuild_deploy" {
  name               = "fiap-eks-deploy-runner"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume.json
}

resource "aws_iam_role_policy" "codebuild_deploy" {
  name = "fiap-eks-deploy-runner"
  role = aws_iam_role.codebuild_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${var.region}:456687462806:log-group:/aws/codebuild/fiap-eks-deploy",
          "arn:aws:logs:${var.region}:456687462806:log-group:/aws/codebuild/fiap-eks-deploy:*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::fiap-tfstate-456687462806/${aws_s3_object.application_deploy_script.key}"
      },
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.observability_probe.arn
      },
      {
        Effect   = "Allow"
        Action   = ["eks:DescribeCluster"]
        Resource = aws_eks_cluster.main.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface",
          "ec2:DescribeDhcpOptions", "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSubnets", "ec2:DescribeSecurityGroups", "ec2:DescribeVpcs"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["ec2:CreateNetworkInterfacePermission"]
        Resource = "arn:aws:ec2:${var.region}:456687462806:network-interface/*"
        Condition = {
          StringEquals = { "ec2:AuthorizedService" = "codebuild.amazonaws.com" }
          ArnEquals    = { "ec2:Subnet" = [for id in aws_subnet.private[*].id : "arn:aws:ec2:${var.region}:456687462806:subnet/${id}"] }
        }
      },
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          "arn:aws:secretsmanager:${var.region}:456687462806:secret:fiap/*/postgres-*",
          "arn:aws:secretsmanager:${var.region}:456687462806:secret:fiap/*/application-*"
        ]
      }
    ]
  })
}

resource "aws_security_group" "codebuild_deploy" {
  name        = "fiap-eks-deploy-runner"
  description = "HTTPS from the in-VPC deploy runner to EKS and AWS APIs"
  vpc_id      = aws_vpc.main.id
}

# HTTPS through the shared NAT is required for AWS APIs and tool downloads.
#trivy:ignore:AWS-0104
resource "aws_vpc_security_group_egress_rule" "codebuild_deploy_https" {
  security_group_id = aws_security_group.codebuild_deploy.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "AWS APIs, ECR, and tool downloads through the NAT gateway"
}

resource "aws_vpc_security_group_ingress_rule" "eks_from_codebuild" {
  security_group_id            = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
  referenced_security_group_id = aws_security_group.codebuild_deploy.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Private Kubernetes API access from deploy runner"
}

resource "aws_vpc_security_group_ingress_rule" "secrets_manager_from_deploy_runner" {
  security_group_id            = aws_security_group.secrets_manager_endpoint.id
  referenced_security_group_id = aws_security_group.codebuild_deploy.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Private Secrets Manager access from deploy CodeBuild"
}

resource "aws_eks_access_entry" "codebuild_deploy" {
  cluster_name      = aws_eks_cluster.main.name
  principal_arn     = aws_iam_role.codebuild_deploy.arn
  type              = "STANDARD"
  kubernetes_groups = []
}

resource "aws_eks_access_policy_association" "codebuild_deploy" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_iam_role.codebuild_deploy.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"
  access_scope {
    type       = "namespace"
    namespaces = ["develop", "homol", "prod"]
  }

  depends_on = [aws_eks_access_entry.codebuild_deploy]
}

resource "aws_cloudwatch_log_group" "codebuild_deploy" {
  name              = "/aws/codebuild/fiap-eks-deploy"
  retention_in_days = 14
}

resource "aws_codebuild_project" "eks_deploy" {
  name         = "fiap-eks-deploy"
  description  = "Apply an image already built in ECR to one FIAP environment namespace"
  service_role = aws_iam_role.codebuild_deploy.arn

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    environment_variable {
      name  = "VPC_CIDR"
      value = var.vpc_cidr
    }
  }

  source {
    type = "NO_SOURCE"
    buildspec = yamlencode({
      version = "0.2"
      phases = {
        install = { commands = local.runner_install_commands }
        pre_build = { commands = [
          "aws eks update-kubeconfig --name ${aws_eks_cluster.main.name} --region ${var.region}"
        ] }
        build = { commands = [
          "aws s3 cp s3://fiap-tfstate-456687462806/${aws_s3_object.application_deploy_script.key} /tmp/deploy_application.py",
          "python3 /tmp/deploy_application.py"
        ] }
      }
    })
  }

  vpc_config {
    vpc_id             = aws_vpc.main.id
    subnets            = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.codebuild_deploy.id]
  }

  logs_config {
    cloudwatch_logs {
      status     = "ENABLED"
      group_name = aws_cloudwatch_log_group.codebuild_deploy.name
    }
  }

  concurrent_build_limit = 1
  build_timeout          = 15
  queued_timeout         = 15
  tags                   = { Name = "fiap-eks-deploy" }
}

output "eks_deploy_project_name" {
  value = aws_codebuild_project.eks_deploy.name
}

output "eks_deploy_role_arn" {
  value = aws_iam_role.codebuild_deploy.arn
}
