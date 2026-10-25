# Desmontagem AWS por PR para ALL

## Estado da implementação

O código adiciona uma operação administrativa ao mesmo `pipeline.yml`. A ativação requer instalar o código revisado, configurar um GitHub App exclusivo, o environment `aws-destroy`, regras de ALL e roles OIDC. Não executar exclusões para testar a instalação.

O nome é **exatamente `feature/destroy-infra-aws`**, no repositório **fiap-k8s**. O destino do PR é a branch **ALL**, em maiúsculas. Essa operação afeta a infraestrutura compartilhada dos quatro projetos e dos três ambientes.

### Instalação e auditoria observadas em 22/10/2026

| Componente | Situação conferida |
|---|---|
| Branch ALL | Criada a partir da main, com dois reviews obrigatórios e sem bypass |
| Environment aws-destroy | Restrito à branch ALL; variável do Client ID e nome do secret presentes |
| App fiap-operacoes-infra | Instalação limitada aos quatro repositórios; exceção nas 16 regras das branches normais |
| Guards de publicação | Conferidos em develop, release ativa, prod e main dos quatro projetos |
| Bootstrap IAM | Aplicado: duas roles novas, três políticas da operação e dez políticas de leitura do controle S3 |
| Estado dos quatro projetos | maintenance; publicação de infraestrutura bloqueada |
| Auditoria real pelo runner | Autenticação OIDC e consulta ao Cost Explorer funcionaram |
| Exclusão real | Não executada; continua exigindo pedido, aprovações e merge em ALL |

O apply administrativo registrou **15 adições, zero alterações e zero exclusões**.
As roles instaladas são `fiap-gh-plan-destroy` e `fiap-gh-destroy-infra`; seus documentos foram comparados com o plano revisado.
O CI/CD utiliza credenciais temporárias OIDC, sem depender de códigos de MFA de um integrante.
O bootstrap local foi concluído com a sessão root existente, por decisão expressa do responsável de manter o MFA inalterado;
essa exceção de instalação não concede acesso root aos runners.

A [auditoria de 22/10](https://github.com/FIAP-GRUPO05/fiap-k8s/actions/runs/39731760026)
encontrou 43 recursos remanescentes e gerou o relatório mesmo com resultado de falha.
Além dos recursos ainda existentes, o código anterior classificou incorretamente os 13 segredos já inventariados como recursos desconhecidos.
A correção associa o serviço Secrets Manager ao tipo `secret`, mantendo a conferência do ARN efetivamente inventariado,
da tag do projeto e do prefixo `fiap/`. Segredos com exclusão agendada continuam separados dos recursos em operação.
Recursos desconhecidos ou sem comprovação de pertencimento ao projeto continuam bloqueando o destroy.

As regressões locais cobrem segredos ativos, exclusão agendada, ausência na listagem, tag ou prefixo incorretos e identificação em outro serviço.
A correção precisa chegar à main pelo fluxo normal antes de repetir a auditoria manual confiável.
Mesmo depois desse ajuste, uma auditoria com recursos remanescentes deve continuar retornando falha: ela não representa uma confirmação de infraestrutura desligada.

## Execução real de 25/10/2026 UTC

O [PR #32](https://github.com/FIAP-GRUPO05/fiap-k8s/pull/32) recebeu as aprovações de `timbeck97` e `matpitas` no commit do pedido.
O solicitante habilitou auto-merge; o check inicial de aprovações foi reexecutado após os reviews para substituir o resultado anterior de falta de aprovação.
As regras obrigatórias foram mantidas. O merge em ALL disparou a [execução 40148447028](https://github.com/FIAP-GRUPO05/fiap-k8s/actions/runs/40148447028).

| Conferência | Resultado registrado |
|---|---|
| Sincronização | 16 branches nos quatro projetos, na ordem develop → release ativa → prod → main |
| Operações registradas | 72 ações concluídas, incluindo exclusão do bucket de estado por último |
| Recursos ativos restantes no inventário | 0 |
| Exclusões agendadas | 13 segredos e uma chave KMS, com janela de sete dias |
| Identidades preservadas | IAM, OIDC e chaves gerenciadas pela AWS |
| Resultado original do workflow | Falha de auditoria: 13 referências de regras de segurança ainda retornadas na consulta de tags |

A auditoria independente confirmou os mesmos resultados e publicou os artefatos, sem registrar erro nas operações de exclusão.
O resultado vermelho não deve ser convertido em sucesso apenas pela ausência de VPC: cada referência de regra precisa de uma consulta direta ao EC2.
A correção consulta `DescribeSecurityGroupRules` pelo ID e só classifica a referência como ausente quando o EC2 confirma a ausência.
Regra existente, erro de permissão ou ID malformado continuam bloqueando a auditoria.
O código `InvalidSecurityGroupRuleId.NotFound` significa regra inexistente na [referência oficial do EC2](https://docs.aws.amazon.com/ec2/latest/devguide/errors-overview.html).

O snapshot financeiro independente registrou consumo estimado de USD 31,1124656281 e créditos de USD -31,1124673418, com líquido aproximadamente zero.
Esses valores são históricos, sujeitos ao atraso do faturamento, e não representam ausência de consumo nem garantia de custo futuro zero.
Não repetir o destroy para tratar referências de tags: promover a correção e executar somente `destroy-audit` pela main.

## Fluxo

```text
feature/destroy-infra-aws
    → PR automático para ALL, alterando apenas o arquivo de pedido
    → validação do pedido + inventário/plano somente de leitura
    → aprovação dos dois integrantes diferentes do solicitante
    → merge em ALL
    → congelar publicações e aguardar/cancelar jobs em andamento
    → sincronizar develop nos quatro repositórios
    → sincronizar a release ativa, depois prod e por último main
    → excluir infraestrutura e dados do projeto
    → auditar novamente e publicar relatório com links e ícones
```

As releases antigas são histórico e não são atualizadas. A release ativa é escolhida no momento do pedido e fica explícita no JSON aprovado. Conflitos, avanço de branches ou recursos novos não aprovados interrompem a operação. Não há force push.

## Aprovações

| Solicitante | Aprovações exigidas |
|---|---|
| codewesleylima | timbeck97 e matpitas |
| timbeck97 | codewesleylima e matpitas |
| matpitas | codewesleylima e timbeck97 |

O PR pode ser criado pelo App, mas o solicitante real é conferido no evento push autenticado do GitHub. As aprovações devem se referir ao SHA atual. Aprovação antiga, retirada ou substituída por solicitação de alterações não autoriza a execução. ALL não recebe bypass do App operacional.

## Instalação administrativa, uma vez

Antes dos merges de instalação, o administrador configura `FIAP_INFRA_STATE=maintenance` nos quatro repositórios usando `python tools/configure_destroy.py --freeze-only --apply`. Esse modo não exige App novo e não remove recursos. Os workflows novos validam codigo e abrem os PRs das proximas etapas em maintenance, sem publicar infraestrutura. Workflows antigos ainda sem guard não devem ser usados para deploy nessa transição.

1. Criar um GitHub App **exclusivo de operações**, instalado somente nos quatro repositórios. Permissões de repositório: Contents (write), Workflows (write), Actions (write), Variables (write), Pull requests (read) e Metadata (read). Webhooks desativados. Não ampliar o App de promoção existente: sua chave é usada fora da operação protegida.
2. Guardar o Client ID, o App ID numérico e o PEM localmente. Não colocar PEM, tokens ou chaves no Git ou na descrição do PR.
3. Revisar `tools/configure_destroy.py`. Sem `--apply`, ele prepara o ruleset local. Com `--apply`, cria ALL a partir de main se ainda não existir, configura o environment restrito a ALL, exige dois reviews e os checks operacionais, inicializa o estado como `maintenance` e permite ao App exclusivo sincronizar somente as branches normais protegidas. Essa exceção é administrativa e precisa ser revisada; não é concedida ao App comum de promoção.
4. Instalar o PEM no secret `FIAP_OPERATIONS_APP_PRIVATE_KEY` **do environment aws-destroy**, e o Client ID na variável `FIAP_OPERATIONS_APP_CLIENT_ID` desse environment. Usar arquivo/stdin em `gh secret set`; não passar o conteúdo em argumentos ou pelo chat.
5. Aplicar o Terraform revisado de `infra/bootstrap`, com perfil administrativo da conta TWM e state bootstrap correto. Isso cria `fiap-gh-plan-destroy` e `fiap-gh-destroy-infra`, sem AdministratorAccess. O subject usa IDs imutáveis do repositório; a role destrutiva exige o contexto de environment. As roles de publicação recebem somente leitura do controle central S3.
6. Instalar os guards nos quatro repositórios. Como a infraestrutura já foi desmontada parcialmente, a instalação é feita em manutenção, sem recriar EKS/RDS ou depender de telemetria inexistente. Em maintenance, deploys ficam bloqueados e os PRs de promocao de codigo sao abertos apos Verify passar; as revisoes sao recomendadas e os merges continuam manuais.
7. Conferir que o código operacional confiável está em main antes de criar ALL. O configurador recusa a criação de ALL se main ainda não contém o script. Durante a instalacao inicial, os merges em develop, release e prod abrem o PR seguinte automaticamente em maintenance, apos as validacoes de codigo. Os merges sao manuais e nao publicam infraestrutura; o PR de prod para main executa somente Route. Depois disso, aplicar a configuração de ALL e conferir o código nos dois destinos antes do primeiro pedido.

O pedido e a execução verificam o hash do guard e sua presença nos workflows de develop, release ativa, prod e main dos quatro repositórios. Instalação parcial é recusada, pois workflows antigos poderiam ignorar o bloqueio e recriar recursos durante a desmontagem.
8. Habilitar Cost Explorer pelo console de Billing. Para detalhamento por recurso, habilitar os dados granulares aplicáveis e/ou manter um relatório de custos com IDs de recursos. Os dados têm atraso e a cobertura histórica é limitada. A ausência dessa configuração não será interpretada como custo zero.

As permissões de escrita de rede da role operacional são regionais; o script restringe a conta, a VPC e os recursos do projeto pelo inventário aprovado. Revisar os ARNs e relações antes de aplicar. A role não possui permissão para alterar IAM, assumir outras roles ou ampliar suas próprias políticas.

## Preparar um pedido depois da instalação

Não basta criar uma branch sem commits: o GitHub precisa de diferença para abrir um PR. O arquivo de pedido registra IDs, política de dados e os SHAs dos quatro projetos.

```powershell
git fetch origin
git switch -c feature/destroy-infra-aws origin/ALL
$env:GH_TOKEN = gh auth token
python .github/scripts/destroy_ops.py prepare
Remove-Item Env:GH_TOKEN
git add .github/operations/destroy-request.json
git commit -m "feat(ops): solicitar desmontagem da infraestrutura AWS"
git push -u origin feature/destroy-infra-aws
```

O token acima é consumido localmente para consultas; não imprimir seu valor. Em pedidos posteriores, atualizar a branch operacional a partir de ALL sem reescrever histórico e criar um novo pedido com UUID e snapshots atuais.

O JSON deve conter `confirmation=DESTRUIR-456687462806` e `delete_project_data=true`. Os dois revisores aprovam a exclusão de recursos e dados: banco, snapshots, imagens, logs e versões do bucket de estado entram no escopo. Segredos são marcados para exclusão com janela de sete dias e KMS é agendada com janela de sete dias, ficando fora de operação. Durante esses estados a AWS não cobra retenção do segredo nem armazenamento da chave; cancelar o agendamento pode restabelecer cobrança. IAM/OIDC são preservados e não têm tarifa direta de provisionamento.

## Prevenção de recriação

`FIAP_INFRA_STATE` é colocado em `destroying` nos quatro repositórios. O controle S3 `fiap/operations/state.json` é consultado imediatamente antes de operações de publicação/apply. A execução aguarda/cancela outros runners e CodeBuilds antes da sincronização. A concorrência de um único repositório não seria suficiente para os quatro projetos.

Depois da conclusão, o estado permanece `destroyed`. O bucket é removido por último; ausência do backend faz o guard falhar fechado. Recriar a infraestrutura exige um procedimento administrativo separado, com revisão de código, configuração e política de dados; não basta trocar uma variável para active.

## Desmontagem real

A ferramenta trata recursos ausentes de forma idempotente e não chama simplesmente um destroy genérico de Terraform. O inventário de 19/10 já encontrou EKS/RDS/ALB ausentes e dependências de rede restantes. Com EKS privado existente, a ferramenta remove os nós antes de limpar o Load Balancer diretamente pela API AWS, impedindo que o controlador o recrie. Se houver Fargate ou dependências fora do plano, interrompe a operação.

O script aguarda liberações de ENIs pelo serviço proprietário, resolve referências entre security groups da VPC do projeto e remove recursos de rede na ordem das dependências. Não força detach de interfaces gerenciadas. Os estados S3, versões antigas, delete markers e uploads multipart são tratados ao final. Uma falha produz relatório parcial e mantém as publicações bloqueadas.

## Relatório e custos

Ao final do runner, mesmo em falha, ficam um link para o resumo da execução e outro para os artefatos HTML/Markdown/JSON, com retenção de 90 dias:

Um job final independente, com role somente de leitura e outro runner, repete a auditoria mesmo se o job destrutivo falhar ou atingir o limite de tempo. Ele recupera o plano aprovado e o log anterior quando disponível. Se o runner original não publicar o log, informa essa ausência e mostra a verificação nova, sem inventar ações realizadas. Cancelamento forçado do workflow ou indisponibilidade do GitHub pode impedir jobs finais; nesse caso usar a auditoria manual abaixo.

- ✅ Recurso não encontrado na auditoria final, ou fora de operação com exclusão agendada sem a tarifa de retenção indicada.
- ❌ Recurso ainda encontrado ou exclusão com falha.
- ⚠️ Auditoria/custo indisponível ou dados estimados.
- ℹ️ Identidades preservadas sem tarifa direta de provisionamento.

O custo histórico implementado usa Cost Explorer por serviço da conta e período solicitado, com moeda e marca Estimated. **Ele não representa custo individual comprovado de cada recurso.** Sem dados de faturamento apropriados, não é possível prometer esse detalhamento. Não há rateio inventado nem substituição de erro por zero. Se o acesso continuar `User not enabled for cost explorer access`, a verificação financeira permanece pendente, mesmo que os recursos tenham sido removidos.

Consultas à API Cost Explorer também têm tarifa própria por requisição, conforme a [tabela da AWS](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/). O relatório é pontual, não um monitor contínuo. O consumo/taxas aparece separado de créditos e reembolsos, para não confundir saldo compensado com ausência de uso.

Os estados Terraform são excluídos no modo de remoção dos dados do projeto. Como IAM/OIDC são preservados sem tarifa direta, uma reconstrução futura precisará reconciliar/importar essas identidades no novo state antes de aplicar o bootstrap; não assumir que um apply em state vazio adotará recursos existentes automaticamente.

Uma auditoria posterior pode ser acionada em Actions → Phase 3 Pipeline → Run workflow → `destroy-audit`, na main. Ela consulta recursos e custos sem excluir nada. O relatório distingue comprovação de remoção, estado das exclusões agendadas e custos históricos; não declara garantia universal de zero cobrança da conta, de plano de suporte, GitHub ou New Relic.

## Verificação local

```powershell
python -m unittest discover -s .github/scripts -p 'test_*.py' -v
terraform -chdir=infra/bootstrap init -backend=false -input=false
terraform -chdir=infra/bootstrap validate
```

Os testes não executam exclusões reais. A primeira execução destrutiva continua dependendo do pedido operacional, das aprovações e do merge em ALL.
