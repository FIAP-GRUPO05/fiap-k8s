terraform {
  required_version = ">= 1.13.0"
  required_providers {
    newrelic = { source = "newrelic/newrelic", version = "~> 3.0" }
  }
  backend "s3" {}
}

variable "account_id" { type = number }
variable "api_key" {
  type      = string
  sensitive = true
}
variable "region" {
  type    = string
  default = "US"
}

provider "newrelic" {
  account_id = var.account_id
  api_key    = var.api_key
  region     = var.region
}

module "environment" {
  for_each     = toset(["develop", "homol", "prod"])
  source       = "./modules/environment"
  environment  = each.key
  cluster_name = "fiap-shared"
}

output "dashboard_urls" {
  value = { for name, environment in module.environment : name => environment.newrelic_dashboard_url }
}
