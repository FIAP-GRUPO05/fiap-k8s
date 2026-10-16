# Bootstrap de identidade AWS para o CI/CD

Esta configuração cria o provedor OIDC do GitHub e quatro roles de verificação,
uma por repositório. Cada role aceita somente tokens de PR do repositório
correspondente. As roles não possuem permissões sobre recursos AWS; o primeiro
uso valida apenas o ID da conta via STS.

A conta é fixada em `456687462806` e a região em `sa-east-1`. Os IDs imutáveis
da organização e dos repositórios fazem parte da política de confiança.

## Pré-requisitos

1. Habilitar MFA na conta root e configurar uma identidade administrativa do time.
2. Criar o bucket `fiap-tfstate-456687462806` em `sa-east-1`, com versionamento,
   criptografia padrão e bloqueio integral de acesso público, usando o script
   abaixo no diretório `infra/bootstrap`.
3. Usar uma identidade administrativa autenticada na conta `456687462806`.

```powershell
Set-Location infra/bootstrap
./create-state-bucket.ps1 -Profile fiap-team
Set-Location ../..
terraform -chdir=infra/bootstrap init -input=false -backend-config=bucket=fiap-tfstate-456687462806 -backend-config=key=fiap/bootstrap.tfstate -backend-config=region=sa-east-1 -backend-config=encrypt=true -backend-config=use_lockfile=true
terraform -chdir=infra/bootstrap plan -input=false
terraform -chdir=infra/bootstrap apply -input=false
```

O `plan` deve ser revisado antes do `apply`. O estado do Terraform fica no S3
com bloqueio por arquivo `.tflock`; nenhum segredo AWS é salvo no repositório.

O deploy real terá roles separadas para homologação e produção, com permissões
específicas para cada serviço. A role de verificação não será ampliada para
fazer deploy, pois também pode ser assumida durante a avaliação de um PR.
