# Dashboards e alertas New Relic

Esta raiz reutiliza os paineis e o alerta de falhas em ordens de servico,
separados por ambiente. O estado fica em `fiap/observability.tfstate`.
O workflow `fiap-k8s` aplica os recursos usando os secrets centralizados.

As chaves sao parametros sensiveis do provider e nao devem ser gravadas em
tfvars. O executor local pode carregar `TF_VAR_account_id` e `TF_VAR_api_key`
diretamente do Secrets Manager sem imprimir seus valores.

O indicador de disponibilidade usa amostras reais de prontidao dos pods.
Ele nao mede disponibilidade externa ponta a ponta. Monitores Synthetics pagos
nao sao criados nesta topologia de menor custo. Os dashboards sao privados na
conta New Relic. Alertas abrem incidentes, sem enviar mensagens a terceiros.

## Monitor HTTPS

`fiap-uptime-probe` roda a cada cinco minutos via EventBridge, fora da VPC,
e verifica health e JWKS das tres URLs publicas do API Gateway. Envia somente
status, ambiente e duracao ao New Relic como `FiapUptimeCheck`. A chave de ingestao
e carregada do Secrets Manager em memoria. Os dashboards incluem disponibilidade
HTTPS e tempo da verificacao; alertas detectam falhas e 15 minutos sem sinal.
O monitor nao substitui a regressao autenticada de negocio executada no deploy.
