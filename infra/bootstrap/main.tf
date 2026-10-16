terraform {
  required_version = ">= 1.13.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region              = "sa-east-1"
  allowed_account_ids = ["456687462806"]

  default_tags {
    tags = {
      Project   = "fiap-tech-challenge-fase-3"
      ManagedBy = "terraform"
    }
  }
}

locals {
  github_organization = "FIAP-GRUPO05"
  github_owner_id     = "338354925"
  repositories = {
    fiap-application = "1378462765"
    fiap-lambda      = "1378444263"
    fiap-k8s         = "1378460324"
    fiap-database    = "1378461621"
  }
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

# Esta role serve somente para conferir a identidade da conta no CI.
# Sem policy anexada, ela nao consegue ler ou alterar recursos do projeto.
resource "aws_iam_role" "github_preflight" {
  for_each = local.repositories

  name = "fiap-gh-preflight-${each.key}"
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
          "token.actions.githubusercontent.com:sub" = "repo:${local.github_organization}@${local.github_owner_id}/${each.key}@${each.value}:pull_request"
        }
      }
    }]
  })
}

