terraform {
  required_version = ">= 1.13.0"

  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region              = var.region
  allowed_account_ids = ["456687462806"]

  default_tags {
    tags = {
      Project     = "fiap-tech-challenge-fase-3"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
