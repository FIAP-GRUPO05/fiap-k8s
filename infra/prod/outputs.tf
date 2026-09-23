# Hostname do Load Balancer que expoe a API. E o valor que alimenta a variavel
# appPublicUrl: rode o apply, copie daqui para o terraform.tfvars e aplique de novo
# para que os links do e-mail passem a apontar para producao.
data "kubernetes_service" "api" {
  depends_on = [kubectl_manifest.api-service]

  metadata {
    name      = "api-service"
    namespace = "prod"
  }
}

output "api_load_balancer_hostname" {
  value       = try(data.kubernetes_service.api.status[0].load_balancer[0].ingress[0].hostname, "")
  description = "Hostname do ELB. Vazio logo apos o primeiro apply: o provisionamento leva alguns minutos."
}

output "api_public_url" {
  value = try(
    "http://${data.kubernetes_service.api.status[0].load_balancer[0].ingress[0].hostname}:8080",
    ""
  )
  description = "Valor pronto para colar em appPublicUrl no terraform.tfvars."
}
