variable "projectName" {
  type        = string
  default     = "TC-FIAP"
  description = "Nome do projeto"
}
variable "region" {
  type        = string
  default     = "us-east-1"
  description = "Região onde os recursos serão criados"
}
variable "accessConfig" {
  type        = string
  default     = "API"
  description = "Access config"
}
variable "postgresDb" {
  type        = string
  default     = "oficina_db"
  description = "Nome do banco de dados"
}
variable "postgresUser" {
  type        = string
  default     = "oficina"
  description = "Usuário do banco de dados"
}
variable "postgresPassword" {
  type        = string
  sensitive   = true
  description = "Senha do banco de dados"
}
variable "jwtSecret" {
  type        = string
  sensitive   = true
  description = "Chave de assinatura do JWT (mínimo 256 bits)"
}
variable "jwtIssuer" {
  type        = string
  default     = ""
  description = "Issuer dos tokens RS256. Vazio usa o bucket de JWKS do fiap-lambda (fiap-jwt-jwks-<conta>), calculado em data.tf"
}
variable "jwtAudience" {
  type        = string
  default     = "fiap-api"
  description = "Claim aud exigida nos tokens RS256 (mesmo jwt_audience do fiap-lambda)"
}
variable "clusterName" {
  type        = string
  default     = "my-cluster"
  description = "Nome do cluster EKS"
}
variable "logRetentionDays" {
  type        = number
  default     = 7
  description = "Retenção dos log groups do cluster. Sem isso o padrão do CloudWatch é nunca expirar"
}
variable "clusterLogTypes" {
  type        = list(string)
  default     = ["api", "audit", "authenticator"]
  description = "Logs do control plane. controllerManager e scheduler ficam de fora por serem os mais verbosos"
}

variable "appPublicUrl" {
  type        = string
  default     = ""
  description = "Base dos links dos e-mails. No CI, o segundo apply passa o output api_public_url"
}
variable "accessKeyId" {
  type        = string
  sensitive   = true
  description = "Credencial do Learner Lab que a API usa para invocar a lambda-email"
}
variable "secretAccessKey" {
  type      = string
  sensitive = true
}
variable "sessionToken" {
  type      = string
  sensitive = true
}

variable "newrelic_license_key" {
  type        = string
  sensitive   = true
  description = "License key (ingest) da conta New Relic usada pelo nri-bundle"
}

variable "newrelic_account_id" {
  type        = number
  description = "ID da conta New Relic onde o dashboard é criado"
}

variable "newrelic_api_key" {
  type        = string
  sensitive   = true
  description = "User API key (NRAK-...) usada pelo provider newrelic para criar o dashboard"
}

variable "newrelic_region" {
  type        = string
  default     = "US"
  description = "Região da conta New Relic (US ou EU)"
}
