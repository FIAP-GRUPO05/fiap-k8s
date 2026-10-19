locals {
  runner_install_commands = [
    "python3 -m pip install --quiet boto3",
    "curl -fsSLo /tmp/kubectl https://dl.k8s.io/release/v${aws_eks_cluster.main.version}.0/bin/linux/amd64/kubectl",
    "curl -fsSLo /tmp/kubectl.sha256 https://dl.k8s.io/release/v${aws_eks_cluster.main.version}.0/bin/linux/amd64/kubectl.sha256",
    "echo \"$(cat /tmp/kubectl.sha256) /tmp/kubectl\" | sha256sum --check",
    "install -m 0755 /tmp/kubectl /usr/local/bin/kubectl",
  ]
  runner_network_permissions = [for statement in jsondecode(aws_iam_role_policy.codebuild_deploy.policy).Statement : statement if startswith(statement.Action[0], "ec2:") || statement.Action[0] == "eks:DescribeCluster"]
}

resource "aws_s3_object" "application_deploy_script" {
  bucket = "fiap-tfstate-456687462806"
  key    = "fiap/platform/scripts/deploy_application.py"
  source = "${path.module}/scripts/deploy_application.py"
  etag   = filemd5("${path.module}/scripts/deploy_application.py")
}

resource "aws_s3_object" "platform_bootstrap_script" {
  bucket = "fiap-tfstate-456687462806"
  key    = "fiap/platform/scripts/bootstrap_platform.py"
  source = "${path.module}/scripts/bootstrap_platform.py"
  etag   = filemd5("${path.module}/scripts/bootstrap_platform.py")
}

resource "aws_secretsmanager_secret" "newrelic" {
  name                    = "fiap/shared/newrelic"
  description             = "New Relic credentials synchronized by the infrastructure repository"
  recovery_window_in_days = 7
}

resource "aws_cloudwatch_log_group" "platform_bootstrap" {
  name              = "/aws/codebuild/fiap-platform-bootstrap"
  retention_in_days = 14
}

resource "aws_iam_role" "platform_bootstrap" {
  name               = "fiap-platform-bootstrap"
  assume_role_policy = data.aws_iam_policy_document.codebuild_assume.json
}

resource "aws_iam_role_policy" "platform_bootstrap" {
  name = "fiap-platform-bootstrap"
  role = aws_iam_role.platform_bootstrap.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.runner_network_permissions, [
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.platform_bootstrap.arn}:*" },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = "arn:aws:s3:::fiap-tfstate-456687462806/${aws_s3_object.platform_bootstrap_script.key}" },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.newrelic.arn },
      { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = aws_lambda_function.observability_probe.arn }
    ])
  })
}

resource "aws_eks_access_entry" "platform_bootstrap" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_iam_role.platform_bootstrap.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "platform_bootstrap" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_eks_access_entry.platform_bootstrap.principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope { type = "cluster" }
}

resource "aws_codebuild_project" "platform_bootstrap" {
  name                   = "fiap-platform-bootstrap"
  description            = "Bootstrap namespaces and New Relic inside the private VPC"
  service_role           = aws_iam_role.platform_bootstrap.arn
  build_timeout          = 20
  queued_timeout         = 15
  concurrent_build_limit = 1
  artifacts { type = "NO_ARTIFACTS" }
  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    environment_variable {
      name  = "CLUSTER_VPC_ID"
      value = aws_vpc.main.id
    }
    environment_variable {
      name  = "CLUSTER_REGION"
      value = var.region
    }
    environment_variable {
      name  = "NEW_RELIC_CHART_VERSION"
      value = "8.0.34"
    }
    environment_variable {
      name  = "NEW_RELIC_JAVA_IMAGE"
      value = "newrelic/newrelic-java-init@sha256:d84da0779edd3ce2dad546f16bd7d60471b098a4ab451d2a9df1ab176c262afa"
    }
  }
  source {
    type = "NO_SOURCE"
    buildspec = yamlencode({
      version = "0.2"
      phases = {
        install = { commands = concat(local.runner_install_commands, [
          "curl -fsSLo /tmp/helm-v4.3.1-linux-amd64.tar.gz https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz",
          "curl -fsSLo /tmp/helm-v4.3.1-linux-amd64.tar.gz.sha256sum https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz.sha256sum",
          "cd /tmp && sha256sum --check helm-v4.3.1-linux-amd64.tar.gz.sha256sum && tar -xzf helm-v4.3.1-linux-amd64.tar.gz && install -m 0755 linux-amd64/helm /usr/local/bin/helm"
        ]) }
        pre_build = { commands = ["aws eks update-kubeconfig --name ${aws_eks_cluster.main.name} --region ${var.region}"] }
        build = { commands = [
          "aws s3 cp s3://fiap-tfstate-456687462806/${aws_s3_object.platform_bootstrap_script.key} /tmp/bootstrap_platform.py",
          "python3 /tmp/bootstrap_platform.py"
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
      group_name = aws_cloudwatch_log_group.platform_bootstrap.name
    }
  }
  depends_on = [aws_iam_role_policy.platform_bootstrap, aws_eks_access_policy_association.platform_bootstrap]
}

output "platform_bootstrap_project_name" {
  value = aws_codebuild_project.platform_bootstrap.name
}
