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
variable "mailHost" {
  type        = string
  default     = "smtp.gmail.com"
  description = "Host SMTP usado para as notificações por e-mail"
}
variable "mailPort" {
  type        = number
  default     = 587
  description = "Porta SMTP. 587 = STARTTLS (a porta 25 é bloqueada na saída da AWS)"
}
variable "mailUsername" {
  type        = string
  description = "Conta que autentica no SMTP. No Gmail, o endereço completo (ex: oficina@gmail.com)"
}
variable "mailPassword" {
  type        = string
  sensitive   = true
  description = "Senha SMTP. No Gmail, a App Password de 16 caracteres (exige verificação em duas etapas)"
}
variable "notificationsEmailFrom" {
  type        = string
  default     = ""
  description = "Remetente dos e-mails. Vazio usa o mailUsername, que é o que o Gmail exige; preencha apenas para um alias verificado na conta"
}

variable "appPublicUrl" {
  type        = string
  default     = ""
}
