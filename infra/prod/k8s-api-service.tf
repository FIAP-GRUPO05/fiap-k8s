resource "kubectl_manifest" "api-service" {
  depends_on = [kubectl_manifest.api-deployment]
  yaml_body  = <<YAML
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: prod
  annotations:
    # Torna o Load Balancer acessível pela internet
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
    # Anexa o seu Security Group customizado ao Load Balancer
    service.beta.kubernetes.io/aws-load-balancer-extra-security-groups: "${aws_security_group.sg.id}"
spec:
  selector:
    app: api
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 8080
  type: LoadBalancer

YAML
}