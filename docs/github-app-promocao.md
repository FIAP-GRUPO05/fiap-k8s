# GitHub App para promocao automatica

Os quatro repositorios usam o mesmo workflow para criar os PRs de promocao. O
`GITHUB_TOKEN` consegue abrir esses PRs, mas o GitHub pode deixar as esteiras
iniciadas por eles aguardando aprovacao. Um GitHub App da organizacao permite
que as validacoes comecem automaticamente.

1. Em **FIAP-GRUPO05 > Settings > Developer settings > GitHub Apps**, crie um
   aplicativo privado, por exemplo `fiap-promocao-ci`.
2. Conceda apenas as permissoes de repositorio **Contents: Read and write** e
   **Pull requests: Read and write**. `Metadata: Read-only` e implicita. O
   workflow nao depende de webhooks; desative-os se o formulario permitir.
3. Instale o aplicativo na organizacao selecionando somente
   `fiap-application`, `fiap-lambda`, `fiap-k8s` e `fiap-database`.
4. Em **Credentials**, gere uma chave privada. Guarde o arquivo PEM fora dos
   repositorios e nao envie seu conteudo por chat.
5. Em **FIAP-GRUPO05 > Settings > Secrets and variables > Actions**, crie a
   variavel `FIAP_PROMOTION_APP_CLIENT_ID` com o **Client ID** do aplicativo e
   o segredo `FIAP_PROMOTION_APP_PRIVATE_KEY` com o conteudo integral do PEM.
   Limite ambos aos quatro repositorios.
6. Envie um commit em `feature/*`. No job `Propose`, a etapa `10a` deve gerar o
   token. O PR gerado pelo aplicativo deve iniciar o job `Verify` sem uma
   aprovacao adicional. Repita a verificacao ao promover para `release/vX.Y.Z`
   e `prod`.

Enquanto a variavel nao existir, o workflow continua com `GITHUB_TOKEN` e
exibe um aviso. Nessa condicao, o GitHub pode exigir aprovacao manual da
execucao criada pelo PR automatico.
