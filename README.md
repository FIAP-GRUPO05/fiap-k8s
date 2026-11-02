# fiap-k8s

Plataforma AWS/Kubernetes do projeto: rede privada, EKS, executores de deploy, identidades IAM, observabilidade e operações de reconstrução/desmontagem.

📚 **[Documentação principal — fiap-docs](https://github.com/FIAP-GRUPO05/fiap-docs)**

## Tecnologias e requisitos

Terraform 1.13+, Python 3.12, AWS CLI, GitHub CLI, Trivy no PATH (ou `--trivy <caminho>`), Docker, Amazon EKS, CodeBuild, ECR e New Relic. O provisionamento é na conta `456687462806`, região São Paulo (`sa-east-1`). O operador de bootstrap precisa de identidade AWS administrativa autenticada; integrantes não precisam compartilhar credenciais para executar a CI.

## Arquitetura deste componente

![Arquitetura do fiap-k8s](docs/arquitetura.png)

Fonte editável: [`docs/arquitetura.mmd`](docs/arquitetura.mmd).

O node group `fiap-shared-nodes` tem 2 nós `t3.medium` fixos (`min_size = desired_size = 2`; `max_size = 4` é só teto, sem Cluster Autoscaler instalado), por decisão de custo registrada na [ADR#0009](https://github.com/FIAP-GRUPO05/fiap-docs/blob/main/adr/ADR%230009.md). A escala automática é feita pelo HPA de cada namespace: `prod` de 2 a 4 réplicas e `develop`/`homol` de 1 a 2, com alvo de 70% de CPU.

> **Legado:** `infra/prod/` (AWS Academy, `us-east-1`) e `k8s/` (manifestos com a imagem `timbeck97/tc-fiap:latest`) são do laboratório anterior, não são usados pelo pipeline e **não devem ser aplicados**. Ficam apenas como referência.

## Validar localmente

Na raiz deste repositório:

```powershell
terraform -chdir=infra/bootstrap init -backend=false -input=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/platform init -backend=false -input=false
terraform -chdir=infra/platform validate
python -m unittest discover -s .github/scripts -p 'test_*.py' -v
```

A validação não cria recursos. As raízes ativas são `infra/bootstrap`, `infra/platform` e `infra/observability`.

## Deploy e ambientes

O fluxo é `feature/* → develop → release/vX.Y.Z → prod → main`. Após o push da feature e o sucesso da CI, o PR é aberto automaticamente; os merges são manuais. Os próximos PRs são gerados após a promoção aprovada.

| Branch | Ambiente | O que o pipeline deste repositório faz |
|---|---|---|
| `feature/*` | — | Valida e abre PR para `develop` |
| `develop` | namespace `develop` | Aplica `infra/observability` |
| `release/vX.Y.Z` | namespace `homol` (homologação) | Aplica `infra/observability` |
| `prod` | namespace `prod` (produção) | Aplica `infra/platform` (EKS, rede, executores) e depois `infra/observability` |
| `main` | — | Só consolida a versão; sem deploy |

O deploy da API em cada namespace é feito pelo `fiap-application`, pelo CodeBuild desta plataforma.

O modo vem da variável de repositório `FIAP_INFRA_STATE`, conferida também no controle S3 `fiap/operations/state.json` antes de qualquer escrita na AWS:

- `active`: esteira completa; deploys e aplicações de Terraform liberados.
- `maintenance`: valida código e abre os PRs de promoção, mas bloqueia deploys. Não desliga recursos nem interrompe cobranças AWS.
- `destroying`/`destroyed`: deploys e promoções bloqueados.

Para colocar em manutenção, `python tools/configure_destroy.py --freeze-only --apply` grava `maintenance` na variável dos quatro repositórios. Para voltar a `active`, `python tools/restore_infra.py --stage activate --execute --sender ... --test-recipient ...` roda os regressivos reais antes de atualizar a variável e o controle S3. O bootstrap administrativo usa AWS CLI; a operação diária do CI usa OIDC e não exige credenciais AWS de cada integrante.

O primeiro provisionamento é administrativo e respeita a dependência plataforma → banco → Lambda/Gateway → aplicação. Depois disso, o workflow aplica a plataforma em `prod` e configura New Relic. A publicação da aplicação usa CodeBuild, pois o endpoint Kubernetes é privado.

## Provisionamento manual

Sem o script, a ordem é `infra/bootstrap` → `infra/platform` → `infra/observability`; banco, Lambda/Gateway e aplicação vêm depois, nos respectivos repositórios. O bucket `fiap-tfstate-456687462806` precisa existir (`infra/bootstrap/create-state-bucket.ps1` ou `restore_infra.py --stage prepare`). Cada raiz tem seu `backend.hcl`.

```bash
export AWS_PROFILE=twm-admin-terraform

# 1. IAM/OIDC do GitHub (somente administrativo; aws_profile é opcional)
terraform -chdir=infra/bootstrap init -backend-config=backend.hcl -input=false
terraform -chdir=infra/bootstrap plan -input=false -out=bootstrap.tfplan
terraform -chdir=infra/bootstrap apply -input=false bootstrap.tfplan

# 2. VPC, EKS e executores (shared.auto.tfvars já é carregado). Sem -var=api_endpoints='{"develop":...,"homol":...,"prod":...}'
#    (URLs de FIAP_RUNTIME_CONFIG), o agendamento do uptime fica desabilitado.
terraform -chdir=infra/platform init -backend-config=backend.hcl -input=false
terraform -chdir=infra/platform plan -input=false -out=platform.tfplan
terraform -chdir=infra/platform apply -input=false platform.tfplan
aws codebuild start-build --project-name fiap-platform-bootstrap  # namespaces, LB Controller e nri-bundle

# 3. Dashboards e alertas New Relic (credenciais do Secrets Manager)
secret=$(aws secretsmanager get-secret-value --secret-id fiap/shared/newrelic --query SecretString --output text)
export TF_VAR_account_id=$(python -c 'import json,sys; print(json.loads(sys.argv[1])["account_id"])' "$secret")
export TF_VAR_api_key=$(python -c 'import json,sys; print(json.loads(sys.argv[1])["api_key"])' "$secret")
terraform -chdir=infra/observability init -backend-config=backend.hcl -input=false
terraform -chdir=infra/observability plan -input=false -out=observability.tfplan
terraform -chdir=infra/observability apply -input=false observability.tfplan
```

Revise cada `plan` antes do `apply`. `tools/restore_infra.py` automatiza essa sequência entre os quatro repositórios (`prepare`, `bootstrap`, `platform`, `observability`, `database`, `lambda`, `application`, `gateway`, `sync`, `validate`), importa recursos preservados, reconcilia o New Relic para evitar duplicação e recusa planos com exclusões/substituições; por isso é o caminho preferido para reconstruir.

## Reconstruir após destroy

A reconstrução foi validada em 28/10/2026. Para conferir a sessão, sem alterar a conta:

```powershell
aws login --profile twm-admin
python tools/restore_infra.py --stage status --profile twm-admin-terraform
```

O perfil `twm-admin-terraform` deve usar `credential_process` para exportar a sessão temporária do `twm-admin`. Após uma desmontagem, com os quatro repositórios lado a lado, configure um remetente SES e um destinatário de teste autorizados:

```powershell
python tools/restore_infra.py --stage all --execute --sender 'remetente@dominio.com' --test-recipient 'teste@dominio.com'
```

O script para se o remetente SES ainda não estiver verificado, importa IAM/OIDC preservados, reconcilia dashboards e alertas existentes do New Relic para evitar duplicação, restaura segredos ainda recuperáveis, recusa planos com exclusões/substituições e deixa a CI em `maintenance` até a ativação. A reconstrução exige reconciliação dos estados anteriores; mensagens de falha devem ser resolvidas antes de retomar a etapa. Consulte `--help` para executar uma etapa individual. O script não substitui a revisão dos planos e só altera recursos com `--execute`.

Não repita `--stage all` sobre a instalação já reconstruída: confira o estado e retome somente a etapa pendente. O bootstrap inicial desabilita temporariamente o proxy do backend, que já está habilitado na instalação concluída.

Depois de reconstruir, ele atualiza `FIAP_RUNTIME_CONFIG` e os endpoints do monitor de uptime. A ativação é uma etapa explícita: `--stage activate --execute`, com os mesmos remetente/destinatário, após os regressivos reais. Para desligar, use `feature/destroy-infra-aws` → `ALL`, com as aprovações exigidas; o relatório inclui as Lambdas de e-mail e distingue recursos removidos dos retidos.

## APIs e observabilidade

Este componente não tem Swagger próprio. Consulte o [Swagger e as URLs da aplicação](https://github.com/FIAP-GRUPO05/fiap-application#api-e-urls-dos-ambientes). Os dashboards New Relic são obtidos em `terraform -chdir=infra/observability output dashboard_urls` após provisionamento/reconciliação do respectivo state. Os alertas não têm notification destination nem workflow configurados: os incidentes ficam apenas em **Alerts > Issues** no New Relic. Regressivos reais verificam saúde, APM, eventos de OS, logs correlacionados e uptime; com a AWS desligada, esses checks ficam pendentes e não representam aprovação do deploy.

## Membros da equipe

<table>
  <tr>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/wesslima/" title="Wesley Lima">
        <img src="https://media.licdn.com/dms/image/v2/D4D03AQG__sMSpl_SEg/profile-displayphoto-scale_400_400/B4DaEHvVltHsAg-/0/1791131212617?e=1794441600&amp;v=beta&amp;t=VPPE-aIk2CNR6rhd3yPIdsPjOuVyl7gdsCxP6AlAlpg" width="100" height="100" alt="Foto de Wesley Lima"><br>
        <sub><b>Wesley Lima</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/tim-morgenstern-4581911b1/" title="Tim Morgenstern">
        <img src="https://media.licdn.com/dms/image/v2/C4E03AQG57Du9tsCS5A/profile-displayphoto-shrink_400_400/profile-displayphoto-shrink_400_400/0/1643980434981?e=1794441600&amp;v=beta&amp;t=6fVFPP0UXkaUU6K77-XJ3fPtGR2YvE1KRoRn9ze-Vog" width="100" height="100" alt="Foto de Tim Morgenstern"><br>
        <sub><b>Tim Morgenstern</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
    <td align="center" width="160">
      <a href="https://www.linkedin.com/in/matheus-pitas-baptista/" title="Matheus Pitas Baptista">
        <img src="https://media.licdn.com/dms/image/v2/D4D03AQHFS4VJk5WteA/profile-displayphoto-scale_400_400/B4DZv_LwbmHYAg-/0/1769512832179?e=1794441600&amp;v=beta&amp;t=gaI3wzS0F5BnXd5z0V9sS90uFcyxOLiK0vgWPnzMOJg" width="100" height="100" alt="Foto de Matheus Pitas Baptista"><br>
        <sub><b>Matheus Pitas Baptista</b></sub>
      </a><br><sub>Backend Engineer</sub>
    </td>
  </tr>
</table>
