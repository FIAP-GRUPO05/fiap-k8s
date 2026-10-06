resource "kubectl_manifest" "api-deployment" {
  depends_on = [aws_eks_cluster.main, aws_eks_addon.metrics_server, kubectl_manifest.api-secret]
  # O banco vem do fiap-database, aplicado depois deste repositório: esperar o
  # rollout aqui travaria o apply até o timeout.
  wait_for_rollout = false
  yaml_body        = <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: prod
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0   # nenhum pod antigo sai antes de um novo estar Ready
  selector:
    matchLabels:
      app: api       
  template:
    metadata:
      labels:
        app: api
      annotations:
        appPublicUrlHash: "${sha1(var.appPublicUrl)}"
        jwtConfigHash: "${sha1("${var.jwtIssuer}|${var.jwtAudience}")}"
        instrumentation.opentelemetry.io/inject-java: "true"
    spec:
      containers:
      - name: api-container
        image: timbeck97/tc-fiap:latest
        ports:
        - containerPort: 8080
        env:
        - name: SPRING_OUTPUT_ANSI_ENABLED
          value: "never"
        envFrom:
        - secretRef:
            name: api-secret
        startupProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          periodSeconds: 5
          failureThreshold: 30   # tolera até 150s de boot
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          periodSeconds: 10
          timeoutSeconds: 3
          failureThreshold: 3
        resources:
          # Base do calculo do HPA: "70% de CPU" significa 70% destas requests.
          requests:
            cpu: "250m"      # 0,25 vCPU
            memory: "348Mi"
          limits:
            cpu: "500m"      # teto de 0,5 vCPU
            memory: "512Mi"
YAML
}