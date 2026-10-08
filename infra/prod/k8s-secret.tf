# O postgres-service e o postgres-secret são criados pelo repositório fiap-database.
resource "kubectl_manifest" "api-secret" {
  depends_on = [kubectl_manifest.namespace]
  yaml_body  = <<YAML
apiVersion: v1
kind: Secret
metadata:
  name: api-secret
  namespace: prod
type: Opaque
stringData:
  SPRING_DATASOURCE_URL: "jdbc:postgresql://postgres-service:5432/${var.postgresDb}"
  SPRING_DATASOURCE_USERNAME: "${var.postgresUser}"
  SPRING_DATASOURCE_PASSWORD: "${var.postgresPassword}"
  MAIL_TIPE: "LAMBDA"
  JWT_SECRET: "${var.jwtSecret}"
  JWT_ISSUER: "${local.jwt_issuer}"
  JWT_AUDIENCE: "${var.jwtAudience}"
  APP_PUBLIC_URL: "${var.appPublicUrl}"
  AWS_ACCESS_KEY_ID: "${var.accessKeyId}"
  AWS_SECRET_ACCESS_KEY : "${var.secretAccessKey}"
  AWS_SESSION_TOKEN : "${var.sessionToken}"
  AWS_REGION : "us-east-1"
YAML
}