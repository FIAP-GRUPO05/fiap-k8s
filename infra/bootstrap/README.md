# Bootstrap de identidade AWS para o CI/CD

Esta configuração cria o provedor OIDC do GitHub e quatro roles de verificação,
uma por repositório. Cada role aceita somente tokens de PR do repositório
correspondente. As roles não possuem permissões sobre recursos AWS; o primeiro
uso valida apenas o ID da conta via STS.

A conta é fixada em `456687462806` e a região em `sa-east-1`. Os IDs imutáveis
da organização e dos repositórios fazem parte da política de confiança.

## Pré-requisitos

1. Habilitar MFA na conta root. Preferir uma identidade administrativa do time.
   Para o bootstrap inicial, a identidade root pode ser usada somente com o
   parâmetro explícito `-AllowRootBootstrap`; o script confere se o MFA está ativo.
2. Criar o bucket `fiap-tfstate-456687462806` em `sa-east-1`, com versionamento,
   criptografia padrão e bloqueio integral de acesso público, usando o script
   abaixo no diretório `infra/bootstrap`.
3. Usar uma identidade administrativa autenticada na conta `456687462806`.
   Para uma sessão criada por `aws login`, configure um perfil de processo para o
   Terraform, que obtém credenciais temporárias do AWS CLI sem salvar chaves:

```powershell
aws configure set credential_process "aws configure export-credentials --profile <perfil-admin> --format process" --profile fiap-team-terraform
aws configure set region sa-east-1 --profile fiap-team-terraform
aws sts get-caller-identity --profile fiap-team-terraform
```

O ARN acima deve representar a identidade administrativa. Se ela ainda não
estiver disponível, use temporariamente o perfil `fiap-team-terraform`, que
obtém uma sessão curta do login root, somente para este bootstrap inicial.

```powershell
Set-Location infra/bootstrap
./create-state-bucket.ps1 -Profile fiap-team -AllowRootBootstrap
@'
bucket       = "fiap-tfstate-456687462806"
key          = "fiap/bootstrap.tfstate"
region       = "sa-east-1"
profile      = "fiap-team-terraform"
encrypt      = true
use_lockfile = true
'@ | Set-Content backend.local.hcl
terraform init -input=false -backend-config backend.local.hcl
terraform plan -input=false -var aws_profile=fiap-team-terraform -out bootstrap.tfplan
terraform apply -input=false bootstrap.tfplan
```

O `plan` deve ser revisado antes do `apply`. O estado do Terraform fica no S3
com bloqueio por arquivo `.tflock`; nenhum segredo AWS é salvo no repositório.
O arquivo `backend.local.hcl` é ignorado pelo Git.

O deploy real terá roles separadas para homologação e produção, com permissões
específicas para cada serviço. A role de verificação não será ampliada para
fazer deploy, pois também pode ser assumida durante a avaliação de um PR.
