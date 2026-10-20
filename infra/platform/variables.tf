variable "region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type        = string
  description = "Identificador do ambiente: shared, nonprod ou prod."

  validation {
    condition     = contains(["shared", "nonprod", "prod"], var.environment)
    error_message = "Use shared, nonprod ou prod."
  }
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR exclusivo para a VPC deste cluster."
}

variable "cluster_name" {
  type        = string
  description = "Nome exclusivo do EKS."
}

variable "admin_principal_arn" {
  type        = string
  description = "ARN da identidade IAM administradora, nunca da conta root."
}

variable "node_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 4
}
