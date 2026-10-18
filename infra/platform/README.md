# Plataforma AWS compartilhada

Esta raiz gerencia o EKS `fiap-shared` na conta TWM `456687462806`, regiao
`sa-east-1`. O estado fica no S3, com versionamento e bloqueio de escrita.

## Topologia e custo

- Uma VPC, duas zonas e dois nos privados `t3.medium`.
- Um EKS para `develop`, `homol` e `prod`, separados em namespaces.
- Um NAT compartilhado e um endpoint privado de Secrets Manager em uma zona.
- RDS privado em `fiap-database/infra/managed`; imagem em ECR em
  `fiap-application/infra/registry`.
- Somente `prod` solicita um LoadBalancer publico. Os Services de desenvolvimento
  e homologacao ficam internos. Isso evita manter tres balanceadores pagos.

EKS, EC2, NAT, endpoint, RDS, armazenamento e balanceador geram custos enquanto
provisionados. Compartilhar cluster/banco e usar um NAT reduz o custo fixo,
mas tambem compartilha capacidade e reduz a tolerancia a falhas de zona. Os
namespaces nao equivalem ao isolamento de contas ou clusters independentes.

## Aplicacao por CLI

```powershell
$env:AWS_PROFILE = '<perfil-com-permissao-de-infraestrutura>'
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

`shared.auto.tfvars` contem somente identificadores e parametros sem segredos.
Credenciais permanecem nos perfis AWS locais, OIDC ou Secrets Manager.

## Deploy privado e observabilidade

`fiap-platform-bootstrap` cria os namespaces e instala o chart New Relic
`8.0.34`, com metricas, eventos, logs e instrumentacao Java. O agente Java usa
um digest imutavel. Esse executor precisa de administracao do cluster para
instalar CRDs, webhooks e agentes.

`fiap-eks-deploy` recebe `IMAGE_URI` e `DEPLOY_NAMESPACE`, aplica Deployment,
Secret, Service e HPA, aguarda o rollout e verifica `/actuator/health`, incluindo
o banco. Seu acesso Kubernetes esta restrito aos tres namespaces. O Deployment
usa `envFrom.secretRef`; senhas nao sao copiadas para seus campos de ambiente.

Os executores CodeBuild so cobram durante a execucao. Usam a API EKS privada,
sem abrir o endpoint do cluster para runners publicos do GitHub. O workflow
aguarda o resultado do CodeBuild e falha quando o deploy falha.

O repositorio `fiap-k8s` sincroniza os tres secrets `NEW_RELIC_*` existentes no
GitHub para `fiap/shared/newrelic`; nenhum valor precisa passar por maquinas
dos integrantes. A excecao `bootstrap_feature_ref` no bootstrap OIDC deve
permanecer `null` depois da verificacao inicial. E-mail usa `MAIL_TIPE=NONE`
enquanto a integracao real de notificacoes estiver pendente.
