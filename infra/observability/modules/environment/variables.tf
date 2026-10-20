terraform {
  required_providers {
    newrelic = { source = "newrelic/newrelic", version = "~> 3.0" }
  }
}
variable "environment" { type = string }
variable "cluster_name" { type = string }
